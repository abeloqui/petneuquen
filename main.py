import os
import sqlite3
import requests
from io import BytesIO
from flask import Flask, render_template, request, jsonify, send_file
from PIL import Image, ImageDraw, ImageFont, ImageOps

app = Flask(__name__)
DB_PATH = 'database.db'

# 1. ASEGURAR CARPETAS (Crucial para Render)
if not os.path.exists('static'):
    os.makedirs('static')

# Paleta de colores Huellitas NQN
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

def get_font(size):
    # En Linux (Render), las fuentes están aquí. Si falla, usa la default.
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    ]
    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/pets', methods=['GET'])
def get_pets():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM pets").fetchall()
        return jsonify([dict(r) for r in rows])

@app.route('/pets', methods=['POST'])
def add_pet():
    data = request.form
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO pets (name, especie, status, barrio, lat, lng, image_url) VALUES (?,?,?,?,?,?,?)",
                    (data['name'], data['especie'], data['status'], data['barrio'], data['lat'], data['lng'], data['image_url']))
    return jsonify({"status": "ok"})

@app.route('/generate_plate/<int:pet_id>')
def generate_plate(pet_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        pet = conn.execute("SELECT * FROM pets WHERE id = ?", (pet_id,)).fetchone()
    
    if not pet: return "No encontrado", 404

    # Crear lienzo
    canvas = Image.new('RGB', (1080, 1080), COLORS['crema'])
    draw = ImageDraw.Draw(canvas)
    
    # Diseño de Placa
    draw.rectangle([20, 20, 1060, 1060], fill=COLORS['coral'])
    draw.rectangle([45, 45, 1035, 1035], fill=COLORS['blanco'])

    # Logo (Opcional si existe el archivo)
    if os.path.exists("static/logo.png"):
        logo = Image.open("static/logo.png").convert("RGBA")
        logo.thumbnail((250, 250))
        canvas.paste(logo, (415, 70), logo)

    # Procesar Foto
    try:
        resp = requests.get(pet['image_url'], timeout=5)
        pet_img = Image.open(BytesIO(resp.content)).convert("RGB")
        pet_img = ImageOps.fit(pet_img, (820, 500), centering=(0.5, 0.5))
        mask = Image.new('L', (820, 500), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, 820, 500], radius=40, fill=255)
        canvas.paste(pet_img, (130, 240), mask)
    except:
        draw.rectangle([130, 240, 950, 740], fill=(240, 240, 240)) # Cuadro gris si falla foto

    # Textos
    f_name = get_font(110)
    f_status = get_font(55)
    f_barrio = get_font(42)

    draw.text((540, 800), pet['name'].upper(), fill=COLORS['dark'], font=f_name, anchor="mm")
    
    st_text = "¡SE BUSCA!" if pet['status'] == 'perdido' else "EN ADOPCIÓN"
    draw.text((540, 895), st_text, fill=COLORS['rojo'], font=f_status, anchor="mm")

    # Botón Barrio
    txt = f"BARRIO {pet['barrio'].upper()}"
    bbox = draw.textbbox((540, 975), txt, font=f_barrio, anchor="mm")
    draw.rounded_rectangle([bbox[0]-40, bbox[1]-20, bbox[2]+40, bbox[3]+20], radius=30, fill=COLORS['celeste'])
    draw.text((540, 975), txt, fill="white", font=f_barrio, anchor="mm")

    draw.text((540, 1045), "petneuquen.onrender.com", fill=(180,180,180), font=get_font(22), anchor="mm")

    out = BytesIO()
    canvas.save(out, format='PNG')
    out.seek(0)
    return send_file(out, mimetype='image/png', as_attachment=True, download_name=f"{pet['name']}.png")

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
        
