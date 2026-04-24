import os
from flask import Flask, request, jsonify, send_from_directory
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- CONFIGURACIONES ---
try:
    # Supabase
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    supabase: Client = create_client(url, key)

    # Cloudinary
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
    
    # Credenciales de Admin (Hardcoded para emergencia, ideal usar env)
    admin_email = os.getenv("ADMIN_EMAIL", "admin@huellitas.com")
    admin_pass = os.getenv("ADMIN_PASS", "admin123")

    if e == admin_email and p == admin_pass:
        return jsonify({"id": "admin", "email": e, "role": "admin", "is_approved": True})
    
    try:
        res = supabase.table("users").select("*").eq("email", e).execute()
        if res.data:
            user = res.data[0]
            # Verificamos si la cuenta está aprobada y si la clave coincide
            if str(user.get('is_approved')).lower() == 'true':
                if user.get('password') == p: # Aquí podrías usar check_password_hash
                    return jsonify(user)
                else:
                    return jsonify({"msg": "Clave incorrecta"}), 401
            else:
                return jsonify({"msg": "Tu cuenta aún no ha sido aprobada por un admin."}), 401
    except Exception as err:
        print(f"Error login: {err}")
    
    return jsonify({"msg": "Usuario no encontrado"}), 401

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
        return jsonify({"msg": "Registro enviado. Un admin deberá aprobarte."}), 201
    except Exception as e:
        print(f"Error registro: {e}")
        return jsonify({"msg": "Error en el registro"}), 400

@app.route('/pets', methods=['GET'])
def get_pets():
    try:
        # Traemos solo las mascotas aprobadas
        res = supabase.table("pets").select("*, users(telefono)").eq("is_approved", True).execute()
        
        for p in res.data:
            # Limpiamos el teléfono para WhatsApp (solo números)
            raw_tel = p.get('users', {}).get('telefono') if p.get('users') else "2996894360"
            p['tel_final'] = "".join(filter(str.isdigit, str(raw_tel)))
            
        return jsonify(res.data)
    except Exception as e:
        print(f"Error pets: {e}")
        return jsonify([])
@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    try:
        print("--- Iniciando subida ---")
        f = request.files.get('file')
        d = request.form
        print(f"Datos recibidos: {d}")

        # Intento con Cloudinary
        try:
            up = cloudinary.uploader.upload(f, folder="huellitas")
            print(f"Cloudinary OK: {up['secure_url']}")
        except Exception as e_cloud:
            print(f"FALLÓ CLOUDINARY: {e_cloud}")
            return jsonify({"msg": f"Error Cloudinary: {str(e_cloud)}"}), 500

        # Intento con Supabase
        try:
            # IMPORTANTE: Asegúrate de que user_id no sea null
            user_id = d.get('user_id')
            if not user_id or user_id == "undefined":
                 return jsonify({"msg": "Error: ID de usuario no válido"}), 400

            supabase.table("pets").insert({
                "user_id": user_id, 
                "name": d['name'], 
                "status": d['status'],
                "barrio": d['barrio'], 
                "latitud": float(d['latitud']),
                "longitud": float(d['longitud']), 
                "image_url": up['secure_url'], 
                "is_approved": False
            }).execute()
            print("Supabase INSERT exitoso")
        except Exception as e_supa:
            print(f"FALLÓ SUPABASE: {e_supa}")
            return jsonify({"msg": f"Error Supabase: {str(e_supa)}"}), 500

        return jsonify({"msg": "OK"}), 201
    except Exception as e:
        print(f"ERROR GENERAL: {e}")
        return jsonify({"msg": str(e)}), 500
        
@app.route('/admin/data', methods=['GET'])
def admin_data():
    try:
        u = supabase.table("users").select("*").eq("is_approved", False).execute()
        p = supabase.table("pets").select("*").execute()
        return jsonify({"users": u.data, "pets": p.data})
    except:
        return jsonify({"users": [], "pets": []})

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
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
    
