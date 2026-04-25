import os
from flask import Flask, request, jsonify, send_from_directory
from supabase import create_client, Client
from auth import verify_password  # Usamos tu archivo auth.py para validar

app = Flask(__name__, static_folder='static', static_url_path='')

# --- CONFIGURACIÓN DESDE VARIABLES DE ENTORNO (Render) ---
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

# --- RUTA DE LOGIN CORREGIDA ---
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    try:
        # 1. Buscamos al usuario en la tabla 'users' de Supabase
        res = supabase.table("users").select("*").eq("email", email).execute()
        
        if not res.data:
            return jsonify({"error": "Usuario no encontrado"}), 401
        
        user_db = res.data[0]

        # 2. Verificamos la contraseña usando tu lógica de auth.py
        # Si guardaste la clave como texto plano en Supabase, usa: if user_db['hashed_password'] == password:
        if verify_password(password, user_db['hashed_password']):
            # 3. Retornamos los datos si coinciden
            return jsonify({
                "id": user_db['id'],
                "email": user_db['email'],
                "role": user_db.get('role', 'user'),
                "is_verified": user_db.get('is_verified', False)
            })
        else:
            return jsonify({"error": "Contraseña incorrecta"}), 401

    except Exception as e:
        print(f"Error en Login: {e}")
        return jsonify({"error": str(e)}), 500

# --- EL RESTO DE TUS RUTAS (get_pets, upload_pet, etc.) ---
# ... (mantené el código de upload que te pasé antes) ...

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
  
