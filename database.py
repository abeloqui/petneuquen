import sqlite3
import os
from datetime import datetime

DB_PATH = "huellitas.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        email TEXT UNIQUE,
        hashed_password TEXT,
        telefono TEXT,
        is_approved BOOLEAN DEFAULT 0,
        role TEXT DEFAULT 'user'
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS pets (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        name TEXT,
        especie TEXT,
        status TEXT,
        barrio TEXT,
        descripcion TEXT,
        latitud REAL,
        longitud REAL,
        image_url TEXT,
        is_approved BOOLEAN DEFAULT 0,
        necesita_medicacion BOOLEAN DEFAULT 0,
        esta_herido BOOLEAN DEFAULT 0,
        estado_resguardo TEXT DEFAULT 'calle',
        referencia TEXT,
        created_at TEXT
    )''')
    
    conn.commit()
    conn.close()

init_db()
