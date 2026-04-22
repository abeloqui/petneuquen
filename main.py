import os
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import cloudinary, cloudinary.uploader
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

@app.get("/pets")
def list_pets(status: str = None, db: Session = Depends(get_db)):
    # Hacemos un Join para traer el teléfono del dueño también
    query = db.query(models.Pet, models.User.telefono).\
            join(models.User, models.Pet.owner_id == models.User.id).\
            filter(models.Pet.is_approved == True)
    
    if status:
        query = query.filter(models.Pet.status == status)
    
    results = query.all()
    # Formateamos la respuesta para que el JS la entienda fácil
    return [{**p.__dict__, "telefono": tel} for p, tel in results]

@app.post("/login")
def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not auth.verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401)
    return {"id": user.id, "role": user.role, "telefono": user.telefono}

@app.post("/pets/approve/{pet_id}")
def approve_pet(pet_id: int, db: Session = Depends(get_db)):
    pet = db.query(models.Pet).filter(models.Pet.id == pet_id).first()
    pet.is_approved = True
    db.commit()
    return {"status": "ok"}
    
