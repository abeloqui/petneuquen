import streamlit as st
import sqlite3
import cloudinary
import cloudinary.uploader
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
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
cookie_manager = stx.CookieManager()

def get_cookie_manager():
    return cookie_manager

# ===================== DATABASE =====================
def get_db_connection():
    conn = sqlite3.connect("huellitas.db")
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
        name TEXT,
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
        conn.execute("INSERT INTO users (email, hashed_password, telefono, is_approved, role) VALUES (?, ?, ?, 1, 'admin')",
                     ("admin@huellitas.com", hashed, "2996894360"))
        conn.commit()
    conn.close()

init_db()
create_default_admin()

# ===================== AUTH =====================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_user(email, password):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    if user and user['hashed_password'] == hash_password(password):
        if user['is_approved'] or user['role'] == 'admin':
            return dict(user)
    return None

# ===================== APP =====================
cookies = get_cookie_manager()

# Intentar recuperar sesión desde cookie
if 'user' not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    saved_email = cookies.get("huellitas_user_email")
    if saved_email:
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (saved_email,)).fetchone()
        conn.close()
        if user and (user['is_approved'] or user['role'] == 'admin'):
            st.session_state.user = dict(user)

if st.session_state.user is None:
    st.title("🐾 Huellitas NQN")
    st.caption("Comunidad de Mascotas de Neuquén")

    tab1, tab2 = st.tabs(["Iniciar Sesión", "Registrarse"])

    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Contraseña", type="password", key="login_pass")
        remember = st.checkbox("Recordarme (permanente)", value=True)
        
        if st.button("Entrar", type="primary"):
            user = login_user(email, password)
            if user:
                st.session_state.user = user
                if remember:
                    cookies.set("huellitas_user_email", email, expires_at="2035-01-01")
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
else:
    user = st.session_state.user
    st.sidebar.success(f"👋 {user['email'].split('@')[0]}")
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.user = None
        cookies.delete("huellitas_user_email")
        st.rerun()
    
    opciones = ["Mapa", "Nueva Publicación", "Mis Reportes"]
    if user.get('role') == 'admin':
        opciones.append("Admin")
    
    page = st.sidebar.radio("Menú", opciones)

    if page == "Mapa":
        st.title("🐾 Mascotas cerca tuyo")
        
        # Geolocalización del usuario
        st.subheader("📍 Tu ubicación")
        location = streamlit_geolocation()
        
        if location and location.get('latitude'):
            user_lat = location['latitude']
            user_lng = location['longitude']
            st.success(f"📍 Ubicación detectada: {user_lat:.4f}, {user_lng:.4f}")
            
            # Mapa centrado en el usuario
            m = folium.Map(location=[user_lat, user_lng], zoom_start=14)
            
            # Marcador del usuario
            folium.Marker(
                [user_lat, user_lng],
                popup="📍 Tu ubicación actual",
                icon=folium.Icon(color="blue", icon="user")
            ).add_to(m)
        else:
            user_lat, user_lng = -38.951, -68.059
            m = folium.Map(location=[user_lat, user_lng], zoom_start=13)
            st.info("Usá el botón de geolocalización para centrar el mapa en tu posición.")

        # Cargar mascotas aprobadas
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

    # Resto de páginas (Nueva Publicación, Mis Reportes, Admin) quedan iguales a la versión anterior...

st.caption("Huellitas NQN - Neuquén Capital ❤️")
