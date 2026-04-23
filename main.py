import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify, send_from_directory
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader

app = Flask(__name__)

# --- CONFIGURACIONES ---
try:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    supabase: Client = create_client(url, key)

    cloudinary.config( 
      cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"), 
      api_key = os.getenv("CLOUDINARY_API_KEY"), 
      api_secret = os.getenv("CLOUDINARY_API_SECRET"),
      secure = True
    )

    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
except Exception as e:
    print(f"Error config: {e}")

# --- FUNCIÓN DE EMAIL ROBUSTA ---
def enviar_bienvenida(destinatario):
    if not MAIL_USERNAME or not MAIL_PASSWORD: return False
    try:
        msg = MIMEMultipart()
        msg['From'] = f"Huellitas NQN <{MAIL_USERNAME}>"
        msg['To'] = destinatario
        msg['Subject'] = "¡Bienvenido a Huellitas NQN! 🐾"
        html = f"""
        <div style="font-family: sans-serif; border: 1px solid #eee; padding: 20px; border-radius: 10px;">
            <h2 style="color: #f97316;">¡Hola! Gracias por sumarte.</h2>
            <p>Recibimos tu solicitud. Un administrador te habilitará pronto para que puedas publicar.</p>
            <p><b>Equipo Huellitas NQN</b></p>
        </div>
        """
        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.send_raw_message(msg)
        return True
    except Exception as e:
        print(f"Error mail: {e}")
        return False

# --- RUTAS ---
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.form
    e, p = data.get('email'), data.get('password')
    if e == "admin@huellitas.com" and p == "admin123":
        return jsonify({"id": "admin", "email": e, "role": "admin", "is_approved": True})
    try:
        res = supabase.table("users").select("*").eq("email", e).eq("password", p).eq("is_approved", True).execute()
        if res.data: return jsonify(res.data[0])
    except: pass
    return jsonify({"msg": "Pendiente de aprobación"}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.form
    try:
        email = data['email']
        supabase.table("users").insert({
            "email": email, "password": data['password'], 
            "telefono": data['telefono'], "role": "user", "is_approved": False
        }).execute()
        enviar_bienvenida(email)
        return jsonify({"msg": "Solicitud enviada exitosamente"}), 201
    except: return jsonify({"msg": "Error en registro"}), 400

@app.route('/pets', methods=['GET'])
def get_pets():
    try:
        # Traemos mascotas y el teléfono del dueño (si existe)
        res = supabase.table("pets").select("*, users(telefono)").eq("is_approved", True).execute()
        pets = []
        for p in res.data:
            # Si no hay usuario vinculado, usamos el tuyo por defecto para que no falle el link de WA
            tel = p.get('users', {}).get('telefono') if p.get('users') else "2996894360"
            p['telefono_contacto'] = tel
            pets.append(p)
        return jsonify(pets)
    except: return jsonify([])

@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    f = request.files.get('file')
    if not f: return jsonify({"msg": "Falta imagen"}), 400
    try:
        up = cloudinary.uploader.upload(f, folder="huellitas")
        d = request.form
        supabase.table("pets").insert({
            "user_id": d['user_id'], "name": d['name'], "status": d['status'],
            "barrio": d['barrio'], "latitud": float(d['latitud']),
            "longitud": float(d['longitud']), "image_url": up['secure_url'], "is_approved": False
        }).execute()
        return jsonify({"msg": "OK"}), 201
    except Exception as e: return jsonify({"msg": str(e)}), 500

@app.route('/admin/data', methods=['GET'])
def admin_data():
    u = supabase.table("users").select("*").eq("is_approved", False).execute()
    p = supabase.table("pets").select("*").execute()
    return jsonify({"users": u.data, "pets": p.data})

@app.route('/admin/approve/<t>/<id>', methods=['POST'])
def approve(t, id):
    table = "users" if t == "user" else "pets"
    supabase.table(table).update({"is_approved": True}).eq("id", id).execute()
    return jsonify({"msg": "OK"})

@app.route('/admin/delete/pet/<id>', methods=['DELETE'])
def delete_pet(id):
    try:
        res = supabase.table("pets").select("image_url").eq("id", id).execute()
        if res.data:
            public_id = "huellitas/" + res.data[0]['image_url'].split('/')[-1].split('.')[0]
            cloudinary.uploader.destroy(public_id)
        supabase.table("pets").delete().eq("id", id).execute()
        return jsonify({"msg": "OK"})
    except: return jsonify({"msg": "Error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
    
