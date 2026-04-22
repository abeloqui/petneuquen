import os
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import cloudinary, cloudinary.uploader
from database import SessionLocal, engine
import models, auth

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index(): return FileResponse('static/index.html')

# --- BUSCADOR ROBUSTO ---
@app.get("/pets/search")
def search_pets(status: str = None, barrio: str = None, q: str = None, db: Session = Depends(get_db)):
    query = db.query(models.Pet).filter(models.Pet.is_approved == True)
    if status: query = query.filter(models.Pet.status == status)
    if barrio: query = query.filter(models.Pet.barrio == barrio)
    if q: query = query.filter(models.Pet.name.ilike(f"%{q}%"))
    return query.all()

# --- UPLOAD CON TELÉFONO ---
@app.post("/pets/upload")
async def upload_pet(
    name: str = Form(...), barrio: str = Form(...), user_id: int = Form(...),
    status: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)
):
    # Lógica de subida...
    res = cloudinary.uploader.upload(file.file)
    new_pet = models.Pet(
        name=name, barrio=barrio, image_url=res.get("secure_url"),
        status=status, owner_id=user_id, is_approved=False
    )
    db.add(new_pet)
    db.commit()
    return {"status": "enviado_revision"}
    
