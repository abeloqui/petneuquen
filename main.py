import os
import re
import cloudinary
import cloudinary.uploader
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models, auth

# Crea las tablas si no existen
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Configuración de Cloudinary (Asegurate de configurar estas variables en Render)
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET")
)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --- VALIDACIONES REFORZADAS ---
def validar_datos(email, telefono):
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if not re.match(email_regex, email):
        raise HTTPException(status_code=400, detail="El formato del email no es válido.")
    # Limpia el teléfono de espacios o guiones y verifica longitud
    tel_limpio = "".join(filter(str.isdigit, str(telefono)))
    if len(tel_limpio) < 8:
        raise HTTPException(status_code=400, detail="El teléfono debe tener al menos 8 dígitos numéricos.")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index(): return FileResponse('static/index.html')

# --- AUTENTICACIÓN Y REGISTRO ---
@app.post("/register")
def register(email: str = Form(...), password: str = Form(...), telefono: str = Form(...), db: Session = Depends(get_db)):
    validar_datos(email, telefono)
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=400, detail="Este email ya está registrado.")
    
    new_user = models.User(
        email=email, 
        telefono=telefono, 
        hashed_password=auth.get_password_hash(password),
        is_verified=False # Requiere aprobación del admin
    )
    db.add(new_user)
    db.commit()
    return {"message": "Usuario registrado, pendiente de aprobación."}

@app.post("/login")
def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not auth.verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos.")
    if not user.is_verified and user.role != "admin":
        raise HTTPException(status_code=403, detail="Tu cuenta aún no ha sido aprobada por el administrador.")
    return {"id": user.id, "role": user.role, "telefono": user.telefono, "email": user.email}

# --- GESTIÓN DE MASCOTAS ---
@app.get("/pets")
def list_pets(all_pets: bool = False, db: Session = Depends(get_db)):
    # Traemos la mascota y el teléfono del dueño haciendo un Join
    query = db.query(models.Pet, models.User.telefono).join(models.User)
    if not all_pets:
        query = query.filter(models.Pet.is_approved == True)
    results = query.all()
    return [{**p.__dict__, "telefono": tel} for p, tel in results]

@app.post("/pets/upload")
async def upload(name: str = Form(...), status: str = Form(...), barrio: str = Form(...), 
                 raza: str = Form(None), edad: str = Form(None),
                 user_id: int = Form(...), latitud: float = Form(None), longitud: float = Form(None),
                 file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Subida a Cloudinary
    result = cloudinary.uploader.upload(file.file)
    new_pet = models.Pet(
        name=name, status=status, barrio=barrio, raza=raza, edad=edad,
        image_url=result.get("secure_url"), owner_id=user_id, 
        latitud=latitud, longitud=longitud, is_approved=False # Pendiente de moderación
    )
    db.add(new_pet)
    db.commit()
    return {"message": "Mascota enviada a revisión."}

# --- PANEL DE ADMINISTRACIÓN ---
@app.get("/admin/users/pending")
def pending_users(db: Session = Depends(get_db)):
    return db.query(models.User).filter(models.User.is_verified == False, models.User.role != "admin").all()

@app.post("/admin/users/approve/{u_id}")
def approve_user(u_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == u_id).first()
    if user:
        user.is_verified = True
        db.commit()
    return {"status": "usuario aprobado"}

@app.delete("/admin/users/delete/{u_id}")
def delete_user(u_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == u_id).first()
    if user:
        db.delete(user)
        db.commit()
    return {"status": "usuario rechazado"}

@app.post("/pets/approve/{pid}")
def approve_pet(pid: int, db: Session = Depends(get_db)):
    pet = db.query(models.Pet).filter(models.Pet.id == pid).first()
    if pet:
        pet.is_approved = True
        db.commit()
    return {"status": "publicación aprobada"}

@app.delete("/admin/pets/delete/{pid}")
def delete_pet(pid: int, db: Session = Depends(get_db)):
    pet = db.query(models.Pet).filter(models.Pet.id == pid).first()
    if pet:
        db.delete(pet)
        db.commit()
    return {"status": "publicación eliminada"}

# Inicialización automática del Administrador
@app.on_event("startup")
def startup():
    db = SessionLocal()
    try:
        if not db.query(models.User).filter(models.User.role == "admin").first():
            admin = models.User(
                email="admin@huellitas.com", 
                telefono="299000000", 
                hashed_password=auth.get_password_hash("admin123"), 
                role="admin", 
                is_verified=True
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()
        
