import os
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import cloudinary
import cloudinary.uploader
from database import SessionLocal, engine
import models, auth

# Intentamos crear las tablas si no existen
models.Base.metadata.create_all(bind=engine)

# Configuración de Cloudinary
cloudinary.config(
  cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME"),
  api_key = os.environ.get("CLOUDINARY_API_KEY"),
  api_secret = os.environ.get("CLOUDINARY_API_SECRET")
)

app = FastAPI(title="Huellitas NQN API")

# Dependencia de DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Servir archivos estáticos
if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

# --- AUTENTICACIÓN ---

@app.post("/register")
def register(
    email: str = Form(...), 
    password: str = Form(...), 
    telefono: str = Form(...), 
    db: Session = Depends(get_db)
):
    user_exists = db.query(models.User).filter(models.User.email == email).first()
    if user_exists:
        raise HTTPException(status_code=400, detail="El email ya está registrado.")
    
    # Hasheo de password (bcrypt limita a 72 caracteres, auth.py debería manejarlo)
    hashed = auth.get_password_hash(password)
    
    new_user = models.User(
        email=email,
        telefono=telefono,
        hashed_password=hashed,
        is_verified=True # Cambiar a False si querés validar vos primero
    )
    db.add(new_user)
    db.commit()
    return {"message": "Usuario creado correctamente"}

@app.post("/login")
def login(
    email: str = Form(...), 
    password: str = Form(...), 
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not auth.verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    return {
        "id": user.id, 
        "email": user.email, 
        "role": user.role, 
        "telefono": user.telefono
    }

# --- GESTIÓN DE MASCOTAS ---

@app.get("/pets")
def list_pets(status: str = None, all_pets: bool = False, db: Session = Depends(get_db)):
    # Traemos la mascota y el teléfono del dueño (User)
    query = db.query(models.Pet, models.User.telefono).join(models.User)
    
    if not all_pets:
        query = query.filter(models.Pet.is_approved == True)
    
    if status:
        query = query.filter(models.Pet.status == status)
    
    results = query.all()
    return [{**p.__dict__, "telefono": tel} for p, tel in results]

@app.post("/pets/upload")
async def upload_pet(
    name: str = Form(...),
    status: str = Form(...),
    barrio: str = Form(...),
    user_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        # Subida a Cloudinary
        upload_result = cloudinary.uploader.upload(file.file)
        
        new_pet = models.Pet(
            name=name,
            status=status,
            barrio=barrio,
            image_url=upload_result.get("secure_url"),
            owner_id=user_id,
            is_approved=False # Siempre requiere aprobación del admin
        )
        db.add(new_pet)
        db.commit()
        return {"message": "Mascota enviada a revisión"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir: {str(e)}")

@app.post("/pets/approve/{pet_id}")
def approve_pet(pet_id: int, db: Session = Depends(get_db)):
    pet = db.query(models.Pet).filter(models.Pet.id == pet_id).first()
    if not pet:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")
    pet.is_approved = True
    db.commit()
    return {"message": "Mascota aprobada con éxito"}

@app.post("/pets/delete/{pet_id}")
def delete_pet(pet_id: int, db: Session = Depends(get_db)):
    pet = db.query(models.Pet).filter(models.Pet.id == pet_id).first()
    if not pet:
        raise HTTPException(status_code=404, detail="No encontrada")
    db.delete(pet)
    db.commit()
    return {"message": "Eliminada"}

# --- EVENTO DE ARRANQUE (ROOT USER) ---

@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    try:
        # Buscamos si ya existe un admin
        admin = db.query(models.User).filter(models.User.role == "admin").first()
        if not admin:
            print("Cargando Administrador por defecto...")
            # IMPORTANTE: El password no debe ser largo para evitar el error de 72 bytes
            hashed_pw = auth.get_password_hash("admin123")
            
            root_admin = models.User(
                email="admin@huellitas.com",
                telefono="299000000",
                hashed_password=hashed_pw,
                role="admin",
                is_verified=True
            )
            db.add(root_admin)
            db.commit()
            print("✅ Administrador creado: admin@huellitas.com / admin123")
    except Exception as e:
        print(f"⚠️ Error durante el inicio: {e}")
    finally:
        db.close()
      
