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
def list_pets(status: str = None, q: str = None, all_pets: bool = False, db: Session = Depends(get_db)):
    query = db.query(models.Pet)
    if not all_pets:
        query = query.filter(models.Pet.is_approved == True)
    if status:
        query = query.filter(models.Pet.status == status)
    if q:
        query = query.filter(models.Pet.name.ilike(f"%{q}%"))
    return query.all()

@app.post("/pets/approve/{pet_id}")
def approve_pet(pet_id: int, db: Session = Depends(get_db)):
    pet = db.query(models.Pet).filter(models.Pet.id == pet_id).first()
    pet.is_approved = True
    db.commit()
    return {"status": "ok"}

@app.post("/pets/delete/{pet_id}")
def delete_pet(pet_id: int, db: Session = Depends(get_db)):
    pet = db.query(models.Pet).filter(models.Pet.id == pet_id).first()
    db.delete(pet)
    db.commit()
    return {"status": "deleted"}

@app.post("/pets/upload")
async def upload_pet(
    name: str = Form(...), status: str = Form(...), user_id: int = Form(...),
    vacunado: bool = Form(False), vacunas_detalle: str = Form(None),
    lat: float = Form(None), lon: float = Form(None),
    file: UploadFile = File(...), db: Session = Depends(get_db)
):
    res = cloudinary.uploader.upload(file.file)
    new_pet = models.Pet(
        name=name, image_url=res.get("secure_url"), status=status,
        vacunado=vacunado, vacunas_detalle=vacunas_detalle,
        lat=lat, lon=lon, owner_id=user_id, is_approved=False
    )
    db.add(new_pet)
    db.commit()
    return {"message": "Enviado"}

@app.post("/login")
def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not auth.verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401)
    return {"id": user.id, "role": user.role, "email": user.email}

@app.post("/setup-admin-secreto")
def setup_admin(db: Session = Depends(get_db)):
    admin = models.User(email="admin@huellitas.com", hashed_password=auth.get_password_hash("admin123"), role="admin", is_verified=True)
    db.add(admin)
    db.commit()
    return {"message": "Admin ok"}
  
