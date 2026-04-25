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

# --- CONFIGURACIONES DE SERVICIOS ---
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

@app.route('/mascota/<int:pet_id>')
def pet_detail(pet_id):
    try:
        res = supabase.table("pets").select("*").eq("id", pet_id).execute()
        if not res.data: return "No encontrado", 404
        p = res.data[0]
        return f"""
        <html>
        <head>
            <meta property="og:title" content="🐾 {p['name']} busca ayuda en {p['barrio']}" />
            <meta property="og:image" content="{p['image_url']}" />
            <meta property="og:description" content="Estado: {p['status'].upper()}. Mirá la ubicación en Huellitas NQN." />
            <script>setTimeout(function() {{ window.location.href = "/"; }}, 1500);</script>
        </head>
        <body style="font-family:sans-serif; text-align:center; padding:50px;">
            <h2>Localizando a {p['name']}...</h2>
        </body>
        </html>
        """
    except: return "Error", 500

@app.route('/login', methods=['POST'])
def login():
    e, p = request.form.get('email'), request.form.get('password')
    # Admin bypass
    if e == os.getenv("ADMIN_EMAIL") and p == os.getenv("ADMIN_PASS"):
        return jsonify({"id": "admin", "email": e, "role": "admin", "is_approved": True})
    
    res = supabase.table("users").select("*").eq("email", e).execute()
    if res.data and res.data[0]['password'] == p:
        if res.data[0]['is_approved']: return jsonify(res.data[0])
        return jsonify({"msg": "Pendiente de aprobación"}), 401
    return jsonify({"msg": "Credenciales inválidas"}), 401

@app.route('/register', methods=['POST'])
def register():
    d = request.form
    try:
        supabase.table("users").insert({
            "email": d['email'], 
            "password": d['password'], 
            "telefono": d['telefono'], 
            "is_approved": False
        }).execute()
        return jsonify({"msg": "OK"}), 201
    except: return jsonify({"msg": "Error al registrar"}), 400

@app.route('/pets', methods=['GET'])
def get_pets():
    res = supabase.table("pets").select("*, users(telefono)").eq("is_approved", True).execute()
    return jsonify(res.data)

@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    f, d = request.files.get('file'), request.form
    up = cloudinary.uploader.upload(f, folder="huellitas")
    supabase.table("pets").insert({
        "user_id": int(d['user_id']), "name": d['name'], "status": d['status'],
        "especie": d.get('especie', 'perro'), "barrio": d['barrio'], 
        "latitud": float(d['latitud']), "longitud": float(d['longitud']), 
        "image_url": up['secure_url'], "is_approved": False
    }).execute()
    return jsonify({"msg": "OK"}), 201

@app.route('/admin/data', methods=['GET'])
def admin_data():
    u = supabase.table("users").select("*").eq("is_approved", False).execute()
    p = supabase.table("pets").select("*").execute()
    pets = p.data or []
    stats = {
        "perdidos": len([x for x in pets if x['status'] == 'perdido' and x['is_approved']]),
        "adopcion": len([x for x in pets if x['status'] == 'adopcion' and x['is_approved']]),
        "pendientes": len([x for x in pets if not x['is_approved']])
    }
    return jsonify({"users": u.data, "pets": pets, "stats": stats})

@app.route('/admin/approve/<t>/<id>', methods=['POST'])
def approve(t, id):
    table = "users" if t == "user" else "pets"
    supabase.table(table).update({"is_approved": True}).eq("id", id).execute()
    return jsonify({"msg": "OK"})

@app.route('/my-pets/<int:user_id>', methods=['GET'])
def my_pets(user_id):
    res = supabase.table("pets").select("*").eq("user_id", user_id).execute()
    return jsonify(res.data)

@app.route('/pets/user-delete/<int:pet_id>', methods=['DELETE'])
def user_delete(pet_id):
    supabase.table("pets").delete().eq("id", pet_id).execute()
    return jsonify({"msg": "OK"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
      
