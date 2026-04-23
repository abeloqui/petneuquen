import os
from flask import Flask, request, jsonify, send_from_directory
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader

app = Flask(__name__)

# Configuración Supabase (Eterna)
url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Configuración Cloudinary (Inmortal)
cloudinary.config( 
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"), 
  api_key = os.getenv("CLOUDINARY_API_KEY"), 
  api_secret = os.getenv("CLOUDINARY_API_SECRET"),
  secure = True
)

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.form
    try:
        supabase.table("users").insert({
            "email": data['email'], 
            "password": data['password'], 
            "telefono": data['telefono']
        }).execute()
        return jsonify({"msg": "OK"}), 201
    except:
        return jsonify({"msg": "Error"}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.form
    response = supabase.table("users").select("*").eq("email", data['email']).eq("password", data['password']).eq("is_approved", True).execute()
    user = response.data[0] if response.data else None
    if user:
        return jsonify(user)
    return jsonify({"msg": "No autorizado"}), 401

@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    file = request.files['file']
    if file:
        upload_result = cloudinary.uploader.upload(file, folder="huellitas_nqn")
        image_url = upload_result['secure_url']
        data = request.form
        supabase.table("pets").insert({
            "user_id": data['user_id'],
            "name": data['name'],
            "status": data['status'],
            "barrio": data['barrio'],
            "latitud": data['latitud'],
            "longitud": data['longitud'],
            "image_url": image_url
        }).execute()
        return jsonify({"msg": "OK"}), 201
    return jsonify({"msg": "Error"}), 400

@app.route('/pets', methods=['GET'])
def get_pets():
    all_pets = request.args.get('all_pets')
    query = supabase.table("pets").select("*, users(telefono)")
    if not all_pets:
        query = query.eq("is_approved", True)
    response = query.execute()
    # Aplanamos la respuesta para que el frontend siga funcionando igual
    pets = []
    for p in response.data:
        p['telefono'] = p['users']['telefono'] if p.get('users') else ""
        pets.append(p)
    return jsonify(pets)

# --- PANEL ADMIN ---
@app.route('/admin/users/pending', methods=['GET'])
def pending_users():
    res = supabase.table("users").select("*").eq("is_approved", False).execute()
    return jsonify(res.data)

@app.route('/admin/users/approve/<int:id>', methods=['POST'])
def approve_user(id):
    supabase.table("users").update({"is_approved": True}).eq("id", id).execute()
    return jsonify({"msg": "OK"})

@app.route('/pets/approve/<int:id>', methods=['POST'])
def approve_pet(id):
    supabase.table("pets").update({"is_approved": True}).eq("id", id).execute()
    return jsonify({"msg": "OK"})

@app.route('/admin/pets/delete/<int:id>', methods=['DELETE'])
def delete_pet(id):
    supabase.table("pets").delete().eq("id", id).execute()
    return jsonify({"msg": "OK"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
  
