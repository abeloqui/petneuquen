import os
from flask import Flask, request, jsonify, send_from_directory
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader

app = Flask(__name__)

# Configuración de Clientes (Variables de Entorno en Render)
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
    print(f"Error configurando servicios: {e}")

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# --- AUTENTICACIÓN ---
@app.route('/login', methods=['POST'])
def login():
    data = request.form
    email = data.get('email')
    password = data.get('password')
    
    if email == "admin@huellitas.com" and password == "admin123":
        return jsonify({"id": "admin", "email": email, "role": "admin", "is_approved": True})

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
            "role": "user",
            "is_approved": False
        }).execute()
        return jsonify({"msg": "Solicitud enviada con éxito"}), 201
    except Exception as e:
        return jsonify({"msg": f"Error: {str(e)}"}), 400

# --- GESTIÓN DE MASCOTAS ---
@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    file = request.files.get('file')
    if not file: return jsonify({"msg": "Falta imagen"}), 400
    
    try:
        up = cloudinary.uploader.upload(file, folder="huellitas_nqn")
        data = request.form
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
    try:
        # Consulta simplificada: traemos mascotas aprobadas directamente
        res = supabase.table("pets").select("*").eq("is_approved", True).execute()
        
        # Agregamos un teléfono genérico si no se encuentra relación, 
        # para que la app no rompa al intentar mostrar el botón de WhatsApp
        pets = []
        for p in res.data:
            p['telefono'] = p.get('telefono', "2990000000") 
            pets.append(p)
            
        return jsonify(pets)
    except Exception as e:
        print(f"Error GET pets: {e}")
        return jsonify([])

# --- ADMINISTRACIÓN ---
# --- ADMINISTRACIÓN ---

@app.route('/admin/pending', methods=['GET'])
def get_admin_data():
    try:
        # Traemos usuarios pendientes de aprobación
        users = supabase.table("users").select("*").eq("is_approved", False).execute()
        # Traemos TODAS las mascotas para poder borrarlas o aprobarlas
        pets = supabase.table("pets").select("*").order("is_approved").execute() 
        return jsonify({"users": users.data, "pets": pets.data})
    except Exception as e:
        print(f"Error en admin data: {e}")
        return jsonify({"users": [], "pets": []})

@app.route('/admin/approve/<type>/<id>', methods=['POST'])
def approve(type, id):
    table = "users" if type == "user" else "pets"
    try:
        supabase.table(table).update({"is_approved": True}).eq("id", id).execute()
        return jsonify({"msg": "OK"})
    except:
        return jsonify({"msg": "Error"}), 500

@app.route('/admin/delete/pet/<id>', methods=['DELETE'])
def delete_pet(id):
    try:
        # Borra la mascota de la base de datos
        supabase.table("pets").delete().eq("id", id).execute()
        return jsonify({"msg": "Mascota eliminada"})
    except Exception as e:
        return jsonify({"msg": f"Error al borrar: {str(e)}"}), 500
        

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
  
