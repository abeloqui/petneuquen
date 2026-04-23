import os
from flask import Flask, request, jsonify, send_from_directory
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader

app = Flask(__name__)

# Configuración segura
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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
    email, password = data.get('email'), data.get('password')
    if email == "admin@huellitas.com" and password == "admin123":
        return jsonify({"id": "admin", "email": email, "role": "admin", "is_approved": True})
    try:
        res = supabase.table("users").select("*").eq("email", email).eq("password", password).eq("is_approved", True).execute()
        if res.data: return jsonify(res.data[0])
    except Exception as e: print(f"Error Login: {e}")
    return jsonify({"msg": "No autorizado"}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.form
    try:
        # Asegúrate que las columnas en Supabase se llamen exactamente así
        supabase.table("users").insert({
            "email": data['email'], 
            "password": data['password'], 
            "telefono": data['telefono'],
            "is_approved": False,
            "role": "user"
        }).execute()
        return jsonify({"msg": "Solicitud enviada con éxito"}), 201
    except Exception as e:
        return jsonify({"msg": f"Error: {str(e)}"}), 400

@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    file = request.files.get('file')
    if not file: return jsonify({"msg": "Falta imagen"}), 400
    try:
        up = cloudinary.uploader.upload(file, folder="huellitas_nqn")
        data = request.form
        supabase.table("pets").insert({
            "user_id": data['user_id'], "name": data['name'], "status": data['status'],
            "barrio": data['barrio'], "latitud": float(data['latitud']),
            "longitud": float(data['longitud']), "image_url": up['secure_url'], "is_approved": False
        }).execute()
        return jsonify({"msg": "OK"}), 201
    except Exception as e: return jsonify({"msg": str(e)}), 500

@app.route('/pets', methods=['GET'])
@app.route('/pets', methods=['GET'])
def get_pets():
    try:
        # Traemos solo las que tienen is_approved en True
        res = supabase.table("pets").select("*, users(telefono)").eq("is_approved", True).execute()
        
        pets = []
        for p in res.data:
            # Manejo de error por si el usuario no tiene teléfono
            p['telefono'] = p['users']['telefono'] if p.get('users') else "Sin contacto"
            pets.append(p)
        return jsonify(pets)
    except Exception as e:
        print(f"Error al obtener mascotas: {e}")
        return jsonify([])
      

# Endpoints de Admin simplificados para que no fallen
@app.route('/admin/pending', methods=['GET'])
def get_pending():
    u = supabase.table("users").select("*").eq("is_approved", False).execute()
    p = supabase.table("pets").select("*").eq("is_approved", False).execute()
    return jsonify({"users": u.data, "pets": p.data})

@app.route('/admin/approve/<type>/<id>', methods=['POST'])
def approve(type, id):
    table = "users" if type == "user" else "pets"
    supabase.table(table).update({"is_approved": True}).eq("id", id).execute()
    return jsonify({"msg": "OK"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
    
