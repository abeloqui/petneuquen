import os
import cloudinary
import cloudinary.uploader
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models, auth

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

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
async def read_index(): return FileResponse('static/index.html')

# --- AUTH ---
@app.post("/register")
def register(email: str = Form(...), password: str = Form(...), telefono: str = Form(...), db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=400, detail="Email ya registrado")
    new_user = models.User(email=email, telefono=telefono, hashed_password=auth.get_password_hash(password), is_verified=False)
    db.add(new_user)
    db.commit()
    return {"message": "Cuenta creada. Espera aprobación del admin."}

@app.post("/login")
def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not auth.verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Error de acceso")
    if not user.is_verified and user.role != "admin":
        raise HTTPException(status_code=403, detail="Cuenta pendiente de aprobación.")
    return {"id": user.id, "role": user.role, "telefono": user.telefono, "email": user.email}

# --- MASCOTAS ---
@app.get("/pets")
def list_pets(all_pets: bool = False, db: Session = Depends(get_db)):
    query = db.query(models.Pet, models.User.telefono).join(models.User)
    if not all_pets: query = query.filter(models.Pet.is_approved == True)
    results = query.all()
    return [{**p.__dict__, "telefono": tel} for p, tel in results]

@app.post("/pets/upload")
async def upload(name: str = Form(...), status: str = Form(...), barrio: str = Form(...), 
                 user_id: int = Form(...), latitud: float = Form(None), longitud: float = Form(None),
                 file: UploadFile = File(...), db: Session = Depends(get_db)):
    res = cloudinary.uploader.upload(file.file)
    new_pet = models.Pet(name=name, status=status, barrio=barrio, image_url=res.get("secure_url"), 
                         owner_id=user_id, latitud=latitud, longitud=longitud)
    db.add(new_pet)
    db.commit()
    return {"message": "Enviado"}

# --- ADMIN PANEL ---
@app.get("/admin/users/pending")
def pending_users(db: Session = Depends(get_db)):
    return db.query(models.User).filter(models.User.is_verified == False).all()

@app.post("/admin/users/approve/{u_id}")
def approve_user(u_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == u_id).first()
    if user: user.is_verified = True
    db.commit()
    return {"status": "ok"}

@app.post("/pets/approve/{pid}")
def approve_pet(pid: int, db: Session = Depends(get_db)):
    pet = db.query(models.Pet).filter(models.Pet.id == pid).first()
    if pet: pet.is_approved = True
    db.commit()
    return {"status": "ok"}

@app.on_event("startup")
def startup():
    db = SessionLocal()
    try:
        if not db.query(models.User).filter(models.User.role == "admin").first():
            admin = models.User(email="admin@huellitas.com", telefono="299000000", 
                                hashed_password=auth.get_password_hash("admin123"), role="admin", is_verified=True)
            db.add(admin)
            db.commit()
    finally: db.close()
                
