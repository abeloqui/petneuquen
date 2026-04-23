# main.py
import os
import sqlite3
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['DATABASE'] = 'database.db'

# Crear carpetas necesarias
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def get_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

# Inicialización de tablas (Todo lo que veníamos trabajando)
with get_db() as conn:
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        password TEXT,
        telefono TEXT,
        role TEXT DEFAULT 'user',
        is_approved INTEGER DEFAULT 0
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS pets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        status TEXT,
        barrio TEXT,
        latitud REAL,
        longitud REAL,
        image_url TEXT,
        is_approved INTEGER DEFAULT 0
    )''')
    # Admin por defecto (admin@huellitas.com / admin123)
    try:
        conn.execute("INSERT INTO users (email, password, role, is_approved) VALUES (?, ?, ?, ?)",
                     ('admin@huellitas.com', 'admin123', 'admin', 1))
    except:
        pass
    conn.commit()

# --- RUTAS ---
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.form
    try:
        with get_db() as conn:
            conn.execute("INSERT INTO users (email, password, telefono) VALUES (?, ?, ?)",
                         (data['email'], data['password'], data['telefono']))
            conn.commit()
        return jsonify({"msg": "Registrado"}), 201
    except:
        return jsonify({"msg": "Error"}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.form
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ? AND password = ? AND is_approved = 1",
                            (data['email'], data['password'])).fetchone()
    if user:
        return jsonify({"id": user['id'], "email": user['email'], "role": user['role']})
    return jsonify({"msg": "No autorizado"}), 401

@app.route('/pets/upload', methods=['POST'])
def upload_pet():
    file = request.files['file']
    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    data = request.form
    with get_db() as conn:
        conn.execute('''INSERT INTO pets (user_id, name, status, barrio, latitud, longitud, image_url) 
                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                     (data['user_id'], data['name'], data['status'], data['barrio'], 
                      data['latitud'], data['longitud'], f"/static/uploads/{filename}"))
        conn.commit()
    return jsonify({"msg": "OK"}), 201

@app.route('/pets', methods=['GET'])
def get_pets():
    all_pets = request.args.get('all_pets')
    with get_db() as conn:
        if all_pets:
            pets = conn.execute("SELECT p.*, u.telefono FROM pets p JOIN users u ON p.user_id = u.id").fetchall()
        else:
            pets = conn.execute("SELECT p.*, u.telefono FROM pets p JOIN users u ON p.user_id = u.id WHERE p.is_approved = 1").fetchall()
    return jsonify([dict(p) for p in pets])

# Rutas de Admin
@app.route('/admin/users/pending', methods=['GET'])
def pending_users():
    with get_db() as conn:
        users = conn.execute("SELECT * FROM users WHERE is_approved = 0").fetchall()
    return jsonify([dict(u) for u in users])

@app.route('/admin/users/approve/<int:id>', methods=['POST'])
def approve_user(id):
    with get_db() as conn:
        conn.execute("UPDATE users SET is_approved = 1 WHERE id = ?", (id,))
        conn.commit()
    return jsonify({"msg": "OK"})

@app.route('/pets/approve/<int:id>', methods=['POST'])
def approve_pet(id):
    with get_db() as conn:
        conn.execute("UPDATE pets SET is_approved = 1 WHERE id = ?", (id,))
        conn.commit()
    return jsonify({"msg": "OK"})

@app.route('/admin/pets/delete/<int:id>', methods=['DELETE'])
def delete_pet(id):
    with get_db() as conn:
        conn.execute("DELETE FROM pets WHERE id = ?", (id,))
        conn.commit()
    return jsonify({"msg": "OK"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
    
