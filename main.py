import os
from flask import Flask, request, jsonify, send_from_directory
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader
from flask_mail import Mail, Message

# 1. [span_0](start_span)Configuración de Flask y Carpeta Static[span_0](end_span)
app = Flask(__name__, static_folder='static', static_url_path='/static')

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

# --- RUTAS DE USUARIOS ---

@app.route('/login', methods=['POST'])
def login():
    # CAMBIO CLAVE: Usamos request.form porque tu index manda FormData
    e = request.form.get('email')
    p = request.form.get('password')
    
    # Validación Admin desde Render
    if e == os.getenv("ADMIN_EMAIL") and p == os.getenv("ADMIN_PASS"):
        return jsonify({
            "id": "admin", 
            "email": e, 
            "role": "admin", 
            "is_approved": True
        })

    try:
        # Validación Usuarios desde Supabase
        res = supabase.table("users").select("*").eq("email", e).execute()
        if res.data:
            user = res.data[0]
            # Si en tu DB la clave no está hasheada, la comparación es directa
            if user.get('password') == p:
                if user.get('is_approved'):
                    return jsonify(user)
                return jsonify({"msg": "Cuenta pendiente de aprobación"}), 401
    except Exception as err:
        print(f"Error login: {err}")
        
    return jsonify({"msg": "Credenciales inválidas"}), 401

@app.route('/register', methods=['POST'])
def register():
    try:
        # Tu index manda email, password y telefono
        d = request.form
        supabase.table("users").insert({
            "email": d['email'], 
            "password": d['password'], 
            "telefono": d['telefono'], 
            "is_approved": False
        }).execute()
        return jsonify({"msg": "OK"}), 201
    except Exception as e: 
        return jsonify({"msg": str(e)}), 500

# --- RUTAS DE MASCOTAS ---

@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    try:
        f = request.files.get('file')
        d = request.form
        
        if not f:
            return jsonify({"msg": "No se recibió ninguna imagen"}), 400

        # 1. Subida a Cloudinary con optimización para móviles
        up = cloudinary.uploader.upload(f, 
            folder="huellitas",
            transformation=[{"quality": "auto", "fetch_format": "auto"}]
        )
        
        # 2. Manejo SEGURO del user_id
        raw_user_id = d.get('user_id')
        user_id_final = None
        
        if raw_user_id and raw_user_id != 'admin' and raw_user_id != 'undefined':
            try:
                user_id_final = int(raw_user_id)
            except ValueError:
                user_id_final = None

        # 3. Insertar en Supabase
        supabase.table("pets").insert({
            "user_id": user_id_final, 
            "name": d.get('name', 'Sin nombre'), 
            "status": d.get('status', 'perdido'), 
            "especie": d.get('especie', 'perro'),
            "barrio": d.get('barrio', 'Sin barrio'), 
            "latitud": float(d.get('latitud', 0)), 
            "longitud": float(d.get('longitud', 0)), 
            "image_url": up['secure_url'], 
            "is_approved": False,
            "necesita_medicacion": d.get('necesita_medicacion') == 'on',
            "esta_herido": d.get('esta_herido') == 'on',
            "estado_resguardo": d.get('estado_resguardo', 'calle'),
            "referencia": d.get('referencia', '')
        }).execute()
        
        return jsonify({"msg": "OK"}), 201
    except Exception as e:
        print(f"ERROR EN UPLOAD: {str(e)}") # Esto aparecerá en los logs de Render
        return jsonify({"msg": str(e)}), 500
      

@app.route('/pets', methods=['GET'])
def get_pets():
    # Traemos mascotas aprobadas y el teléfono de quien reportó
    res = supabase.table("pets").select("*, users(telefono)").eq("is_approved", True).execute()
    return jsonify(res.data)

# --- RUTAS DE ADMIN ---

# --- PODER ABSOLUTO: RUTAS DE ELIMINACIÓN ---

@app.route('/admin/delete-pet/<int:pet_id>', methods=['DELETE'])
def admin_delete_pet(pet_id):
    try:
        # Borra la mascota sin importar su estado
        supabase.table("pets").delete().eq("id", pet_id).execute()
        return jsonify({"msg": "Mascota eliminada del sistema"}), 200
    except Exception as e:
        return jsonify({"msg": str(e)}), 500

@app.route('/admin/delete-user/<int:user_id>', methods=['DELETE'])
def admin_delete_user(user_id):
    try:
        # Borra al usuario (cuidado: esto es permanente)
        supabase.table("users").delete().eq("id", user_id).execute()
        return jsonify({"msg": "Usuario eliminado"}), 200
    except Exception as e:
        return jsonify({"msg": str(e)}), 500
      

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
    # 't' viene como 'user' o 'pet' desde tu index
    table = "users" if t == "user" else "pets"
    supabase.table(table).update({"is_approved": True}).eq("id", id).execute()
    return jsonify({"msg": "OK"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
      
