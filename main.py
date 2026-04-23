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
    print(f"Error inicial: {e}")

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
        res = supabase.table("users").select("*").eq("email", e).eq("password", p).execute()
        if res.data and str(res.data[0].get('is_approved')).lower() == 'true':
            return jsonify(res.data[0])
    except: pass
    return jsonify({"msg": "No autorizado"}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.form
    try:
        supabase.table("users").insert({
            "email": data['email'], "password": data['password'], 
            "telefono": data['telefono'], "role": "user", "is_approved": False
        }).execute()
        return jsonify({"msg": "Registro enviado"}), 201
    except: return jsonify({"msg": "Error"}), 400

@app.route('/pets', methods=['GET'])
def get_pets():
    try:
        # Traemos todas las mascotas y manejamos la aprobación manualmente para evitar errores de tipo
        res = supabase.table("pets").select("*, users(telefono)").execute()
        aprobadas = []
        for p in res.data:
            is_ok = str(p.get('is_approved')).lower() == 'true'
            if is_ok:
                # Si no hay teléfono de usuario, usamos el tuyo por defecto
                p['tel_final'] = p.get('users', {}).get('telefono') if p.get('users') else "2996894360"
                aprobadas.append(p)
        return jsonify(aprobadas)
    except Exception as e:
        print(f"Error pets: {e}")
        return jsonify([])

@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    try:
        f = request.files.get('file')
        up = cloudinary.uploader.upload(f, folder="huellitas")
        d = request.form
        supabase.table("pets").insert({
            "user_id": d['user_id'], "name": d['name'], "status": d['status'],
            "barrio": d['barrio'], "latitud": float(d['latitud']),
            "longitud": float(d['longitud']), "image_url": up['secure_url'], "is_approved": False
        }).execute()
        return jsonify({"msg": "OK"}), 201
    except: return jsonify({"msg": "Error"}), 500

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
    supabase.table("pets").delete().eq("id", id).execute()
    return jsonify({"msg": "OK"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
    
