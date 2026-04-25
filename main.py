import os
from flask import Flask, request, jsonify, send_from_directory
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader
from flask_mail import Mail, Message

# Configuramos Flask para que reconozca la carpeta static
app = Flask(__name__, static_folder='static', static_url_path='/static')

# --- CONFIGURACIÓN DE CLOUDINARY ---
cloudinary.config(
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
  api_key = os.getenv("CLOUDINARY_API_KEY"),
  api_secret = os.getenv("CLOUDINARY_API_SECRET")
)

# --- CONFIGURACIÓN DE SUPABASE ---
url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# --- CONFIGURACIÓN DE CORREO ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

mail = Mail(app)

def enviar_mail(email_destino, tipo_evento, datos=None):
    temas = {
        "bienvenida": { "asunto": "¡Bienvenido! 🐾", "cuerpo": "Tu cuenta está en revisión." },
        "cuenta_aprobada": { "asunto": "¡Cuenta Activada! 🐶", "cuerpo": "Ya podés reportar mascotas." }
    }
    if tipo_evento in temas:
        msg = Message(temas[tipo_evento]["asunto"], recipients=[email_destino])
        msg.body = temas[tipo_evento]["cuerpo"]
        try: mail.send(msg)
        except Exception as e: print(f"Error mail: {e}")

# --- RUTAS ---

# CORRECCIÓN AQUÍ: Ahora busca el index.html DENTRO de la carpeta 'static'
@app.route('/')
def serve_index():
    return send_from_directory('static', 'index.html')

@app.route('/pets', methods=['GET'])
def get_pets():
    res = supabase.table("pets").select("*, users(telefono)").eq("is_approved", True).execute()
    return jsonify(res.data)

@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    try:
        file = request.files.get('file')
        if not file: return jsonify({"error": "No image"}), 400

        upload_result = cloudinary.uploader.upload(file)
        img_url = upload_result.get('secure_url')

        new_pet = {
            "name": request.form.get('name'),
            "especie": request.form.get('especie'),
            "status": request.form.get('status'),
            "barrio": request.form.get('barrio'),
            "latitud": float(request.form.get('latitud')),
            "longitud": float(request.form.get('longitud')),
            "image_url": img_url,
            "user_id": request.form.get('user_id'),
            "user_email": request.form.get('user_email'),
            "is_approved": False,
            "necesita_medicacion": request.form.get('necesita_medicacion') == 'true',
            "esta_herido": request.form.get('esta_herido') == 'true',
            "estado_resguardo": request.form.get('estado_resguardo', 'calle'),
            "referencia": request.form.get('referencia', '')
        }

        res = supabase.table("pets").insert(new_pet).execute()
        return jsonify(res.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/approve/<t>/<id>', methods=['POST'])
def approve(t, id):
    table = "users" if t == 'u' else "pets"
    column = "is_verified" if t == 'u' else "is_approved"
    res = supabase.table(table).update({column: True}).eq("id", id).execute()
    if t == 'u' and res.data: enviar_mail(res.data[0]['email'], "cuenta_aprobada")
    return jsonify({"msg": "OK"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
    
