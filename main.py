import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify, send_from_directory
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader

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

    # Email
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
except Exception as e:
    print(f"Error en configuración inicial: {e}")

# --- FUNCIÓN DE EMAIL (Manejo de errores mejorado) ---
def enviar_bienvenida(destinatario):
    if not MAIL_USERNAME or not MAIL_PASSWORD:
        print("Error: Credenciales de mail no configuradas en Render.")
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = f"Huellitas NQN <{MAIL_USERNAME}>"
        msg['To'] = destinatario
        msg['Subject'] = "¡Bienvenido a Huellitas NQN! 🐾"

        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
                <div style="background: #f97316; padding: 25px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="color: white; margin: 0;">¡Hola! 👋</h1>
                </div>
                <div style="padding: 20px; border: 1px solid #eee; border-top: none; border-radius: 0 0 10px 10px;">
                    <p>Gracias por sumarte a <b>Huellitas NQN</b>. Recibimos tu solicitud de registro.</p>
                    <p>Un administrador revisará tu perfil pronto para habilitar tu acceso. Mientras tanto, podés navegar la plataforma.</p>
                    <p style="color: #f97316; font-weight: bold; font-size: 1.1em;">"Cada huella cuenta en nuestra comunidad."</p>
                    <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                    <p style="font-size: 0.8em; color: #888;">Este es un mensaje automático de Huellitas Neuquén.</p>
                </div>
            </body>
        </html>
        """
        msg.attach(MIMEText(html, 'html'))
        
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.send_raw_message(msg)
        print(f"Mail enviado correctamente a {destinatario}")
        return True
    except Exception as e:
        print(f"Error crítico en envío de mail: {e}")
        return False

# --- RUTAS PRINCIPALES ---
@app.route('/')
def serve_index():
    return send_from_directory('static', 'index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.form
    email, password = data.get('email'), data.get('password')
    # Usuario Administrador Maestro
    if email == "admin@huellitas.com" and password == "admin123":
        return jsonify({"id": "admin", "email": email, "role": "admin", "is_approved": True})
    try:
        res = supabase.table("users").select("*").eq("email", email).eq("password", password).eq("is_approved", True).execute()
        if res.data: return jsonify(res.data[0])
    except: pass
    return jsonify({"msg": "No autorizado o cuenta pendiente"}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.form
    try:
        email = data['email']
        supabase.table("users").insert({
            "email": email, "password": data['password'], 
            "telefono": data['telefono'], "role": "user", "is_approved": False
        }).execute()
        enviar_bienvenida(email)
        return jsonify({"msg": "Solicitud enviada. Revisá tu casilla de correo."}), 201
    except Exception as e:
        return jsonify({"msg": str(e)}), 400

@app.route('/pets', methods=['GET'])
def get_pets():
    try:
        # Traemos solo aprobadas. Usamos el campo users para sacar el teléfono de contacto.
        res = supabase.table("pets").select("*, users(telefono)").eq("is_approved", True).execute()
        pets = []
        for p in res.data:
            p['telefono'] = p['users']['telefono'] if p.get('users') and p['users'] else "2990000000"
            pets.append(p)
        return jsonify(pets)
    except Exception as e:
        print(f"Error GET pets: {e}")
        return jsonify([])

@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    file = request.files.get('file')
    if not file: return jsonify({"msg": "Falta imagen"}), 400
    try:
        # Subir a Cloudinary
        up = cloudinary.uploader.upload(file, folder="huellitas_nqn")
        data = request.form
        supabase.table("pets").insert({
            "user_id": data['user_id'], "name": data['name'], "status": data['status'],
            "barrio": data['barrio'], "latitud": float(data['latitud']),
            "longitud": float(data['longitud']), "image_url": up['secure_url'], "is_approved": False
        }).execute()
        return jsonify({"msg": "Mascota subida, pendiente de aprobación"}), 201
    except Exception as e:
        return jsonify({"msg": str(e)}), 500

# --- PANEL DE ADMINISTRACIÓN ---
@app.route('/admin/data', methods=['GET'])
def admin_data():
    u = supabase.table("users").select("*").eq("is_approved", False).execute()
    p = supabase.table("pets").select("*").order("is_approved").execute()
    return jsonify({"users": u.data, "pets": p.data})

@app.route('/admin/approve/<type>/<id>', methods=['POST'])
def approve(type, id):
    table = "users" if type == "user" else "pets"
    supabase.table(table).update({"is_approved": True}).eq("id", id).execute()
    return jsonify({"msg": "Aprobado"})

@app.route('/admin/delete/pet/<id>', methods=['DELETE'])
def delete_pet(id):
    try:
        # 1. Borrar de Cloudinary primero
        res = supabase.table("pets").select("image_url").eq("id", id).execute()
        if res.data:
            img_url = res.data[0]['image_url']
            public_id = "huellitas_nqn/" + img_url.split('/')[-1].split('.')[0]
            cloudinary.uploader.destroy(public_id)
        # 2. Borrar de Supabase
        supabase.table("pets").delete().eq("id", id).execute()
        return jsonify({"msg": "Eliminado"})
    except:
        return jsonify({"msg": "Error al borrar"}), 500

if __name__ == '__main__':
    # Puerto dinámico para Render
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
        
