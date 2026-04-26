import os
from flask import Flask, request, jsonify, send_from_directory
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader
from flask_mail import Mail, Message

# Configuración de Flask
app = Flask(__name__, static_folder='static', static_url_path='/static')
# Permitir archivos de hasta 16MB
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# --- CONFIGURACIÓN DE CORREO ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

mail = Mail(app)

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
    return send_from_directory(app.static_folder, 'index.html')

# RUTA PARA COMPARTIR: Evita el error 404
@app.route('/mascota/<int:pet_id>')
def pet_detail(pet_id):
    return send_from_directory(app.static_folder, 'index.html')

# --- RUTAS DE USUARIOS ---

@app.route('/login', methods=['POST'])
def login():
    e = request.form.get('email')
    p = request.form.get('password')
    if e == os.getenv("ADMIN_EMAIL") and p == os.getenv("ADMIN_PASS"):
        return jsonify({"id": "admin", "email": e, "role": "admin", "is_approved": True})
    try:
        res = supabase.table("users").select("*").eq("email", e).execute()
        if res.data:
            user = res.data[0]
            if user.get('password') == p:
                if user.get('is_approved'): return jsonify(user)
                return jsonify({"msg": "Cuenta pendiente de aprobación"}), 401
    except Exception as err:
        print(f"Error login: {err}")
    return jsonify({"msg": "Credenciales inválidas"}), 401

@app.route('/register', methods=['POST'])
def register():
    try:
        d = request.form
        supabase.table("users").insert({
            "email": d['email'], "password": d['password'], 
            "telefono": d['telefono'], "is_approved": False
        }).execute()
        return jsonify({"msg": "OK"}), 201
    except Exception as e: return jsonify({"msg": str(e)}), 500

# --- RUTAS DE MASCOTAS ---

@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    try:
        f = request.files.get('file')
        d = request.form
        up = cloudinary.uploader.upload(f, folder="huellitas", transformation=[{"quality": "auto", "fetch_format": "auto"}])
        
        u_id = d.get('user_id')
        # Validamos el ID de usuario para guardarlo correctamente
        user_id_val = int(u_id) if (u_id and u_id not in ['admin', 'undefined'] and u_id.isdigit()) else None

        supabase.table("pets").insert({
            "user_id": user_id_val, 
            "name": d['name'], "status": d['status'], 
            "especie": d.get('especie', 'perro'), "barrio": d['barrio'], 
            "latitud": float(d['latitud']), "longitud": float(d['longitud']), 
            "image_url": up['secure_url'], "is_approved": False,
            "necesita_medicacion": d.get('necesita_medicacion') == 'on',
            "esta_herido": d.get('esta_herido') == 'on',
            "estado_resguardo": d.get('estado_resguardo', 'calle'),
            "referencia": d.get('referencia', '')
        }).execute()
        return jsonify({"msg": "OK"}), 201
    except Exception as e: return jsonify({"msg": str(e)}), 500

@app.route('/pets', methods=['GET'])
def get_pets():
    # MODIFICACIÓN: Traemos TODAS las mascotas (aprobadas y no aprobadas)
    # El filtrado de qué se ve en el mapa se hace en el Frontend.
    # Esto permite que el usuario vea sus propias mascotas "Pendientes" en su panel.
    res = supabase.table("pets").select("*, users(telefono)").execute()
    return jsonify(res.data)

# --- RUTAS DE ADMIN (OMNIPOTENTE) ---

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
    table = "users" if t == "user" else "pets"
    supabase.table(table).update({"is_approved": True}).eq("id", id).execute()
    return jsonify({"msg": "OK"})

@app.route('/admin/delete-pet/<int:pet_id>', methods=['DELETE'])
def admin_delete_pet(pet_id):
    try:
        supabase.table("pets").delete().eq("id", pet_id).execute()
        return jsonify({"msg": "Eliminado"}), 200
    except Exception as e: return jsonify({"msg": str(e)}), 500

@app.route('/admin/delete-user/<int:user_id>', methods=['DELETE'])
def admin_delete_user(user_id):
    try:
        supabase.table("users").delete().eq("id", user_id).execute()
        return jsonify({"msg": "Usuario eliminado"}), 200
    except Exception as e: return jsonify({"msg": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
              
