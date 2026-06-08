import streamlit as st
import sqlite3
import cloudinary
import cloudinary.uploader
from datetime import datetime
import folium
from streamlit_folium import st_folium
import hashlib
import os
from streamlit_geolocation import streamlit_geolocation
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

st.set_page_config(page_title="Huellitas NQN", layout="wide", page_icon="🐾")

# ===================== ESTILO VISUAL (más parecido al original) =====================
st.markdown("""
<style>
    .main { background-color: #F4F1DE; }
    .stButton>button { background-color: #E07A5F; color: white; border-radius: 20px; font-weight: bold; }
    .stButton>button:hover { background-color: #C94C4C; }
    h1, h2, h3 { color: #3D405B; }
    .report-view { background-color: white; border-radius: 20px; padding: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
</style>
""", unsafe_allow_html=True)

# ===================== CONFIG =====================
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

# ===================== EMAIL =====================
def enviar_mail(destino, tipo, datos=None):
    try:
        msg = MIMEMultipart()
        msg['From'] = os.getenv("MAIL_USERNAME")
        msg['To'] = destino
        if tipo == "cuenta_aprobada":
            msg['Subject'] = "¡Tu cuenta en Huellitas NQN ha sido aprobada! 🐾"
            body = "¡Bienvenido! Ya podés publicar y ayudar a otras mascotas."
        elif tipo == "publicacion_aprobada":
            nombre = datos.get('nombre', 'tu mascota')
            msg['Subject'] = f"✅ {nombre} ya está visible en el mapa"
            body = f"¡Tu publicación de {nombre} fue aprobada y ya aparece en el mapa!"
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(os.getenv("MAIL_USERNAME"), os.getenv("MAIL_PASSWORD"))
        server.send_message(msg)
        server.quit()
        return True
    except:
        return False

# ===================== DATABASE =====================
def get_db_connection():
    conn = sqlite3.connect("huellitas.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, hashed_password TEXT NOT NULL, telefono TEXT, is_approved INTEGER DEFAULT 0, role TEXT DEFAULT 'user')''')
    c.execute('''CREATE TABLE IF NOT EXISTS pets (
        id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT NOT NULL, especie TEXT, status TEXT, barrio TEXT, 
        descripcion TEXT, latitud REAL, longitud REAL, image_url TEXT, is_approved INTEGER DEFAULT 0, 
        created_at TEXT, edad TEXT, raza TEXT, necesita_medicacion INTEGER DEFAULT 0, esta_herido INTEGER DEFAULT 0,
        estado_resguardo TEXT DEFAULT 'calle', referencia TEXT
    )''')
    conn.commit()
    conn.close()

def create_default_admin():
    conn = get_db_connection()
    if not conn.execute("SELECT id FROM users WHERE email = 'admin@huellitas.com'").fetchone():
        hashed = hashlib.sha256("admin123".encode()).hexdigest()
        conn.execute("INSERT INTO users (email, hashed_password, telefono, is_approved, role) VALUES (?,?,?,?,?)",
                     ("admin@huellitas.com", hashed, "2996894360", 1, "admin"))
        conn.commit()
    conn.close()

init_db()
create_default_admin()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ===================== AUTH =====================
if 'user' not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.title("🐾 Huellitas NQN")
    st.caption("Comunidad de Mascotas de Neuquén Capital")
    tab1, tab2 = st.tabs(["🔑 Iniciar Sesión", "📝 Registrarse"])
    # ... (login y registro igual que antes)
else:
    user = st.session_state.user
    st.sidebar.success(f"👋 {user['email'].split('@')[0]}")
    if st.sidebar.button("🚪 Cerrar Sesión"):
        st.session_state.user = None
        st.rerun()

    menu_options = ["🗺️ Mapa Principal", "📸 Nueva Publicación", "Mis Reportes"]
    if user.get('role') == 'admin':
        menu_options.append("🛠 Panel Admin")
    page = st.sidebar.radio("Ir a", menu_options)

    # ===================== MAPA PRINCIPAL =====================
    if page == "🗺️ Mapa Principal":
        st.title("🐾 Mascotas en Neuquén")
        location = streamlit_geolocation()
        if location and location.get('latitude'):
            lat, lng = location['latitude'], location['longitude']
            m = folium.Map(location=[lat, lng], zoom_start=15)
            folium.Marker([lat, lng], popup="📍 Vos estás acá", icon=folium.Icon(color="blue")).add_to(m)
        else:
            lat, lng = -38.951, -68.059
            m = folium.Map(location=[lat, lng], zoom_start=13)

        conn = get_db_connection()
        pets = conn.execute("SELECT * FROM pets WHERE is_approved = 1").fetchall()
        conn.close()

        for p in pets:
            color = "red" if p["status"] == "perdido" else "green"
            folium.Marker([p["latitud"], p["longitud"]], 
                         popup=f"<b>{p['name']}</b><br>{p['especie']} • {p['barrio']}", 
                         icon=folium.Icon(color=color, icon="paw")).add_to(m)
        st_folium(m, width=800, height=600)

    # ===================== NUEVA PUBLICACIÓN (con más campos) =====================
    elif page == "📸 Nueva Publicación":
        st.title("📸 Nueva Publicación")
        with st.form("upload_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Nombre de la mascota *")
                especie = st.selectbox("Especie", ["perro", "gato", "otro"])
                raza = st.text_input("Raza (opcional)")
                edad = st.text_input("Edad aproximada (ej: 2 años)")
            with col2:
                status = st.selectbox("Estado", ["perdido", "adopcion"])
                barrio = st.text_input("Barrio *")
                lat = st.number_input("Latitud", value=-38.951)
                lng = st.number_input("Longitud", value=-68.059)
            
            descripcion = st.text_area("Descripción / Comentarios", height=100)
            
            col3, col4 = st.columns(2)
            with col3:
                necesita_medicacion = st.checkbox("Necesita medicación")
                esta_herido = st.checkbox("Está herido / lastimado")
            with col4:
                estado_resguardo = st.selectbox("Estado de resguardo", ["calle", "en transito", "veterinaria", "rescatado"])
                referencia = st.text_input("Referencia / Contacto extra (opcional)")
            
            file = st.file_uploader("Foto de la mascota *", type=["jpg", "jpeg", "png"])
            
            if st.form_submit_button("Publicar Reporte 🐾", type="primary"):
                if not name or not barrio or not file:
                    st.error("Nombre, barrio y foto son obligatorios")
                else:
                    with st.spinner("Subiendo foto..."):
                        result = cloudinary.uploader.upload(file, folder="huellitas")
                        image_url = result["secure_url"]
                    
                    conn = get_db_connection()
                    conn.execute("""INSERT INTO pets 
                        (user_id, name, especie, status, barrio, descripcion, latitud, longitud, image_url, created_at,
                         edad, raza, necesita_medicacion, esta_herido, estado_resguardo, referencia)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (user['id'], name, especie, status, barrio, descripcion, lat, lng, image_url, 
                         datetime.now().isoformat(), edad, raza, int(necesita_medicacion), int(esta_herido), 
                         estado_resguardo, referencia))
                    conn.commit()
                    conn.close()
                    st.success("✅ Reporte enviado correctamente!")
                    st.rerun()

    # Resto de secciones (Mis Reportes y Panel Admin) se mantienen con edición

st.caption("Huellitas NQN - Neuquén Capital ❤️ Desarrollado por André")
