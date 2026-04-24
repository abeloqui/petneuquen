import os
from flask import Flask, request, jsonify, send_from_directory
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader

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
    print(f"Error de configuración: {e}")

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




@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.form
        email = data.get('email')
        password = data.get('password')
        telefono = data.get('telefono')

        # Verificamos si el usuario ya existe
        check = supabase.table("users").select("*").eq("email", email).execute()
        if check.data:
            return jsonify({"msg": "Este email ya está registrado"}), 400

        # Insertamos el nuevo vecino (por defecto is_approved es False)
        supabase.table("users").insert({
            "email": email,
            "password": password,
            "telefono": telefono,
            "is_approved": False
        }).execute()

        return jsonify({"msg": "Solicitud enviada. El admin te aprobará pronto."}), 201
    except Exception as e:
        print(f"Error en registro: {e}")
        return jsonify({"msg": "Error al procesar el registro"}), 500
        









@app.route('/pets', methods=['GET'])
def get_all_pets():
    try:
        # Importante: usamos la relación que acabas de guardar en Supabase
        res = supabase.table("pets").select("*, users(telefono)").eq("is_approved", True).execute()
        return jsonify(res.data)
    except Exception as e:
        print(f"Error cargando mascotas: {e}")
        return jsonify([])

@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    try:
        f = request.files.get('file')
        d = request.form
        user_id = d.get('user_id')

        if not user_id or user_id == "admin":
            return jsonify({"msg": "Inicia sesión como vecino para publicar"}), 400

        up = cloudinary.uploader.upload(f, 
            folder="huellitas",
            transformation=[{'width': 800, 'crop': "limit"}, {'quality': "auto"}]
        )
        
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
        return jsonify({"msg": "Error al subir datos"}), 500

@app.route('/admin/data', methods=['GET'])
def admin_data():
    try:
        # Traemos todo para que las métricas de los círculos naranja y azul no den 0
        u_res = supabase.table("users").select("*").execute()
        p_res = supabase.table("pets").select("*").execute()
        
        users_all = u_res.data if u_res.data else []
        pets_all = p_res.data if p_res.data else []

        stats = {
            "perdidos": len([x for x in pets_all if x.get('status') == 'perdido']),
            "pendientes": len([x for x in pets_all if not x.get('is_approved')])
        }
        
        pending_users = [u for u in users_all if not u.get('is_approved')]
        
        return jsonify({
            "users": pending_users, 
            "pets": pets_all, 
            "stats": stats
        })
    except Exception as e:
        print(f"Error admin: {e}")
        return jsonify({"users": [], "pets": [], "stats": {"perdidos":0, "pendientes":0}})

@app.route('/admin/approve/<t>/<id>', methods=['POST'])
def approve_item(t, id):
    table = "users" if t == "user" else "pets"
    supabase.table(table).update({"is_approved": True}).eq("id", id).execute()
    return jsonify({"msg": "OK"})

@app.route('/admin/delete/<int:pet_id>', methods=['DELETE'])
def admin_delete(pet_id):
    supabase.table("pets").delete().eq("id", pet_id).execute()
    return jsonify({"msg": "OK"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
    
