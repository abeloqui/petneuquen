from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Float
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user") 
    is_verified = Column(Boolean, default=False)

class Pet(Base):
    __tablename__ = "pets"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    species = Column(String)
    image_url = Column(String)
    status = Column(String, default="adopcion") # 'adopcion' o 'perdido'
    lat = Column(Float, nullable=True) # Para geolocalización
    lon = Column(Float, nullable=True) # Para geolocalización
    owner_id = Column(Integer, ForeignKey("users.id"))
    
