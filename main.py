import os
from flask import Flask, request, jsonify, send_from_directory
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader
from flask_mail import Mail, Message

# Indicamos que los archivos estáticos están en la carpeta raíz si es necesario
app = Flask(__name__, static_folder='static', static_url_path='/static')

# --- CONFIGURACIÓN DE CORREO ---
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
            "cuerpo": "¡Hola! Gracias por sumarte. Tu cuenta está en revisión por seguridad. Te avisaremos apenas sea aprobada."
        },
        "cuenta_aprobada": {
            "asunto": "¡Cuenta Activada! Ya podés ayudar 🐶",
            "cuerpo": "Tu cuenta en Huellitas NQN ha sido aprobada. Ya podés reportar mascotas."
        },
        "publicacion_exitosa": {
            "asunto": "Recibimos tu reporte 🐾",
            "cuerpo": f"¡Gracias! El reporte de {datos.get('nombre') if datos else 'la mascota'} está en revisión."
        }
    }
    evento = temas.get(tipo_evento)
    if not evento or not email_destino: return False
    msg = Message(evento["asunto"], recipients=[email_destino])
    msg.body = evento["cuerpo"]
    try:
        mail.send(msg)
        return True
    except: return False

# --- CONFIGURACIONES DE SERVICIOS ---
supabase: Client = create_client(os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_KEY", ""))
cloudinary.config( 
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"), 
  api_key = os.getenv("CLOUDINARY_API_KEY"), 
  api_secret = os.getenv("CLOUDINARY_API_SECRET"),
  secure = True
)

@app.route('/')
def index():
    # Buscamos el index.html dentro de /static
    return send_from_directory(app.static_folder, 'index.html')

# --- RUTAS DE USUARIOS ---
@app.route('/login', methods=['POST'])
def login():
    e, p = request.form.get('email'), request.form.get('password')
    if e == os.getenv("ADMIN_EMAIL") and p == os.getenv("ADMIN_PASS"):
        return jsonify({"id": "admin", "email": e, "role": "admin", "is_approved": True})
    try:
        res = supabase.table("users").select("*").eq("email", e).execute()
        if res.data:
            user = res.data[0]
            if user.get('password') == p:
                if user.get('is_approved'): return jsonify(user)
                return jsonify({"msg": "Cuenta pendiente de aprobación"}), 401
    except: pass
    return jsonify({"msg": "Credenciales inválidas"}), 401

@app.route('/register', methods=['POST'])
def register():
    try:
        d = request.form
        supabase.table("users").insert({
            "email": d['email'], "password": d['password'], 
            "telefono": d['telefono'], "is_approved": False
        }).execute()
        enviar_mail(d['email'], "bienvenida")
        return jsonify({"msg": "OK"}), 201
    except Exception as e: return jsonify({"msg": str(e)}), 500

# --- RUTAS DE MASCOTAS ---
@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    try:
        f, d = request.files.get('file'), request.form
        up = cloudinary.uploader.upload(f, folder="huellitas")
        supabase.table("pets").insert({
            "user_id": int(d['user_id']) if d['user_id'] != 'admin' else None, 
            "name": d['name'], "status": d['status'], "especie": d.get('especie', 'perro'),
            "barrio": d['barrio'], "latitud": float(d['latitud']), "longitud": float(d['longitud']), 
            "image_url": up['secure_url'], "is_approved": False
        }).execute()
        if d.get('user_email'):
            enviar_mail(d['user_email'], "publicacion_exitosa", {"nombre": d['name']})
        return jsonify({"msg": "OK"}), 201
    except Exception as e: return jsonify({"msg": str(e)}), 500

@app.route('/pets', methods=['GET'])
def get_pets():
    res = supabase.table("pets").select("*, users(telefono)").eq("is_approved", True).execute()
    return jsonify(res.data)

@app.route('/my-pets/<int:user_id>', methods=['GET'])
def get_user_pets(user_id):
    res = supabase.table("pets").select("*").eq("user_id", user_id).execute()
    return jsonify(res.data)

@app.route('/pets/delete/<int:pet_id>', methods=['DELETE'])
def delete_pet(pet_id):
    supabase.table("pets").delete().eq("id", pet_id).execute()
    return jsonify({"msg": "OK"})

# --- RUTAS DE ADMIN ---
@app.route('/admin/data', methods=['GET'])
def admin_data():
    u = supabase.table("users").select("*").eq("is_approved", False).execute()
    p = supabase.table("pets").select("*").execute()
    pets_all = p.data if p.data else []
    stats = {
        "perdidos": len([x for x in pets_all if x['status'] == 'perdido' and x['is_approved']]),
        "adopcion": len([x for x in pets_all if x['status'] == 'adopcion' and x['is_approved']]),
        "pendientes": len([x for x in pets_all if not x['is_approved']])
    }
    return jsonify({"users": u.data, "pets": pets_all, "stats": stats})

@app.route('/admin/approve/<t>/<id>', methods=['POST'])
def approve(t, id):
    supabase.table("users" if t == "user" else "pets").update({"is_approved": True}).eq("id", id).execute()
    if t == "user":
        res = supabase.table("users").select("email").eq("id", id).execute()
        if res.data: enviar_mail(res.data[0]['email'], "cuenta_aprobada")
    return jsonify({"msg": "OK"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
    
