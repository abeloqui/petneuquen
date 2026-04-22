import os
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import cloudinary
import cloudinary.uploader
from database import SessionLocal, engine
import models, auth

# Iniciamos base de datos
models.Base.metadata.create_all(bind=engine)

# Cloudinary
cloudinary.config(
  cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME"),
  api_key = os.environ.get("CLOUDINARY_API_KEY"),
  api_secret = os.environ.get("CLOUDINARY_API_SECRET")
)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index(): return FileResponse('static/index.html')

# --- API ---

@app.post("/pets/upload")
async def upload_pet(
    name: str = Form(...),
    status: str = Form(...), # 'adopcion' o 'perdido'
    user_id: int = Form(...),
    vacunado: bool = Form(False),
    vacunas_detalle: str = Form(None),
    lat: float = Form(None),
    lon: float = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Verificación de usuario (Debe estar verificado por vos)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or not user.is_verified:
        raise HTTPException(status_code=403, detail="Tu cuenta no está autorizada para publicar.")

    # Subida a la nube
    res = cloudinary.uploader.upload(file.file)
    
    new_pet = models.Pet(
        name=name,
        species="Mascota", # Generalizamos para simplificar
        image_url=res.get("secure_url"),
        status=status,
        vacunado=vacunado,
        vacunas_detalle=vacunas_detalle,
        lat=lat,
        lon=lon,
        is_approved=False, # <-- IMPORTANTE: Nadie ve nada hasta que vos apruebes
        owner_id=user_id
    )
    db.add(new_pet)
    db.commit()
    return {"message": "Enviado con éxito. El admin lo revisará pronto."}

# Login simple para el celu
@app.post("/login")
def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not auth.verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Error de acceso")
    return {"id": user.id, "role": user.role, "is_verified": user.is_verified}

# Endpoint secreto para crearte vos mismo
@app.post("/setup-admin-secreto")
def setup_admin(db: Session = Depends(get_db)):
    admin = models.User(
        email="tu-email@gmail.com", 
        hashed_password=auth.get_password_hash("admin123"), 
        role="admin", 
        is_verified=True
    )
    db.add(admin)
    db.commit()
    return {"message": "Admin creado. Clave: admin123"}
  
