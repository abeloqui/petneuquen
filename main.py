import os
from flask import Flask, request, jsonify, send_from_directory
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader

app = Flask(__name__)

# Configuración de Clientes desde Variables de Entorno
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
    print(f"Error de configuración: {e}")

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# --- AUTENTICACIÓN ---
@app.route('/login', methods=['POST'])
def login():
    data = request.form
    email = data.get('email')
    password = data.get('password')
    
    # LLAVE MAESTRA: Acceso garantizado para vos
    if email == "admin@huellitas.com" and password == "admin123":
        return jsonify({"id": "admin", "email": email, "role": "admin", "is_approved": True})

    try:
        res = supabase.table("users").select("*").eq("email", email).eq("password", password).eq("is_approved", True).execute()
        if res.data:
            return jsonify(res.data[0])
    except Exception as e:
        print(f"Error Login: {e}")
    
    return jsonify({"msg": "Credenciales inválidas o cuenta no aprobada aún"}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.form
    try:
        supabase.table("users").insert({
            "email": data['email'], 
            "password": data['password'], 
            "telefono": data['telefono'],
            "role": "user",
            "is_approved": False
        }).execute()
        return jsonify({"msg": "Solicitud enviada con éxito. Aguarda la aprobación del admin."}), 201
    except Exception as e:
        return jsonify({"msg": "El correo ya está registrado o hubo un error"}), 400

# --- GESTIÓN DE MASCOTAS ---
@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    file = request.files.get('file')
    if not file: return jsonify({"msg": "Falta la foto"}), 400
    
    try:
        # Subida a Cloudinary (Inmortal)
        up = cloudinary.uploader.upload(file, folder="huellitas_nqn")
        data = request.form
        # Guardado en Supabase (Eterno)
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
        # Traemos mascotas y unimos con el teléfono del usuario
        query = supabase.table("pets").select("*, users(telefono)")
        if not all_pets:
            query = query.eq("is_approved", True)
        res = query.execute()
        
        pets = []
        for p in res.data:
            p['telefono'] = p['users']['telefono'] if p.get('users') else "Sin contacto"
            pets.append(p)
        return jsonify(pets)
    except:
        return jsonify([])

# --- ADMINISTRACIÓN ---
@app.route('/admin/pending', methods=['GET'])
def get_pending():
    users = supabase.table("users").select("*").eq("is_approved", False).execute()
    pets = supabase.table("pets").select("*").eq("is_approved", False).execute()
    return jsonify({"users": users.data, "pets": pets.data})

@app.route('/admin/approve/user/<id>', methods=['POST'])
def approve_user(id):
    supabase.table("users").update({"is_approved": True}).eq("id", id).execute()
    return jsonify({"msg": "OK"})

@app.route('/admin/approve/pet/<id>', methods=['POST'])
def approve_pet(id):
    supabase.table("pets").update({"is_approved": True}).eq("id", id).execute()
    return jsonify({"msg": "OK"})

@app.route('/admin/delete/pet/<id>', methods=['DELETE'])
def delete_pet(id):
    supabase.table("pets").delete().eq("id", id).execute()
    return jsonify({"msg": "OK"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
            
