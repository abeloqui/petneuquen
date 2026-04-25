import os
from flask import Flask, request, jsonify, send_from_directory
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader
from flask_mail import Mail, Message
from auth import verify_password  # Importante para que el login funcione

# 1. Configuración de Flask para Render (Sirve archivos desde /static)
app = Flask(__name__, static_folder='static', static_url_path='')

# 2. Configuración de CLOUDINARY (Usa tus variables de entorno de Render)
cloudinary.config(
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
  api_key = os.getenv("CLOUDINARY_API_KEY"),
  api_secret = os.getenv("CLOUDINARY_API_SECRET")
)

# 3. Configuración de SUPABASE
url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# 4. CONFIGURACIÓN DE CORREO
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

mail = Mail(app)

# --- MOTOR DE EMAILS ---
def enviar_mail(email_destino, tipo_evento, datos=None):
    temas = {
        "bienvenida": {
            "asunto": "¡Bienvenido a Huellitas NQN! 🐾",
            "cuerpo": "¡Hola! Gracias por sumarte. Tu cuenta está en revisión por seguridad."
        },
        "cuenta_aprobada": {
            "asunto": "¡Cuenta Activada! Ya podés ayudar 🐶",
            "cuerpo": "Tu cuenta en Huellitas NQN ha sido aprobada. Ya podés reportar mascotas."
        }
    }
    if tipo_evento in temas:
        msg = Message(temas[tipo_evento]["asunto"], recipients=[email_destino])
        msg.body = temas[tipo_evento]["cuerpo"]
        try:
            mail.send(msg)
        except Exception as e:
            print(f"Error enviando mail: {e}")

# --- RUTAS DE NAVEGACIÓN ---

@app.route('/')
def serve_index():
    # Sirve el index.html desde la carpeta static
    return send_from_directory(app.static_folder, 'index.html')

# --- RUTAS DE AUTENTICACIÓN (LOGIN) ---

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')

        # Buscamos en la tabla users de tu Supabase
        res = supabase.table("users").select("*").eq("email", email).execute()
        
        if not res.data:
            return jsonify({"error": "Usuario no encontrado"}), 401
        
        user_db = res.data[0]

        # Verificación de contraseña (usando verify_password de auth.py)
        if verify_password(password, user_db['hashed_password']):
            return jsonify({
                "id": user_db['id'],
                "email": user_db['email'],
                "role": user_db.get('role', 'user'),
                "is_verified": user_db.get('is_verified', False)
            })
        else:
            return jsonify({"error": "Credenciales incorrectas"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- RUTAS DE MASCOTAS ---

@app.route('/pets', methods=['GET'])
def get_pets():
    try:
        # Trae mascotas aprobadas y el teléfono del usuario que reportó
        res = supabase.table("pets").select("*, users(telefono)").eq("is_approved", True).execute()
        return jsonify(res.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    try:
        file = request.files.get('file')
        if not file:
            return jsonify({"error": "Falta la imagen"}), 400

        # Subida a Cloudinary
        upload_result = cloudinary.uploader.upload(file)
        img_url = upload_result.get('secure_url')

        # Procesar booleanos del FormData
        necesita_med = request.form.get('necesita_medicacion') == 'true'
        esta_herido = request.form.get('esta_herido') == 'true'

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
            "is_approved": False, # Requiere revisión de admin
            "necesita_medicacion": necesita_med,
            "esta_herido": esta_herido,
            "estado_resguardo": request.form.get('estado_resguardo', 'calle'),
            "referencia": request.form.get('referencia', '')
        }

        res = supabase.table("pets").insert(new_pet).execute()
        return jsonify(res.data)
    except Exception as e:
        print(f"Error upload: {e}")
        return jsonify({"error": str(e)}), 500

# --- RUTAS DE ADMINISTRACIÓN ---

@app.route('/admin/data', methods=['GET'])
def admin_data():
    try:
        u = supabase.table("users").select("*").eq("is_verified", False).execute()
        p = supabase.table("pets").select("*").execute()
        
        pets_all = p.data if p.data else []
        stats = {
            "perdidos": len([x for x in pets_all if x['status'] == 'perdido' and x['is_approved']]),
            "adopcion": len([x for x in pets_all if x['status'] == 'adopcion' and x['is_approved']]),
            "pendientes": len([x for x in pets_all if not x['is_approved']])
        }
        return jsonify({"users": u.data, "pets": pets_all, "stats": stats})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/approve/<t>/<id>', methods=['POST'])
def approve(t, id):
    try:
        table = "users" if t == 'u' else "pets"
        column = "is_verified" if t == 'u' else "is_approved"
        
        res = supabase.table(table).update({column: True}).eq("id", id).execute()
        
        # Si aprobamos un usuario, le avisamos por mail
        if t == 'u' and res.data:
            enviar_mail(res.data[0]['email'], "cuenta_aprobada")
            
        return jsonify({"msg": "Aprobación exitosa"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- ARRANQUE ---

if __name__ == '__main__':
    # Render usa la variable PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
        
