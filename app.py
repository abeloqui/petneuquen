import streamlit as st
import sqlite3
import cloudinary
import cloudinary.uploader
from datetime import datetime
import folium
from streamlit_folium import st_folium
import hashlib
import os
import extra_streamlit_components as stx
from streamlit_geolocation import streamlit_geolocation

st.set_page_config(page_title="Huellitas NQN", layout="centered", page_icon="🐾")

cloudinary.config(cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"), api_key=os.getenv("CLOUDINARY_API_KEY"), api_secret=os.getenv("CLOUDINARY_API_SECRET"), secure=True)

# ===================== COOKIES =====================
cookie_manager = stx.CookieManager(key="huellitas_cookies")

# ===================== DB =====================
def get_db_connection():
    conn = sqlite3.connect("huellitas.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, hashed_password TEXT NOT NULL,
        telefono TEXT, is_approved INTEGER DEFAULT 0, role TEXT DEFAULT 'user'
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS pets (...)''')  # completa con tus campos
    conn.commit()
    conn.close()

def create_default_admin():
    conn = get_db_connection()
    if not conn.execute("SELECT 1 FROM users WHERE email = 'admin@huellitas.com'").fetchone():
        hashed = hashlib.sha256("admin123".encode()).hexdigest()
        conn.execute("INSERT INTO users (email, hashed_password, telefono, is_approved, role) VALUES (?,?,?,?,?)",
                     ("admin@huellitas.com", hashed, "2996894360", 1, "admin"))
        conn.commit()
    conn.close()

init_db()
create_default_admin()

def hash_password(p): 
    return hashlib.sha256(p.encode()).hexdigest()

# ===================== LOGIN PERSISTENTE =====================
if 'user' not in st.session_state:
    st.session_state.user = None

# Intentar recuperar desde cookie
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
    tab1, tab2 = st.tabs(["🔑 Iniciar Sesión", "📝 Registrarse"])
    
    with tab1:
        email = st.text_input("Email")
        password = st.text_input("Contraseña", type="password")
        remember = st.checkbox("Recordarme (permanente)", value=True)
        
        if st.button("Entrar", type="primary"):
            conn = get_db_connection()
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            conn.close()
            if user and user['hashed_password'] == hash_password(password) and (user['is_approved'] or user['role'] == 'admin'):
                st.session_state.user = dict(user)
                if remember:
                    cookie_manager.set("huellitas_email", email, expires_at="2035-01-01")
                st.rerun()
            else:
                st.error("❌ Credenciales incorrectas")
else:
    user = st.session_state.user
    st.sidebar.success(f"👋 Hola, {user['email'].split('@')[0]}")
    
    if st.sidebar.button("🚪 Cerrar Sesión"):
        st.session_state.user = None
        cookie_manager.delete("huellitas_email")
        st.rerun()
    
    # Menú
    page = st.sidebar.radio("Ir a", ["Mapa", "Nueva Publicación", "Mis Reportes"] + (["Admin"] if user.get('role') == 'admin' else []))

    if page == "Mapa":
        st.title("🐾 Mascotas cerca de ti")
        location = streamlit_geolocation()
        
        if location and location.get('latitude'):
            lat, lng = location['latitude'], location['longitude']
            m = folium.Map(location=[lat, lng], zoom_start=15)
            folium.Marker([lat, lng], popup="📍 Vos estás acá", icon=folium.Icon(color="blue", icon="user")).add_to(m)
        else:
            lat, lng = -38.951, -68.059
            m = folium.Map(location=[lat, lng], zoom_start=13)
        
        conn = get_db_connection()
        pets = conn.execute("SELECT * FROM pets WHERE is_approved = 1").fetchall()
        conn.close()
        
        for p in pets:
            color = "red" if p["status"] == "perdido" else "green"
            folium.Marker([p["latitud"], p["longitud"]], 
                         popup=f"<b>{p['name']}</b><br>{p['barrio']}", 
                         icon=folium.Icon(color=color, icon="paw")).add_to(m)
        
        st_folium(m, width=700, height=550)

    # ... (agregá las otras secciones)

st.caption("Huellitas NQN - Neuquén Capital ❤️")
