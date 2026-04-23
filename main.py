import os
from flask import Flask, request, jsonify, send_from_directory
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader

app = Flask(__name__)

# Configuración de Clientes (Usando las variables que pusiste en Render)
try:
    url: str = os.getenv("SUPABASE_URL")
    key: str = os.getenv("SUPABASE_KEY")
    supabase: Client = create_client(url, key)

    cloudinary.config( 
      cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"), 
      api_key = os.getenv("CLOUDINARY_API_KEY"), 
      api_secret = os.getenv("CLOUDINARY_API_SECRET"),
      secure = True
    )
except Exception as e:
    print(f"Error configurando servicios: {e}")

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# --- LOGIN CON HARDCODE Y SUPABASE ---
@app.route('/login', methods=['POST'])
def login():
    data = request.form
    email = data.get('email')
    password = data.get('password')
    
    # 1. Intento de entrada por Hardcode (Tu llave maestra)
    if email == "admin@huellitas.com" and password == "admin123":
        return jsonify({"id": 0, "email": email, "role": "admin", "is_approved": True})

    # 2. Intento por Base de Datos
    try:
        res = supabase.table("users").select("*").eq("email", email).eq("password", password).eq("is_approved", True).execute()
        if res.data:
            return jsonify(res.data[0])
    except Exception as e:
        print(f"Error Login DB: {e}")
    
    return jsonify({"msg": "Credenciales inválidas o cuenta pendiente"}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.form
    try:
        supabase.table("users").insert({
            "email": data['email'], 
            "password": data['password'], 
            "telefono": data['telefono'],
            "is_approved": False
        }).execute()
        return jsonify({"msg": "Solicitud enviada"}), 201
    except:
        return jsonify({"msg": "Error al registrar"}), 400

@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    file = request.files.get('file')
    if not file: return jsonify({"msg": "Falta imagen"}), 400
    
    try:
        # Subida a Cloudinary
        up = cloudinary.uploader.upload(file, folder="huellitas_nqn")
        data = request.form
        # Guardado en Supabase
        supabase.table("pets").insert({
            "user_id": data['user_id'],
            "name": data['name'],
            "status": data['status'],
            "barrio": data['barrio'],
            "latitud": float(data['latitud']),
            "longitud": float(data['longitud']),
            "image_url": up['secure_url'],
            "is_approved": False
        }).execute()
        return jsonify({"msg": "OK"}), 201
    except Exception as e:
        return jsonify({"msg": str(e)}), 500

@app.route('/pets', methods=['GET'])
def get_pets():
    all_pets = request.args.get('all_pets')
    try:
        query = supabase.table("pets").select("*, users(telefono)")
        if not all_pets:
            query = query.eq("is_approved", True)
        res = query.execute()
        
        # Formatear respuesta para el mapa
        pets = []
        for p in res.data:
            p['telefono'] = p['users']['telefono'] if p.get('users') else "Sin número"
            pets.append(p)
        return jsonify(pets)
    except:
        return jsonify([])

# --- RUTAS DE ADMINISTRACIÓN ---
@app.route('/admin/users/pending', methods=['GET'])
def pending_users():
    res = supabase.table("users").select("*").eq("is_approved", False).execute()
    return jsonify(res.data)

@app.route('/admin/users/approve/<id>', methods=['POST'])
def approve_user(id):
    supabase.table("users").update({"is_approved": True}).eq("id", id).execute()
    return jsonify({"msg": "OK"})

@app.route('/pets/approve/<id>', methods=['POST'])
def approve_pet(id):
    supabase.table("pets").update({"is_approved": True}).eq("id", id).execute()
    return jsonify({"msg": "OK"})

@app.route('/admin/pets/delete/<id>', methods=['DELETE'])
def delete_pet(id):
    supabase.table("pets").delete().eq("id", id).execute()
    return jsonify({"msg": "OK"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
           
