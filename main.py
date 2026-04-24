import os
import sqlite3
from flask import Flask, request, jsonify, send_from_directory
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader
from flask_mail import Mail, Message

app = Flask(__name__, static_folder='static')

# --- CONFIGURACIÓN DE CORREO ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_USERNAME")

mail = Mail(app)

# --- CONFIGURACIONES DE SERVICIOS (Supabase & Cloudinary) ---
url = os.getenv("SUPABASE_URL", "").strip()
key = os.getenv("SUPABASE_KEY", "").strip()
supabase: Client = create_client(url, key)

cloudinary.config( 
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"), 
  api_key = os.getenv("CLOUDINARY_API_KEY"), 
  api_secret = os.getenv("CLOUDINARY_API_SECRET"),
  secure = True
)

# --- MOTOR DE NOTIFICACIONES POR EMAIL ---
def enviar_mail(email_destino, tipo_evento, datos=None):
    temas = {
        "bienvenida": {
            "asunto": "¡Bienvenido a Huellitas NQN! 🐾",
            "cuerpo": "¡Hola! Gracias por sumarte. Tu cuenta está en revisión. Te avisaremos cuando puedas publicar."
        },
        "cuenta_aprobada": {
            "asunto": "¡Cuenta Activada! Ya podés ayudar 🐶",
            "cuerpo": "Tu cuenta en Huellitas NQN ha sido aprobada. Ya podés reportar mascotas."
        },
        "publicacion_exitosa": {
            "asunto": f"Recibimos el reporte de {datos.get('nombre') if datos else 'tu mascota'}",
            "cuerpo": "¡Gracias! El reporte está en revisión y pronto aparecerá en el mapa de Neuquén."
        },
        "mascota_aprobada": {
            "asunto": "¡Tu reporte ya está online! 🚀",
            "cuerpo": f"La publicación de {datos.get('nombre') if datos else 'la mascota'} ha sido aprobada y ya se ve en el mapa."
        }
    }
    evento = temas.get(tipo_evento)
    if not evento or not email_destino: return False

    msg = Message(evento["asunto"], recipients=[email_destino])
    msg.body = evento["cuerpo"]
    try:
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Error envío mail: {e}")
        return False

# --- RUTAS DE NAVEGACIÓN Y AUTH ---
@app.route('/')
def index():
    return send_from_directory('templates', 'index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.form
    e, p = data.get('email'), data.get('password')
    admin_email = os.getenv("ADMIN_EMAIL", "admin@huellitas.com")
    admin_pass = os.getenv("ADMIN_PASS", "admin123")
    
    if e == admin_email and p == admin_pass:
        return jsonify({"id": "admin", "email": e, "role": "admin", "is_approved": True})
    
    try:
        res = supabase.table("users").select("*").eq("email", e).execute()
        if res.data:
            user = res.data[0]
            if str(user.get('is_approved')).lower() == 'true':
                if user.get('password') == p: return jsonify(user)
                return jsonify({"msg": "Clave incorrecta"}), 401
            return jsonify({"msg": "Cuenta pendiente de aprobación"}), 403
    except Exception as err: print(f"Error login: {err}")
    return jsonify({"msg": "Usuario no encontrado"}), 401

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.form
        email, password, tel = data.get('email'), data.get('password'), data.get('telefono')
        supabase.table("users").insert({"email": email, "password": password, "telefono": tel, "is_approved": False}).execute()
        enviar_mail(email, "bienvenida")
        return jsonify({"msg": "OK"}), 201
    except: return jsonify({"msg": "Error"}), 500

# --- RUTAS DE MASCOTAS ---
@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    try:
        f, d = request.files.get('file'), request.form
        user_id = d.get('user_id')
        up = cloudinary.uploader.upload(f, folder="huellitas")
        supabase.table("pets").insert({
            "user_id": int(user_id), "name": d['name'], "status": d['status'],
            "especie": d.get('especie', 'perro'), "barrio": d['barrio'], 
            "latitud": float(d['latitud']), "longitud": float(d['longitud']), 
            "image_url": up['secure_url'], "is_approved": False
        }).execute()
        
        res_user = supabase.table("users").select("email").eq("id", user_id).execute()
        if res_user.data: 
            enviar_mail(res_user.data[0]['email'], "publicacion_exitosa", {"nombre": d['name']})
        return jsonify({"msg": "OK"}), 201
    except: return jsonify({"msg": "Error"}), 500

@app.route('/pets', methods=['GET'])
def get_pets():
    res = supabase.table("pets").select("*, users(telefono)").eq("is_approved", True).execute()
    return jsonify(res.data)

# --- RUTAS ADMINISTRADOR (SUPERUSUARIO) ---
@app.route('/admin/data', methods=['GET'])
def admin_data():
    # Solo para el Superusuario André
    u = supabase.table("users").select("*").eq("is_approved", False).execute()
    p = supabase.table("pets").select("*").order("is_approved").execute()
    return jsonify({"users": u.data, "pets": p.data})

@app.route('/admin/approve/<t>/<id>', methods=['POST'])
def approve(t, id):
    table = "users" if t == "user" else "pets"
    supabase.table(table).update({"is_approved": True}).eq("id", id).execute()
    
    # Notificar aprobación por mail
    if t == "user":
        res = supabase.table("users").select("email").eq("id", id).execute()
        if res.data: enviar_mail(res.data[0]['email'], "cuenta_aprobada")
    else:
        res = supabase.table("pets").select("name, users(email)").eq("id", id).execute()
        if res.data: enviar_mail(res.data[0]['users']['email'], "mascota_aprobada", {"nombre": res.data[0]['name']})
            
    return jsonify({"msg": "OK"})

@app.route('/admin/delete/<t>/<id>', methods=['DELETE'])
def admin_delete(t, id):
    table = "users" if t == "user" else "pets"
    supabase.table(table).delete().eq("id", id).execute()
    return jsonify({"msg": "OK"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
        
