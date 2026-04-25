import os
from flask import Flask, request, jsonify, send_from_directory
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader
from flask_mail import Mail, Message
from auth import verify_password 

app = Flask(__name__, static_folder='static', static_url_path='')

# --- CONFIGURACIÓN DE CLOUDINARY ---
cloudinary.config(
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
  api_key = os.getenv("CLOUDINARY_API_KEY"),
  api_secret = os.getenv("CLOUDINARY_API_SECRET")
)

# --- CONFIGURACIÓN DE SUPABASE ---
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# --- CONFIGURACIÓN DE CORREO ---
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
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')

        # 1. VALIDACIÓN DE ADMIN (Desde variables de Render)
        admin_email = os.getenv("ADMIN_EMAIL") # Asegurate de tener esta variable en Render
        admin_pass = os.getenv("ADMIN_PASSWORD") # Asegurate de tener esta variable en Render

        if email == admin_email and password == admin_pass:
            return jsonify({
                "id": "admin_root",
                "email": admin_email,
                "role": "admin",
                "is_verified": True
            })

        # 2. VALIDACIÓN DE USUARIOS NORMALES (Desde Supabase)
        res = supabase.table("users").select("*").eq("email", email).execute()
        
        if res.data:
            user_db = res.data[0]
            if verify_password(password, user_db['hashed_password']):
                return jsonify({
                    "id": user_db['id'],
                    "email": user_db['email'],
                    "role": user_db.get('role', 'user'),
                    "is_verified": user_db.get('is_verified', False)
                })

        return jsonify({"error": "Credenciales incorrectas"}), 401
        
    except Exception as e:
        print(f"Error Login: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500

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
        if not file: return jsonify({"error": "No image"}), 400

        upload_result = cloudinary.uploader.upload(file)
        img_url = upload_result.get('secure_url')

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
        return jsonify({"error": str(e)}), 500

@app.route('/admin/data', methods=['GET'])
def admin_data():
    u = supabase.table("users").select("*").eq("is_verified", False).execute()
    p = supabase.table("pets").select("*").execute()
    return jsonify({"users": u.data, "pets": p.data})

@app.route('/admin/approve/<t>/<id>', methods=['POST'])
def approve(t, id):
    table = "users" if t == 'u' else "pets"
    column = "is_verified" if t == 'u' else "is_approved"
    res = supabase.table(table).update({column: True}).eq("id", id).execute()
    return jsonify({"msg": "OK"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
  
