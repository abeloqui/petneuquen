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

# --- RUTAS PRINCIPALES ---

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.form
    e, p = data.get('email'), data.get('password')
    admin_email = os.getenv("ADMIN_EMAIL", "admin@huellitas.com")
    admin_pass = os.getenv("ADMIN_PASS", "admin123")

    if e == admin_email and p == admin_pass:
        return jsonify({"id": "admin", "email": e, "role": "admin", "is_approved": True})
    
    try:
        res = supabase.table("users").select("*").eq("email", e).execute()
        if res.data:
            user = res.data[0]
            if str(user.get('is_approved')).lower() == 'true':
                if user.get('password') == p:
                    return jsonify(user)
                return jsonify({"msg": "Clave incorrecta"}), 401
            return jsonify({"msg": "Cuenta pendiente de aprobación"}), 401
    except Exception as err:
        print(f"Error login: {err}")
    return jsonify({"msg": "Usuario no encontrado"}), 401

@app.route('/pets', methods=['GET'])
def get_all_pets():
    try:
        res = supabase.table("pets").select("*, users(telefono)").eq("is_approved", True).execute()
        data = res.data
        for p in data:
            user_data = p.get('users')
            raw_tel = user_data.get('telefono') if user_data else "2996894360"
            p['tel_final'] = "".join(filter(str.isdigit, str(raw_tel)))
        return jsonify(data)
    except:
        res = supabase.table("pets").select("*").eq("is_approved", True).execute()
        return jsonify(res.data)

# --- GESTIÓN DE USUARIO (MIS PUBLICACIONES) ---

@app.route('/my-pets/<int:user_id>', methods=['GET'])
def get_user_pets_list(user_id):
    try:
        res = supabase.table("pets").select("*").eq("user_id", user_id).execute()
        return jsonify(res.data)
    except Exception as e:
        print(f"Error en mis mascotas: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/pets/user-delete/<int:pet_id>', methods=['DELETE'])
def user_self_delete(pet_id):
    try:
        supabase.table("pets").delete().eq("id", pet_id).execute()
        return jsonify({"msg": "Publicación eliminada"})
    except Exception as e:
        print(f"Error al eliminar: {e}")
        return jsonify({"error": str(e)}), 500

# --- SUBIDA DE MASCOTAS ---

@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    try:
        f = request.files.get('file')
        d = request.form
        user_id = d.get('user_id')

        if not user_id or user_id == "admin":
            return jsonify({"msg": "Usa una cuenta de usuario real para publicar"}), 400

        up = cloudinary.uploader.upload(f, folder="huellitas")
        
        supabase.table("pets").insert({
            "user_id": int(user_id), 
            "name": d['name'], 
            "status": d['status'],
            "barrio": d['barrio'], 
            "latitud": float(d['latitud']),
            "longitud": float(d['longitud']), 
            "image_url": up['secure_url'], 
            "is_approved": False
        }).execute()
        return jsonify({"msg": "OK"}), 201
    except Exception as e:
        print(f"Error subida: {e}")
        return jsonify({"msg": str(e)}), 500

# --- ADMINISTRACIÓN ---

@app.route('/admin/data', methods=['GET'])
def admin_data():
    u = supabase.table("users").select("*").eq("is_approved", False).execute()
    p = supabase.table("pets").select("*").execute()
    return jsonify({"users": u.data, "pets": p.data})

@app.route('/admin/approve/<t>/<id>', methods=['POST'])
def approve_item(t, id):
    table = "users" if t == "user" else "pets"
    supabase.table(table).update({"is_approved": True}).eq("id", id).execute()
    return jsonify({"msg": "OK"})

@app.route('/admin/delete-any/<int:pet_id>', methods=['DELETE'])
def admin_delete_pet(pet_id):
    supabase.table("pets").delete().eq("id", pet_id).execute()
    return jsonify({"msg": "Eliminado por admin"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
    
