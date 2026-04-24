import os
from flask import Flask, request, jsonify, send_from_directory
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader
from flask_mail import Mail, Message

app = Flask(__name__)

# --- CONFIGURACIÓN DE CORREO ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("Mail_Username") or os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("Mail_Password") or os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

mail = Mail(app)

# --- CONFIGURACIÓN SERVICIOS EXTERNOS ---
url = os.getenv("SUPABASE_URL", "").strip()
key = os.getenv("SUPABASE_KEY", "").strip()
supabase: Client = create_client(url, key)

cloudinary.config( 
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"), 
  api_key = os.getenv("CLOUDINARY_API_KEY"), 
  api_secret = os.getenv("CLOUDINARY_API_SECRET"),
  secure = True
)

# --- FUNCIONES AUXILIARES ---
def enviar_mail(email_destino, tipo_evento, datos=None):
    temas = {
        "bienvenida": {"asunto": "¡Bienvenido a Huellitas NQN! 🐾", "cuerpo": "Gracias por sumarte. Tu cuenta está en revisión."},
        "cuenta_aprobada": {"asunto": "¡Cuenta Activada! 🐶", "cuerpo": "Ya podés publicar reportes en la plataforma."},
        "publicacion_exitosa": {"asunto": "Reporte Recibido", "cuerpo": f"El reporte de {datos.get('nombre') if datos else 'la mascota'} está en revisión."}
    }
    ev = temas.get(tipo_evento)
    if not ev or not email_destino: return
    try:
        msg = Message(ev["asunto"], recipients=[email_destino])
        msg.body = ev["cuerpo"]
        mail.send(msg)
    except Exception as e: print(f"Error mail: {e}")

def eliminar_foto_cloudinary(url_imagen):
    try:
        if "cloudinary" in url_imagen:
            public_id = f"huellitas/{url_imagen.split('/')[-1].split('.')[0]}"
            cloudinary.uploader.destroy(public_id)
    except Exception as e: print(f"Error Cloudinary: {e}")

# --- RUTAS DE APLICACIÓN ---
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.form
    e, p = data.get('email'), data.get('password')
    if e == os.getenv("ADMIN_EMAIL") and p == os.getenv("ADMIN_PASS"):
        return jsonify({"id": "admin", "email": e, "role": "admin", "is_approved": True})
    try:
        res = supabase.table("users").select("*").eq("email", e).execute()
        if res.data:
            u = res.data[0]
            if not u.get('is_approved'): return jsonify({"msg": "Cuenta pendiente"}), 401
            if u.get('password') == p: return jsonify(u)
    except: pass
    return jsonify({"msg": "Credenciales inválidas"}), 401

@app.route('/register', methods=['POST'])
def register():
    d = request.form
    try:
        supabase.table("users").insert({"email": d['email'], "password": d['password'], "telefono": d['telefono'], "is_approved": False}).execute()
        enviar_mail(d['email'], "bienvenida")
        return jsonify({"msg": "OK"}), 201
    except: return jsonify({"msg": "Error"}), 400

@app.route('/pets/upload', methods=['POST'])
def upload():
    try:
        f, d = request.files.get('file'), request.form
        up = cloudinary.uploader.upload(f, folder="huellitas")
        supabase.table("pets").insert({
            "user_id": d['user_id'], "name": d['name'], "status": d['status'],
            "especie": d.get('especie', 'perro'), "barrio": d['barrio'],
            "latitud": float(d['latitud']), "longitud": float(d['longitud']),
            "image_url": up['secure_url'], "is_approved": False
        }).execute()
        return jsonify({"msg": "OK"}), 201
    except Exception as e: return jsonify({"msg": str(e)}), 500

@app.route('/pets', methods=['GET'])
def get_pets():
    res = supabase.table("pets").select("*, users(telefono)").eq("is_approved", True).execute()
    return jsonify(res.data)

@app.route('/my-pets/<int:user_id>', methods=['GET'])
def my_pets(user_id):
    res = supabase.table("pets").select("*").eq("user_id", user_id).execute()
    return jsonify(res.data)

# --- RUTAS ADMIN ---
@app.route('/admin/data', methods=['GET'])
def admin_data():
    u = supabase.table("users").select("*").order("id", desc=True).execute()
    p = supabase.table("pets").select("*").order("id", desc=True).execute()
    return jsonify({"users": u.data, "pets": p.data})

@app.route('/admin/approve/<t>/<id>', methods=['POST'])
def approve(t, id):
    table = "users" if t == "user" else "pets"
    supabase.table(table).update({"is_approved": True}).eq("id", id).execute()
    if t == "user":
        u = supabase.table("users").select("email").eq("id", id).execute()
        if u.data: enviar_mail(u.data[0]['email'], "cuenta_aprobada")
    return jsonify({"msg": "OK"})

@app.route('/admin/delete/<t>/<id>', methods=['DELETE'])
def admin_delete(t, id):
    if t == "pet":
        res = supabase.table("pets").select("image_url").eq("id", id).execute()
        if res.data: eliminar_foto_cloudinary(res.data[0]['image_url'])
    supabase.table("users" if t == "user" else "pets").delete().eq("id", id).execute()
    return jsonify({"msg": "OK"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
    
