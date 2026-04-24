from flask import Flask, render_template, request, jsonify, send_file
from PIL import Image, ImageDraw, ImageFont, ImageOps
import requests
from io import BytesIO
import os

app = Flask(__name__)

# Configuración de colores (Huellitas NQN)
COLOR_CORAL = (224, 122, 95)
COLOR_CELESTE = (129, 178, 154)
COLOR_CREMA = (244, 241, 222)
COLOR_DARK = (61, 64, 91)
COLOR_ROJO = (201, 76, 76)

def get_font(size):
    # Intentamos cargar una fuente del sistema, si no, usamos la básica
    try:
        return ImageFont.truetype("arialbd.ttf", size) # O la ruta a tu fuente Lexend
    except:
        return ImageFont.load_default()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_plate')
def generate_plate():
    name = request.args.get('name', 'Mascota').upper()
    barrio = request.args.get('barrio', 'Neuquén').upper()
    status = request.args.get('status', 'perdido')
    img_url = request.args.get('img_url')

    # 1. Crear lienzo base (1080x1080)
    canvas = Image.new('RGB', (1080, 1080), COLOR_CREMA)
    draw = ImageDraw.Draw(canvas)

    # 2. Dibujar borde Coral
    border_width = 45
    draw.rectangle([border_width/2, border_width/2, 1080-border_width/2, 1080-border_width/2], 
                   outline=COLOR_CORAL, width=border_width)
    
    # Relleno blanco central
    draw.rectangle([border_width, border_width, 1080-border_width, 1080-border_width], fill="white")

    # 3. Insertar Logo (Si existe localmente)
    try:
        logo = Image.open("static/logo.png").convert("RGBA")
        logo.thumbnail((300, 300))
        canvas.paste(logo, (390, 70), logo)
    except:
        pass

    # 4. Procesar Imagen de la Mascota
    try:
        response = requests.get(img_url)
        pet_img = Image.open(BytesIO(response.content)).convert("RGB")
        # Hacerla cuadrada y centrarla (Object-fit: cover manual)
        pet_img = ImageOps.fit(pet_img, (850, 500), centering=(0.5, 0.5))
        
        # Redondear esquinas
        mask = Image.new('L', (850, 500), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.rounded_rectangle([0, 0, 850, 500], radius=40, fill=255)
        
        canvas.paste(pet_img, (115, 230), mask)
    except Exception as e:
        print(f"Error imagen: {e}")

    # 5. Escribir Textos
    font_name = get_font(110)
    font_status = get_font(50)
    font_barrio = get_font(40)

    # Nombre
    draw.text((540, 780), name, fill=COLOR_DARK, font=font_name, anchor="mm")
    
    # Estado
    txt_status = "¡SE BUSCA!" if status == "perdido" else "EN ADOPCIÓN"
    draw.text((540, 880), txt_status, fill=COLOR_ROJO, font=font_status, anchor="mm")

    # Barrio (Caja Verde)
    barrio_txt = f"BARRIO {barrio}"
    bbox = draw.textbbox((540, 960), barrio_txt, font=font_barrio, anchor="mm")
    draw.rounded_rectangle([bbox[0]-40, bbox[1]-20, bbox[2]+40, bbox[3]+20], radius=30, fill=COLOR_CELESTE)
    draw.text((540, 960), barrio_txt, fill="white", font=font_barrio, anchor="mm")

    # URL pie
    draw.text((540, 1030), "petneuquen.onrender.com", fill=(150, 150, 150), font=get_font(20), anchor="mm")

    # 6. Guardar en memoria y enviar
    img_io = BytesIO()
    canvas.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png', as_attachment=True, download_name=f"placa_{name}.png")

if __name__ == '__main__':
    app.run(debug=True)
    
