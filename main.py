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
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

mail = Mail(app)

# --- MOTOR DE EMAILS ---
def enviar_mail(email_destino, tipo_evento, datos=None):
    temas = {
        "bienvenida": {
            "asunto": "¡Bienvenido a Huellitas NQN! 🐾",
            "cuerpo": "¡Hola! Gracias por sumarte. Tu cuenta está en revisión. Te avisaremos cuando sea aprobada."
        },
        "cuenta_aprobada": {
            "asunto": "¡Cuenta Activada! Ya podés ayudar 🐶",
            "cuerpo": "Tu cuenta en Huellitas NQN ha sido aprobada. Ya podés reportar mascotas."
        },
        "publicacion_exitosa": {
            "asunto": "Recibimos tu reporte 🐾",
            "cuerpo": f"¡Gracias! El reporte de {datos.get('nombre') if datos else 'la mascota'} está en revisión por el admin."
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

# --- CONFIGURACIONES ---
url = os.getenv("SUPABASE_URL", "").strip()
key = os.getenv("SUPABASE_KEY", "").strip()
supabase: Client = create_client(url, key)

cloudinary.config( 
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"), 
  api_key = os.getenv("CLOUDINARY_API_KEY"), 
  api_secret = os.getenv("CLOUDINARY_API_SECRET"),
  secure = True
)

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

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
            return jsonify({"msg": "Cuenta pendiente de aprobación"}), 401
    except: pass
    return jsonify({"msg": "Usuario no encontrado"}), 401

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.form
        email, password, tel = data.get('email'), data.get('password'), data.get('telefono')
        supabase.table("users").insert({"email": email, "password": password, "telefono": tel, "is_approved": False}).execute()
        enviar_mail(email, "bienvenida")
        return jsonify({"msg": "OK"}), 201
    except Exception as e: return jsonify({"msg": str(e)}), 500

@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    try:
        f = request.files.get('file')
        d = request.form
        user_id = d.get('user_id')
        user_email = d.get('user_email')
        up = cloudinary.uploader.upload(f, folder="huellitas")
        
        supabase.table("pets").insert({
            "user_id": int(user_id) if (user_id and user_id != 'admin') else None, 
            "name": d['name'], "status": d['status'],
            "especie": d.get('especie', 'perro'), "barrio": d['barrio'], 
            "latitud": float(d['latitud']), "longitud": float(d['longitud']), 
            "image_url": up['secure_url'], "is_approved": False
        }).execute()
        
        if user_email:
            enviar_mail(user_email, "publicacion_exitosa", {"nombre": d['name']})
        return jsonify({"msg": "OK"}), 201
    except Exception as e: return jsonify({"msg": str(e)}), 500

@app.route('/pets', methods=['GET'])
def get_pets():
    # Crucial: Traemos los datos de la mascota Y el teléfono del usuario que la subió
    res = supabase.table("pets").select("*, users(telefono)").eq("is_approved", True).execute()
    return jsonify(res.data)

@app.route('/admin/data', methods=['GET'])
def admin_data():
    u = supabase.table("users").select("*").eq("is_approved", False).execute()
    p = supabase.table("pets").select("*").execute()
    pets_all = p.data or []
    stats = {
        "perdidos": len([x for x in pets_all if x.get('status') == 'perdido' and x.get('is_approved')]),
        "adopcion": len([x for x in pets_all if x.get('status') == 'adopcion' and x.get('is_approved')]),
        "pendientes": len([x for x in pets_all if not x.get('is_approved')])
    }
    return jsonify({"users": u.data, "pets": pets_all, "stats": stats})

@app.route('/admin/approve/<t>/<id>', methods=['POST'])
def approve(t, id):
    table = "users" if t == "user" else "pets"
    supabase.table(table).update({"is_approved": True}).eq("id", id).execute()
    if t == "user":
        res = supabase.table("users").select("email").eq("id", id).execute()
        if res.data: enviar_mail(res.data[0]['email'], "cuenta_aprobada")
    return jsonify({"msg": "OK"})

@app.route('/admin/delete-pet/<int:pet_id>', methods=['DELETE'])
def admin_delete_pet(pet_id):
    supabase.table("pets").delete().eq("id", pet_id).execute()
    return jsonify({"msg": "OK"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
                     
