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

st.set_page_config(page_title="Huellitas NQN", layout="centered", page_icon="🐾")

# ===================== CONFIG =====================
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

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

init_db()

# ===================== EMAIL =====================
def enviar_mail(destino, tipo, datos=None):
    try:
        msg = MIMEMultipart()
        msg['From'] = os.getenv("MAIL_USERNAME")
        msg['To'] = destino
        
        if tipo == "bienvenida":
            msg['Subject'] = "¡Bienvenido a Huellitas NQN! 🐾"
            body = "Tu cuenta está en revisión. Te avisaremos cuando esté aprobada."
        elif tipo == "cuenta_aprobada":
            msg['Subject'] = "¡Cuenta Activada! Ya podés ayudar 🐶"
            body = "Tu cuenta en Huellitas NQN ha sido aprobada."
        elif tipo == "publicacion_exitosa":
            nombre = datos.get('nombre', 'la mascota') if datos else 'la mascota'
            msg['Subject'] = f"Recibimos el reporte de {nombre}"
            body = "¡Gracias por tu compromiso! El reporte pronto estará visible."
        else:
            return False
            
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(os.getenv("MAIL_USERNAME"), os.getenv("MAIL_PASSWORD"))
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Error enviando email: {e}")
        return False

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
        else:
            st.warning("Tu cuenta aún está pendiente de aprobación por André.")
            return None
    return None

# ===================== APP =====================
if 'user' not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.title("🐾 Huellitas NQN")
    tab1, tab2 = st.tabs(["Iniciar Sesión", "Registrarse"])
    
    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Contraseña", type="password", key="login_pass")
        if st.button("Entrar", type="primary"):
            user = login_user(email, password)
            if user:
                st.session_state.user = user
                st.rerun()
    
    with tab2:
        email_r = st.text_input("Email", key="reg_email")
        tel = st.text_input("WhatsApp (con código de país)", key="reg_tel")
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
                    enviar_mail(email_r, "bienvenida")
                    st.success("✅ Solicitud enviada! André la revisará pronto.")
else:
    user = st.session_state.user
    st.sidebar.success(f"👋 {user['email'].split('@')[0]}")
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.user = None
        st.rerun()
    
    page = st.sidebar.radio("Menú", 
        ["Mapa", "Nueva Publicación", "Mis Reportes"] + (["Admin"] if user.get('role') == 'admin' else []))

    if page == "Mapa":
        st.title("🐾 Mascotas en Neuquén")
        conn = get_db_connection()
        pets = conn.execute("SELECT * FROM pets WHERE is_approved = 1").fetchall()
        conn.close()

        if pets:
            m = folium.Map(location=[-38.951, -68.059], zoom_start=13)
            for p in pets:
                color = "red" if p["status"] == "perdido" else "green"
                folium.Marker(
                    [p["latitud"], p["longitud"]],
                    popup=f"<b>{p['name']}</b><br>{p['barrio']}<br>{p['especie']}",
                    icon=folium.Icon(color=color, icon="paw")
                ).add_to(m)
            st_folium(m, width=700, height=500)
        else:
            st.info("Aún no hay publicaciones aprobadas.")

    elif page == "Nueva Publicación":
        st.title("📸 Nueva Publicación")
        with st.form("upload_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Nombre de la mascota *")
                especie = st.selectbox("Especie", ["perro", "gato", "otro"])
            with col2:
                status = st.selectbox("Estado", ["perdido", "adopcion"])
                barrio = st.text_input("Barrio *")
            
            descripcion = st.text_area("Descripción / Comentarios", height=100)
            
            col3, col4 = st.columns(2)
            with col3:
                lat = st.number_input("Latitud", value=-38.951)
            with col4:
                lng = st.number_input("Longitud", value=-68.059)
            
            file = st.file_uploader("Foto de la mascota *", type=["jpg", "jpeg", "png"])
            
            submitted = st.form_submit_button("Publicar Reporte 🐾", type="primary")
            if submitted:
                if not name or not barrio or not file:
                    st.error("Nombre, barrio y foto son obligatorios")
                else:
                    with st.spinner("Subiendo a Cloudinary..."):
                        upload_result = cloudinary.uploader.upload(file, folder="huellitas")
                        image_url = upload_result["secure_url"]
                    
                    conn = get_db_connection()
                    conn.execute("""INSERT INTO pets 
                        (user_id, name, especie, status, barrio, descripcion, latitud, longitud, image_url, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (user['id'], name, especie, status, barrio, descripcion, lat, lng, image_url, datetime.now().isoformat()))
                    conn.commit()
                    conn.close()
                    
                    enviar_mail(user['email'], "publicacion_exitosa", {"nombre": name})
                    st.success("¡Reporte enviado correctamente! Esperando aprobación.")
                    st.rerun()

    elif page == "Mis Reportes":
        st.title("Mis Publicaciones")
        conn = get_db_connection()
        my_pets = conn.execute("SELECT * FROM pets WHERE user_id = ?", (user['id'],)).fetchall()
        conn.close()
        
        if not my_pets:
            st.info("Aún no tienes publicaciones.")
        for p in my_pets:
            col1, col2 = st.columns([1, 3])
            with col1:
                st.image(p["image_url"], width=120)
            with col2:
                st.subheader(p["name"])
                st.caption(f"{p['especie'].capitalize()} • {p['barrio']} • {p['status']}")
                st.write("✅ Aprobado" if p["is_approved"] else "⏳ Pendiente de aprobación")

    elif page == "Admin" and user.get('role') == 'admin':
        st.title("🔧 Panel de Administración")
        # Aquí podemos expandir más tarde

st.caption("Huellitas NQN - Neuquén Capital ❤️")
