import os
from flask import Flask, request, jsonify, send_from_directory
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader
from werkzeug.security import generate_password_hash, check_password_hash

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
except Exception as e:
    print(f"Error de configuración inicial: {e}")

# --- RUTAS ---
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.form
    e, p = data.get('email'), data.get('password')
    
    # Credenciales de Admin (Idealmente en variables de entorno)
    admin_email = os.getenv("ADMIN_EMAIL", "admin@huellitas.com")
    admin_pass = os.getenv("ADMIN_PASS", "admin123")

    if e == admin_email and p == admin_pass:
        return jsonify({"id": "admin", "email": e, "role": "admin", "is_approved": True})
    
    try:
        res = supabase.table("users").select("*").eq("email", e).execute()
        if res.data:
            user = res.data[0]
            # Verificamos hash si usas generate_password_hash, o comparación directa por ahora
            if user.get('password') == p and str(user.get('is_approved')).lower() == 'true':
                return jsonify(user)
    except Exception as e:
        print(f"Error login: {e}")
    
    return jsonify({"msg": "No autorizado o pendiente de aprobación"}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.form
    try:
        # Aquí podrías usar generate_password_hash(data['password']) para más seguridad
        supabase.table("users").insert({
            "email": data['email'], 
            "password": data['password'], 
            "telefono": data['telefono'], 
            "role": "user", 
            "is_approved": False
        }).execute()
        return jsonify({"msg": "Registro enviado. Un admin deberá aprobarte."}), 201
    except Exception as e:
        print(f"Error registro: {e}")
        return jsonify({"msg": "Error en el registro"}), 400

@app.route('/pets', methods=['GET'])
def get_pets():
    try:
        # Filtramos directamente en Supabase para traer solo lo aprobado
        res = supabase.table("pets")\
            .select("*, users(telefono)")\
            .eq("is_approved", True)\
            .execute()
            
        for p in res.data:
            # Limpiamos el teléfono para WhatsApp (solo números)
            raw_tel = p.get('users', {}).get('telefono') if p.get('users') else "2996894360"
            p['tel_final'] = "".join(filter(str.isdigit, str(raw_tel)))
            
        return jsonify(res.data)
    except Exception as e:
        print(f"Error pets: {e}")
        return jsonify([])

# ... Resto de rutas (upload, admin_data, approve, delete) se mantienen igual ...

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
    
