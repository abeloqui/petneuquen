from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Float
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    telefono = Column(String)
    role = Column(String, default="user") # "user" o "admin"
    is_verified = Column(Boolean, default=False) # Moderación de nuevos usuarios

class Pet(Base):
    __tablename__ = "pets"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    status = Column(String) # "perdido" o "adopcion"
    barrio = Column(String)
    image_url = Column(String)
    latitud = Column(Float, nullable=True)
    longitud = Column(Float, nullable=True)
    is_approved = Column(Boolean, default=False)
    owner_id = Column(Integer, ForeignKey("users.id"))
    
