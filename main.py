import os
from flask import Flask, request, jsonify, send_from_directory
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader
from flask_mail import Mail, Message

# Configuración de carpetas para Render
app = Flask(__name__, static_folder='static', static_url_path='/static')

# --- CONFIGURACIÓN DE CLOUDINARY (Variables de Render) ---
cloudinary.config(
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
  api_key = os.getenv("CLOUDINARY_API_KEY"),
  api_secret = os.getenv("CLOUDINARY_API_SECRET")
)

# --- CONFIGURACIÓN DE SUPABASE (Variables de Render) ---
url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# --- CONFIGURACIÓN DE CORREO (Variables de Render) ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

mail = Mail(app)

# --- RUTAS ---

@app.route('/')
def serve_index():
    # Buscamos el index dentro de tu carpeta 'static'
    return send_from_directory('static', 'index.html')

@app.route('/pets', methods=['GET'])
def get_pets():
    try:
        res = supabase.table("pets").select("*, users(telefono)").eq("is_approved", True).execute()
        return jsonify(res.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    try:
        file = request.files.get('file')
        if not file:
            return jsonify({"error": "No hay imagen"}), 400

        # Subida a Cloudinary
        upload_result = cloudinary.uploader.upload(file)
        img_url = upload_result.get('secure_url')

        # Procesar datos del formulario
        new_pet = {
            "name": request.form.get('name'),
            "especie": request.form.get('especie'),
            "status": request.form.get('status'),
            "barrio": request.form.get('barrio'),
            "latitud": float(request.form.get('latitud')),
            "longitud": float(request.form.get('longitud')),
            "image_url": img_url,
            "user_id": request.form.get('user_id'),
            "user_email": request.form.get('user_email'),
            "is_approved": False,
            "necesita_medicacion": request.form.get('necesita_medicacion') == 'true',
            "esta_herido": request.form.get('esta_herido') == 'true',
            "estado_resguardo": request.form.get('estado_resguardo', 'calle'),
            "referencia": request.form.get('referencia', '')
        }

        res = supabase.table("pets").insert(new_pet).execute()
        return jsonify(res.data)
    except Exception as e:
        print(f"Error en el servidor: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/admin/approve/<t>/<id>', methods=['POST'])
def approve(t, id):
    table = "users" if t == 'u' else "pets"
    column = "is_verified" if t == 'u' else "is_approved"
    res = supabase.table(table).update({column: True}).eq("id", id).execute()
    return jsonify({"msg": "OK"})

if __name__ == '__main__':
    # Usamos el puerto que asigne Render o el 5000 por defecto
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
