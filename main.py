import os
import logging
import sys
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import cloudinary
import cloudinary.uploader
from database import SessionLocal, engine, Base
import models, auth

# Configuración de logs para ver errores en el panel de Render
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# Crea las tablas en la base de datos al arrancar
models.Base.metadata.create_all(bind=engine)

# Configuración de Cloudinary (Variables de entorno en Render)
cloudinary.config(
  cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME"),
  api_key = os.environ.get("CLOUDINARY_API_KEY"),
  api_secret = os.environ.get("CLOUDINARY_API_SECRET")
)

app = FastAPI(title="Huellitas Neuquén API")

# Dependencia para la base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- RUTAS DE NAVEGACIÓN ---

# Montamos la carpeta 'static' para archivos CSS/JS (si los tuvieras)
# Si no tienes archivos extra en esa carpeta, no hay problema, déjalo igual
if not os.path.exists("static"):
    os.makedirs("static")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    # Esta ruta sirve tu archivo HTML principal
    return FileResponse('static/index.html')

# --- RUTAS DE LA API ---

@app.post("/register")
def register(email: str, password: str, db: Session = Depends(get_db)):
    user_exists = db.query(models.User).filter(models.User.email == email).first()
    if user_exists:
        raise HTTPException(status_code=400, detail="El email ya registrado")
    
    new_user = models.User(
        email=email, 
        hashed_password=auth.get_password_hash(password),
        role="refugio"
    )
    db.add(new_user)
    db.commit()
    return {"message": "Usuario registrado. Esperando validación admin."}

@app.post("/pets/upload")
async def upload_pet(
    name: str = Form(...),
    species: str = Form(...),
    user_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or not user.is_verified:
        raise HTTPException(status_code=403, detail="Usuario no autorizado o no validado")

    # Sube la imagen a Cloudinary
    result = cloudinary.uploader.upload(file.file)
    url = result.get("secure_url")

    new_pet = models.Pet(name=name, species=species, image_url=url, owner_id=user_id)
    db.add(new_pet)
    db.commit()
    return {"message": "Mascota publicada con éxito", "url": url}

@app.get("/pets")
def list_pets(db: Session = Depends(get_db)):
    # Este endpoint servirá para que el HTML muestre todas las mascotas
    return db.query(models.Pet).all()

# ENDPOINT TEMPORAL PARA CREAR TU ADMIN DESDE EL CELULAR
@app.post("/setup-admin-secreto")
def setup_admin(db: Session = Depends(get_db)):
    admin = db.query(models.User).filter(models.User.role == "admin").first()
    if admin:
        return {"message": "El admin ya existe"}
    
    nuevo_admin = models.User(
        email="tu-email@gmail.com", # <--- Cambia esto
        hashed_password=auth.get_password_hash("tu-clave-segura"), # <--- Cambia esto
        role="admin",
        is_verified=True
    )
    db.add(nuevo_admin)
    db.commit()
    return {"message": "Admin creado con éxito"}
  
