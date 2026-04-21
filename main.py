import os
import logging
import sys
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import cloudinary
import cloudinary.uploader
from database import SessionLocal, engine
import models, auth

# 1. Configuración de Logs (para ver errores en Render)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# 2. Creación de tablas en la DB
models.Base.metadata.create_all(bind=engine)

# 3. Configuración de Cloudinary
cloudinary.config(
  cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME"),
  api_key = os.environ.get("CLOUDINARY_API_KEY"),
  api_secret = os.environ.get("CLOUDINARY_API_SECRET")
)

app = FastAPI(title="Huellitas Neuquén - API")

# Dependencia de Base de Datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- CONFIGURACIÓN DE ARCHIVOS ESTÁTICOS ---

if not os.path.exists("static"):
    os.makedirs("static")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

# --- ENDPOINTS DE LA API ---

@app.get("/pets")
def list_pets(status: str = None, db: Session = Depends(get_db)):
    query = db.query(models.Pet)
    if status:
        query = query.filter(models.Pet.status == status)
    return query.all()

@app.post("/pets/upload")
async def upload_pet(
    name: str = Form(...),
    species: str = Form(...),
    user_id: int = Form(...),
    status: str = Form("adopcion"), # 'adopcion' o 'perdido'
    lat: float = Form(None),
    lon: float = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Verificación de usuario y permisos
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or not user.is_verified:
        raise HTTPException(status_code=403, detail="Usuario no autorizado o no validado por admin")

    # Subida a Cloudinary
    try:
        upload_result = cloudinary.uploader.upload(file.file)
        image_url = upload_result.get("secure_url")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error subiendo imagen: {str(e)}")

    # Guardado en DB
    new_pet = models.Pet(
        name=name,
        species=species,
        image_url=image_url,
        status=status,
        lat=lat,
        lon=lon,
        owner_id=user_id
    )
    db.add(new_pet)
    db.commit()
    db.refresh(new_pet)
    
    return {"message": "Mascota publicada con éxito", "pet": new_pet}

@app.post("/register")
def register(email: str, password: str, db: Session = Depends(get_db)):
    user_exists = db.query(models.User).filter(models.User.email == email).first()
    if user_exists:
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    
    new_user = models.User(
        email=email, 
        hashed_password=auth.get_password_hash(password),
        role="refugio" # Por defecto son refugios esperando validación
    )
    db.add(new_user)
    db.commit()
    return {"message": "Registro exitoso. Un administrador debe validar tu cuenta."}

# --- ACCESO DE EMERGENCIA (ADMIN) ---

@app.post("/setup-admin-secreto")
def setup_admin(db: Session = Depends(get_db)):
    # Cambia estos datos por los tuyos antes de hacer el commit
    admin_email = "tu-email@gmail.com"
    admin_pass = "tu-clave-segura"
    
    admin = db.query(models.User).filter(models.User.role == "admin").first()
    if admin:
        return {"message": "El administrador ya existe"}
    
    nuevo_admin = models.User(
        email=admin_email,
        hashed_password=auth.get_password_hash(admin_pass),
        role="admin",
        is_verified=True
    )
    db.add(nuevo_admin)
    db.commit()
    return {"message": "Admin creado correctamente."}
  
