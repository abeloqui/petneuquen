from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Float
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    telefono = Column(String)
    role = Column(String, default="user") 
    is_verified = Column(Boolean, default=False) 

class Pet(Base):
    __tablename__ = "pets"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    status = Column(String) 
    barrio = Column(String)
    raza = Column(String, nullable=True)
    edad = Column(String, nullable=True)
    image_url = Column(String)
    latitud = Column(Float, nullable=True)
    longitud = Column(Float, nullable=True)
    is_approved = Column(Boolean, default=False)
    owner_id = Column(Integer, ForeignKey("users.id"))
    
    # --- NUEVAS COLUMNAS ---
    necesita_medicacion = Column(Boolean, default=False)
    esta_herido = Column(Boolean, default=False)
    estado_resguardo = Column(String, default="calle")
    referencia = Column(String, nullable=True)
    
