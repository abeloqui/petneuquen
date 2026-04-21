from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Float
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user") # 'admin' o 'user'
    is_verified = Column(Boolean, default=False)

class Pet(Base):
    __tablename__ = "pets"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    species = Column(String)
    image_url = Column(String)
    status = Column(String) # 'adopcion' o 'perdido'
    vacunado = Column(Boolean, default=False)
    vacunas_detalle = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    is_approved = Column(Boolean, default=False) 
    owner_id = Column(Integer, ForeignKey("users.id"))
    
