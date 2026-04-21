import os
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import cloudinary
import cloudinary.uploader
from database import SessionLocal, engine
import models, auth

models.Base.metadata.create_all(bind=engine)

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

@app.get("/pets")
def list_pets(status: str = None, db: Session = Depends(get_db)):
    # IMPORTANTE: Solo mostramos lo aprobado por el admin
    query = db.query(models.Pet).filter(models.Pet.is_approved == True)
    if status:
        query = query.filter(models.Pet.status == status)
    return query.all()

@app.post("/register")
def register(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=400, detail="Email ya registrado")
    new_user = models.User(email=email, hashed_password=auth.get_password_hash(password))
    db.add(new_user)
    db.commit()
    return {"message": "Usuario creado. El admin debe verificarte para que puedas publicar."}

@app.post("/pets/upload")
async def upload_pet(
    name: str = Form(...),
    species: str = Form(...),
    user_id: int = Form(...),
    status: str = Form(...),
    vacunado: bool = Form(False),
    vacunas_detalle: str = Form(None),
    lat: float = Form(None),
    lon: float = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or not user.is_verified:
        raise HTTPException(status_code=403, detail="Tu usuario aún no ha sido habilitado por el admin.")

    res = cloudinary.uploader.upload(file.file)
    new_pet = models.Pet(
        name=name, species=species, image_url=res.get("secure_url"),
        status=status, vacunado=vacunado, vacunas_detalle=vacunas_detalle,
        lat=lat, lon=lon, owner_id=user_id, is_approved=False # Espera aprobación
    )
    db.add(new_pet)
    db.commit()
    return {"message": "Recibido. Se publicará cuando el admin lo apruebe."}

@app.post("/setup-admin-secreto")
def setup_admin(db: Session = Depends(get_db)):
    admin = models.User(email="admin@huellitas.com", hashed_password=auth.get_password_hash("admin123"), role="admin", is_verified=True)
    db.add(admin)
    db.commit()
    return {"message": "Admin creado"}
  
