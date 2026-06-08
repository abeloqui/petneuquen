import streamlit as st
import sqlite3
import cloudinary
import cloudinary.uploader
from datetime import datetime, timedelta
import folium
from streamlit_folium import st_folium
import hashlib
import os
import extra_streamlit_components as stx
from streamlit_geolocation import streamlit_geolocation

st.set_page_config(page_title="Huellitas NQN", layout="centered", page_icon="🐾")

# ===================== CONFIG =====================
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

# ===================== COOKIES =====================
cookie_manager = stx.CookieManager(key="huellitas_cookies")

# ===================== DATABASE =====================
def get_db_connection():
    conn = sqlite3.connect("huellitas.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL,
        telefono TEXT,
        is_approved INTEGER DEFAULT 0,
        role TEXT DEFAULT 'user'
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS pets (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        name TEXT NOT NULL,
        especie TEXT,
        status TEXT,
        barrio TEXT,
        descripcion TEXT,
        latitud REAL,
        longitud REAL,
        image_url TEXT,
        is_approved INTEGER DEFAULT 0,
        created_at TEXT
    )''')
    
    conn.commit()
    conn.close()

def create_default_admin():
    conn = get_db_connection()
    if not conn.execute("SELECT id FROM users WHERE email = 'admin@huellitas.com'").fetchone():
        hashed = hashlib.sha256("admin123".encode()).hexdigest()
        conn.execute("""
            INSERT INTO users (email, hashed_password, telefono, is_approved, role)
            VALUES (?, ?, ?, 1, 'admin')
        """, ("admin@huellitas.com", hashed, "2996894360"))
        conn.commit()
    conn.close()

init_db()
create_default_admin()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ===================== APP =====================
if 'user' not in st.session_state:
    st.session_state.user = None

# Recuperar sesión desde cookie
if st.session_state.user is None:
    saved_email = cookie_manager.get(cookie="huellitas_email")
    if saved_email:
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (saved_email,)).fetchone()
        conn.close()
        if user and (user['is_approved'] or user['role'] == 'admin'):
            st.session_state.user = dict(user)

if st.session_state.user is None:
    st.title("🐾 Huellitas NQN")
    st.caption("Comunidad de Mascotas de Neuquén Capital")
    
    tab1, tab2 = st.tabs(["🔑 Iniciar Sesión", "📝 Registrarse"])
    
    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Contraseña", type="password", key="login_pass")
        remember = st.checkbox("Recordarme (permanente)", value=True)
        
        if st.button("Entrar", type="primary"):
            conn = get_db_connection()
            user_db = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            conn.close()
            
            if user_db and user_db['hashed_password'] == hash_password(password) and (user_db['is_approved'] or user_db['role'] == 'admin'):
                st.session_state.user = dict(user_db)
                if remember:
                    # Fecha de expiración correcta
                    expires = datetime.now() + timedelta(days=365)
                    cookie_manager.set("huellitas_email", email, expires_at=expires)
                st.rerun()
            else:
                st.error("❌ Email o contraseña incorrectos")

    with tab2:
        email_r = st.text_input("Email", key="reg_email")
        tel = st.text_input("WhatsApp", key="reg_tel")
        pass_r = st.text_input("Contraseña", type="password", key="reg_pass")
        if st.button("Solicitar Acceso", type="primary"):
            if not email_r or not pass_r:
                st.error("Email y contraseña son obligatorios")
            else:
                conn = get_db_connection()
                if conn.execute("SELECT id FROM users WHERE email=?", (email_r,)).fetchone():
                    st.error("El email ya está registrado")
                else:
                    hashed = hash_password(pass_r)
                    conn.execute("INSERT INTO users (email, hashed_password, telefono) VALUES (?, ?, ?)",
                               (email_r, hashed, tel))
                    conn.commit()
                    conn.close()
                    st.success("✅ Solicitud enviada! André la revisará pronto.")

else:
    user = st.session_state.user
    st.sidebar.success(f"👋 {user['email'].split('@')[0]}")
    
    if st.sidebar.button("🚪 Cerrar Sesión"):
        st.session_state.user = None
        cookie_manager.delete("huellitas_email")
        st.rerun()
    
    opciones = ["Mapa", "Nueva Publicación", "Mis Reportes"]
    if user.get('role') == 'admin':
        opciones.append("Admin")
    
    page = st.sidebar.radio("Menú", opciones)

    if page == "Mapa":
        st.title("🐾 Mascotas cerca de ti")
        location = streamlit_geolocation()
        
        if location and location.get('latitude'):
            user_lat = location['latitude']
            user_lng = location['longitude']
            st.success(f"📍 Tu ubicación: {user_lat:.4f}, {user_lng:.4f}")
            m = folium.Map(location=[user_lat, user_lng], zoom_start=15)
            folium.Marker([user_lat, user_lng], popup="📍 Vos estás acá", icon=folium.Icon(color="blue")).add_to(m)
        else:
            user_lat, user_lng = -38.951, -68.059
            m = folium.Map(location=[user_lat, user_lng], zoom_start=13)
            st.info("Permite geolocalización para centrar en tu zona")

        conn = get_db_connection()
        pets = conn.execute("SELECT * FROM pets WHERE is_approved = 1").fetchall()
        conn.close()

        for p in pets:
            color = "red" if p["status"] == "perdido" else "green"
            folium.Marker(
                [p["latitud"], p["longitud"]],
                popup=f"<b>{p['name']}</b><br>{p['especie']} • {p['barrio']}",
                icon=folium.Icon(color=color, icon="paw")
            ).add_to(m)
        
        st_folium(m, width=700, height=550)

st.caption("Huellitas NQN ❤️ Neuquén Capital")
