import os
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
import cloudinary
import cloudinary.uploader
from database import SessionLocal, engine
import models, auth

models.Base.metadata.create_all(bind=engine)

# Configuración de Cloudinary (Usa variables de entorno en Render)
cloudinary.config(
  cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME"),
  api_key = os.environ.get("CLOUDINARY_API_KEY"),
  api_secret = os.environ.get("CLOUDINARY_API_SECRET")
)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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
        raise HTTPException(status_code=403, detail="Usuario no validado")

    # Subir imagen a Cloudinary
    result = cloudinary.uploader.upload(file.file)
    url = result.get("secure_url")

    new_pet = models.Pet(name=name, species=species, image_url=url, owner_id=user_id)
    db.add(new_pet)
    db.commit()
    return {"message": "Mascota publicada", "url": url}
