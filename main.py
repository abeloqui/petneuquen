import os
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
import cloudinary
import cloudinary.uploader
from database import SessionLocal, engine, Base
import models, auth

# Crea las tablas en la base de datos al arrancar
models.Base.metadata.create_all(bind=engine)

# Configuración de Cloudinary
cloudinary.config(
  cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME"),
  api_key = os.environ.get("CLOUDINARY_API_KEY"),
  api_secret = os.environ.get("CLOUDINARY_API_SECRET")
)

app = FastAPI(title="PetNeuquen API")

# Dependencia para la base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def home():
    return {"status": "PetNeuquen Online"}

@app.post("/register")
def register(email: str, password: str, db: Session = Depends(get_db)):
    user_exists = db.query(models.User).filter(models.User.email == email).first()
    if user_exists:
        raise HTTPException(status_code=400, detail="El email ya existe")
    
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

    result = cloudinary.uploader.upload(file.file)
    url = result.get("secure_url")

    new_pet = models.Pet(name=name, species=species, image_url=url, owner_id=user_id)
    db.add(new_pet)
    db.commit()
    return {"message": "Mascota publicada", "url": url}

@app.post("/setup-admin-secreto")
def setup_admin(db: Session = Depends(get_db)):
    # Verificamos si ya existe un admin para no crear duplicados
    admin = db.query(models.User).filter(models.User.role == "admin").first()
    if admin:
        return {"message": "El admin ya existe"}
    
    nuevo_admin = models.User(
        email="tu-email@gmail.com", # <--- PONÉ TU MAIL ACÁ
        hashed_password=auth.get_password_hash("tu-clave-segura"), # <--- PONÉ TU CLAVE ACÁ
        role="admin",
        is_verified=True
    )
    db.add(nuevo_admin)
    db.commit()
    return {"message": "Admin creado con éxito desde el celu"}
  
