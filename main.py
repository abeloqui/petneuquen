import os
import sqlite3
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from PIL import Image, ImageDraw, ImageFont, ImageOps
import requests
from io import BytesIO
from datetime import datetime

app = Flask(__name__)
DB_PATH = 'database.db'

# --- CONFIGURACIÓN DE COLORES ---
COLORS = {
    'coral': (224, 122, 95),
    'celeste': (129, 178, 154),
    'crema': (244, 241, 222),
    'dark': (61, 64, 91),
    'rojo': (201, 76, 76),
    'blanco': (255, 255, 255)
}

# --- BASE DE DATOS ---
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users 
            (id INTEGER PRIMARY KEY, email TEXT, password TEXT, telefono TEXT, role TEXT, is_approved INTEGER)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS pets 
            (id INTEGER PRIMARY KEY, name TEXT, especie TEXT, status TEXT, barrio TEXT, 
             latitud REAL, longitud REAL, image_url TEXT, user_id INTEGER, is_approved INTEGER)''')
        # Admin por defecto si no existe
        conn.execute("INSERT OR IGNORE INTO users (id, email, password, role, is_approved) VALUES (1, 'admin@huellitas.com', 'admin123', 'admin', 1)")

# --- LÓGICA DE GENERACIÓN DE PLACA (PILLOW) ---
def get_font(size):
    try:
        # En Render/Linux suele estar en esta ruta
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except:
        return ImageFont.load_default()

@app.route('/generate_plate/<int:pet_id>')
def generate_plate(pet_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        pet = conn.execute("SELECT * FROM pets WHERE id = ?", (pet_id,)).fetchone()
    
    if not pet: return "Mascota no encontrada", 404

    # Crear lienzo 1080x1080
    canvas = Image.new('RGB', (1080, 1080), COLORS['crema'])
    draw = ImageDraw.Draw(canvas)
    
    # Borde y Fondo Blanco
    draw.rectangle([20, 20, 1060, 1060], fill=COLORS['coral'])
    draw.rectangle([45, 45, 1035, 1035], fill=COLORS['blanco'])

    # Logo
    try:
        logo = Image.open("static/logo.png").convert("RGBA")
        logo.thumbnail((250, 250))
        canvas.paste(logo, (415, 70), logo)
    except: pass

    # Imagen Mascota (Procesado de URL)
    try:
        resp = requests.get(pet['image_url'], timeout=5)
        pet_img = Image.open(BytesIO(resp.content)).convert("RGB")
        pet_img = ImageOps.fit(pet_img, (800, 500), centering=(0.5, 0.5))
        
        # Máscara redondeada
        mask = Image.new('L', (800, 500), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0,0,800,500], radius=50, fill=255)
        canvas.paste(pet_img, (140, 240), mask)
    except: pass

    # Textos
    f_name = get_font(120)
    f_status = get_font(50)
    f_barrio = get_font(45)

    draw.text((540, 800), pet['name'].upper(), fill=COLORS['dark'], font=f_name, anchor="mm")
    
    status_txt = "¡SE BUSCA!" if pet['status'] == 'perdido' else "EN ADOPCIÓN"
    draw.text((540, 900), status_txt, fill=COLORS['rojo'], font=f_status, anchor="mm")

    # Botón Barrio
    btxt = f"BARRIO {pet['barrio'].upper()}"
    bbox = draw.textbbox((540, 980), btxt, font=f_barrio, anchor="mm")
    draw.rounded_rectangle([bbox[0]-30, bbox[1]-15, bbox[2]+30, bbox[3]+15], radius=30, fill=COLORS['celeste'])
    draw.text((540, 980), btxt, fill="white", font=f_barrio, anchor="mm")

    draw.text((540, 1045), "petneuquen.onrender.com", fill=(180, 180, 180), font=get_font(22), anchor="mm")

    output = BytesIO()
    canvas.save(output, format='PNG')
    output.seek(0)
    return send_file(output, mimetype='image/png', as_attachment=True, download_name=f"{pet['name']}.png")

# --- RUTAS DE API ---
@app.route('/pets')
def get_pets():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        pets = conn.execute("SELECT * FROM pets WHERE is_approved = 1").fetchall()
        return jsonify([dict(p) for p in pets])

@app.route('/login', methods=['POST'])
def login():
    data = request.form
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        user = conn.execute("SELECT * FROM users WHERE email = ? AND password = ?", 
                           (data['email'], data['password'])).fetchone()
        if user: return jsonify(dict(user))
        return "Error", 401

@app.route('/')
def index(): return render_template('index.html')

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
    
