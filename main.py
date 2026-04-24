import os
import sqlite3
import requests
from io import BytesIO
from flask import Flask, render_template, request, jsonify, send_file
from PIL import Image, ImageDraw, ImageFont, ImageOps

# Indicamos explícitamente las carpetas
app = Flask(__name__, template_folder='templates', static_folder='static')
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
    print("Base de datos inicializada")

@app.route('/')
def index():
    # Render busca este archivo dentro de la carpeta /templates/
    return render_template('index.html')

@app.route('/pets', methods=['GET'])
def get_pets():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM pets").fetchall()
        return jsonify([dict(r) for r in rows])

# --- El generador de placas se mantiene igual ya que es robusto ---
@app.route('/generate_plate/<int:pet_id>')
def generate_plate(pet_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        pet = conn.execute("SELECT * FROM pets WHERE id = ?", (pet_id,)).fetchone()
    
    if not pet: return "Mascota no encontrada", 404

    canvas = Image.new('RGB', (1080, 1080), COLORS['crema'])
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([20, 20, 1060, 1060], fill=COLORS['coral'])
    draw.rectangle([45, 45, 1035, 1035], fill=COLORS['blanco'])

    try:
        resp = requests.get(pet['image_url'], timeout=5)
        pet_img = Image.open(BytesIO(resp.content)).convert("RGB")
        pet_img = ImageOps.fit(pet_img, (820, 500), centering=(0.5, 0.5))
        mask = Image.new('L', (820, 500), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, 820, 500], radius=40, fill=255)
        canvas.paste(pet_img, (130, 240), mask)
    except: pass

    # Tipografía por defecto para evitar errores de archivo en Render
    font_name = ImageFont.load_default()
    draw.text((540, 800), pet['name'].upper(), fill=COLORS['dark'], font=font_name, anchor="mm")

    out = BytesIO()
    canvas.save(out, format='PNG')
    out.seek(0)
    return send_file(out, mimetype='image/png', as_attachment=True, download_name=f"{pet['name']}.png")

if __name__ == '__main__':
    init_db()
    # Usamos el puerto que Render nos asigne
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    
