import os
from flask import Flask, request, jsonify, send_from_directory
from flask_bcrypt import Bcrypt
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader
from flask_mail import Mail, Message
from datetime import datetime

app = Flask(__name__)
bcrypt = Bcrypt(app)

# Configuración
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-huellitas-nqn-2026')
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME") or os.getenv("Mail_Username")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD") or os.getenv("Mail_Password")
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

mail = Mail(app)

supabase: Client = create_client(
    os.getenv("SUPABASE_URL", "").strip(),
    os.getenv("SUPABASE_KEY", "").strip()
)

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

# ====================== EMAIL ======================
def enviar_mail(email_destino, tipo_evento, datos=None):
    temas = {
        "bienvenida": {"asunto": "¡Bienvenido a Huellitas NQN! 🐾", "cuerpo": "Tu cuenta está en revisión."},
        "cuenta_aprobada": {"asunto": "¡Cuenta Activada!", "cuerpo": "Ya podés publicar en Huellitas NQN."},
        "publicacion_exitosa": {"asunto": f"Reporte de {datos.get('name', 'mascota')} recibido", "cuerpo": "¡Gracias! Está en revisión."},
        "rechazo": {"asunto": "Actualización sobre tu reporte", "cuerpo": f"Motivo: {datos.get('motivo', 'No cumple con las normas.')}"}
    }
    evento = temas.get(tipo_evento)
    if not evento or not email_destino: return False
    msg = Message(evento["asunto"], recipients=[email_destino])
    msg.body = evento["cuerpo"]
    try:
        mail.send(msg)
        return True
    except:
        return False

# ====================== ROUTES ======================
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# AUTH
@app.route('/login', methods=['POST'])
def login():
    data = request.form
    email = data.get('email')
    password = data.get('password')

    admin_email = os.getenv("ADMIN_EMAIL", "admin@huellitas.com")
    admin_pass = os.getenv("ADMIN_PASS", "admin123")

    if email == admin_email and password == admin_pass:
        return jsonify({"id": "admin", "email": email, "role": "admin", "is_approved": True})

    try:
        res = supabase.table("users").select("*").eq("email", email).execute()
        if res.data:
            user = res.data[0]
            if not user.get('is_approved'):
                return jsonify({"msg": "Cuenta pendiente de aprobación"}), 401
            if bcrypt.check_password_hash(user.get('password'), password):
                return jsonify(user)
            return jsonify({"msg": "Contraseña incorrecta"}), 401
    except Exception as e:
        print("Login error:", e)
    return jsonify({"msg": "Usuario no encontrado"}), 401

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.form
        email = data.get('email')
        password = data.get('password')
        telefono = data.get('telefono')

        if not email or not password:
            return jsonify({"msg": "Email y contraseña requeridos"}), 400

        check = supabase.table("users").select("id").eq("email", email).execute()
        if check.data:
            return jsonify({"msg": "Email ya registrado"}), 400

        hashed = bcrypt.generate_password_hash(password).decode('utf-8')
        supabase.table("users").insert({
            "email": email, "password": hashed, "telefono": telefono, "is_approved": False
        }).execute()

        enviar_mail(email, "bienvenida")
        return jsonify({"msg": "Registro exitoso. Espera aprobación."}), 201
    except Exception as e:
        return jsonify({"msg": "Error interno"}), 500

