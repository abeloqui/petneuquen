import os
import sqlite3
import requests
from io import BytesIO
from flask import Flask, render_template, request, jsonify, send_file
from PIL import Image, ImageDraw, ImageFont, ImageOps

app = Flask(__name__)
DB_PATH = 'database.db'

# Paleta de colores oficial de Huellitas NQN
COLORS = {
    'coral': (224, 122, 95),
    'celeste': (129, 178, 154),
    'crema': (244, 241, 222),
    'dark': (61, 64, 91),
    'rojo': (201, 76, 76),
    'blanco': (255, 255, 255)
}

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS pets 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, especie TEXT, 
             status TEXT, barrio TEXT, lat REAL, lng REAL, image_url TEXT)''')
        # Datos de prueba si está vacío
        cursor = conn.execute("SELECT COUNT(*) FROM pets")
        if cursor.fetchone()[0] == 0:
            conn.execute("INSERT INTO pets (name, especie, status, barrio, lat, lng, image_url) VALUES (?,?,?,?,?,?,?)",
                        ('Simba', 'gato', 'adopcion', 'Hibepa', -38.940, -68.120, 'https://placekitten.com/800/500'))

def get_font(size):
    try:
        # En Render (Linux), esta es una ruta estándar de fuentes
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except:
        return ImageFont.load_default()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/pets')
def get_pets():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM pets").fetchall()
        return jsonify([dict(r) for r in rows])

@app.route('/generate_plate/<int:pet_id>')
def generate_plate(pet_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        pet = conn.execute("SELECT * FROM pets WHERE id = ?", (pet_id,)).fetchone()
    
    if not pet: return "Mascota no encontrada", 404

    # 1. Crear lienzo base
    canvas = Image.new('RGB', (1080, 1080), COLORS['crema'])
    draw = ImageDraw.Draw(canvas)
    
    # 2. Bordes y Fondo
    draw.rectangle([20, 20, 1060, 1060], fill=COLORS['coral'])
    draw.rectangle([45, 45, 1035, 1035], fill=COLORS['blanco'])

    # 3. Logo superior
    try:
        logo = Image.open("static/logo.png").convert("RGBA")
        logo.thumbnail((250, 250))
        canvas.paste(logo, (415, 70), logo)
    except: pass

    # 4. Foto de la Mascota (con recorte inteligente)
    try:
        resp = requests.get(pet['image_url'], timeout=5)
        pet_img = Image.open(BytesIO(resp.content)).convert("RGB")
        pet_img = ImageOps.fit(pet_img, (820, 500), centering=(0.5, 0.5))
        
        mask = Image.new('L', (820, 500), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, 820, 500], radius=40, fill=255)
        canvas.paste(pet_img, (130, 240), mask)
    except: pass

    # 5. Textos (Simulación de la tipografía Lexend con DejaVu)
    f_name = get_font(110)
    f_status = get_font(50)
    f_barrio = get_font(40)

    # Nombre
    draw.text((540, 800), pet['name'].upper(), fill=COLORS['dark'], font=f_name, anchor="mm")
    
    # Estado (Dinámico)
    status_txt = "¡SE BUSCA!" if pet['status'].lower() == 'perdido' else "EN ADOPCIÓN"
    draw.text((540, 890), status_txt, fill=COLORS['rojo'], font=f_status, anchor="mm")

    # Barrio (Caja Celeste)
    btxt = f"BARRIO {pet['barrio'].upper()}"
    bbox = draw.textbbox((540, 970), btxt, font=f_barrio, anchor="mm")
    draw.rounded_rectangle([bbox[0]-40, bbox[1]-20, bbox[2]+40, bbox[3]+20], radius=30, fill=COLORS['celeste'])
    draw.text((540, 970), btxt, fill="white", font=f_barrio, anchor="mm")

    # Pie de página
    draw.text((540, 1040), "petneuquen.onrender.com", fill=(180,180,180), font=get_font(20), anchor="mm")

    # Enviar archivo
    out = BytesIO()
    canvas.save(out, format='PNG', quality=95)
    out.seek(0)
    return send_file(out, mimetype='image/png', as_attachment=True, download_name=f"Huellitas_{pet['name']}.png")

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=10000, host='0.0.0.0')
    
