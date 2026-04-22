import os
import cloudinary
import cloudinary.uploader
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models, auth

# Crear tablas si no existen (esto no borra datos existentes)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Huellitas NQN")

# Configuración de Cloudinary
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET")
)

# Dependencia de Base de Datos
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

# --- RUTAS DE AUTENTICACIÓN ---

@app.post("/register")
def register(email: str = Form(...), password: str = Form(...), telefono: str = Form(...), db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    
    new_user = models.User(
        email=email,
        telefono=telefono,
        hashed_password=auth.get_password_hash(password),
        is_verified=True
    )
    db.add(new_user)
    db.commit()
    return {"message": "Usuario registrado con éxito"}

@app.post("/login")
def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not auth.verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "telefono": user.telefono
    }

# --- RUTAS DE MASCOTAS ---

@app.get("/pets")
def list_pets(status: str = None, all_pets: bool = False, db: Session = Depends(get_db)):
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
        res = cloudinary.uploader.upload(file.file)
        new_pet = models.Pet(
            name=name,
            status=status,
            barrio=barrio,
            image_url=res.get("secure_url"),
            owner_id=user_id,
            is_approved=False 
        )
        db.add(new_pet)
        db.commit()
        return {"message": "Mascota enviada correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/pets/approve/{pet_id}")
def approve_pet(pet_id: int, db: Session = Depends(get_db)):
    pet = db.query(models.Pet).filter(models.Pet.id == pet_id).first()
    if not pet:
        raise HTTPException(status_code=404, detail="No encontrado")
    pet.is_approved = True
    db.commit()
    return {"message": "Aprobado"}

# --- EVENTO DE INICIO: CREAR ADMIN ---

@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    try:
        admin = db.query(models.User).filter(models.User.role == "admin").first()
        if not admin:
            new_admin = models.User(
                email="admin@huellitas.com",
                telefono="299000000",
                hashed_password=auth.get_password_hash("admin123"),
                role="admin",
                is_verified=True
            )
            db.add(new_admin)
            db.commit()
    except Exception as e:
        print(f"Error en el inicio: {e}")
    finally:
        db.close()
        