# UPLOAD
@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    try:
        form = request.form
        files = request.files.getlist('file')[:3]
        user_id = form.get('user_id')

        if not user_id or not files:
            return jsonify({"msg": "Faltan datos o imágenes"}), 400

        image_urls = []
        for f in files:
            if f.filename:
                result = cloudinary.uploader.upload(f, folder="huellitas")
                image_urls.append(result['secure_url'])

        pet_data = {
            "user_id": int(user_id) if str(user_id) != "admin" else 0,
            "name": form['name'],
            "status": form['status'],
            "especie": form.get('especie', 'perro'),
            "raza": form.get('raza'),
            "edad": form.get('edad'),
            "color": form.get('color'),
            "barrio": form['barrio'],
            "latitud": float(form['latitud']),
            "longitud": float(form['longitud']),
            "descripcion": form.get('descripcion', ''),
            "microchip": form.get('microchip') == 'on',
            "fecha": form.get('fecha'),
            "image_urls": image_urls,
            "is_approved": False
        }

        supabase.table("pets").insert(pet_data).execute()

        user_res = supabase.table("users").select("email").eq("id", user_id).execute()
        if user_res.data:
            enviar_mail(user_res.data[0]['email'], "publicacion_exitosa", {"name": form['name']})

        return jsonify({"msg": "¡Reporte enviado a revisión!"}), 201
    except Exception as e:
        print("Upload error:", e)
        return jsonify({"msg": str(e)}), 500

# NUEVA RUTA: UPDATE PET
@app.route('/pets/update/<int:pet_id>', methods=['PATCH'])
def update_pet(pet_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"msg": "No hay datos para actualizar"}), 400

        # Solo actualizar campos permitidos
        allowed = ['name', 'status', 'especie', 'raza', 'edad', 'color', 'barrio', 'descripcion', 'microchip', 'fecha', 'latitud', 'longitud']
        update_data = {k: v for k, v in data.items() if k in allowed}

        if 'image_urls' in data and isinstance(data['image_urls'], list):
            update_data['image_urls'] = data['image_urls']

        supabase.table("pets").update(update_data).eq("id", pet_id).execute()
        return jsonify({"msg": "Publicación actualizada correctamente"}), 200
    except Exception as e:
        print("Update error:", e)
        return jsonify({"msg": "Error al actualizar"}), 500

@app.route('/pets', methods=['GET'])
def get_pets():
    res = supabase.table("pets").select("*, users(telefono)").eq("is_approved", True).execute()
    return jsonify(res.data)

@app.route('/my-pets/<user_id>', methods=['GET'])
def my_pets(user_id):
    res = supabase.table("pets").select("*").eq("user_id", user_id).execute()
    return jsonify(res.data)

# ADMIN
@app.route('/admin/data', methods=['GET'])
def admin_data():
    users_pend = supabase.table("users").select("*").eq("is_approved", False).execute()
    pets_all = supabase.table("pets").select("*, users(email, telefono)").execute()

    pets = pets_all.data or []
    stats = {
        "perdidos": len([p for p in pets if p.get('status') == 'perdido' and p.get('is_approved')]),
        "adopcion": len([p for p in pets if p.get('status') == 'adopcion' and p.get('is_approved')]),
        "pendientes_pets": len([p for p in pets if not p.get('is_approved')]),
        "pendientes_users": len(users_pend.data or [])
    }

    return jsonify({
        "users_pending": users_pend.data,
        "pets": pets,
        "stats": stats
    })

@app.route('/admin/approve/<t>/<int:id>', methods=['POST'])
def approve(t, id):
    table = "users" if t == "user" else "pets"
    supabase.table(table).update({"is_approved": True}).eq("id", id).execute()
    if t == "user":
        res = supabase.table("users").select("email").eq("id", id).execute()
        if res.data:
            enviar_mail(res.data[0]['email'], "cuenta_aprobada")
    return jsonify({"msg": "Aprobado"})

@app.route('/admin/reject/<t>/<int:id>', methods=['POST'])
def reject(t, id):
    table = "users" if t == "user" else "pets"
    supabase.table(table).update({"is_approved": False}).eq("id", id).execute()
    if t == "user":
        res = supabase.table("users").select("email").eq("id", id).execute()
        if res.data:
            enviar_mail(res.data[0]['email'], "rechazo", {"motivo": "No cumple con las normas"})
    return jsonify({"msg": "Rechazado"})

@app.route('/pets/user-delete/<int:pet_id>', methods=['DELETE'])
def user_delete(pet_id):
    supabase.table("pets").delete().eq("id", pet_id).execute()
    return jsonify({"msg": "Eliminado"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
