import os
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models, auth, cloudinary, cloudinary.uploader

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Configuración Cloudinary
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET")
)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

# Endpoint para el Panel Principal (Muestra las últimas 5 aprobadas)
@app.get("/pets/featured")
def featured_pets(db: Session = Depends(get_db)):
    return db.query(models.Pet).filter(models.Pet.is_approved == True).order_by(models.Pet.id.desc()).limit(5).all()

# --- TODO EL RESTO DE ENDPOINTS (Login, Upload, Approve, etc) IGUAL QUE ANTES ---
