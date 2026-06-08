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

st.set_page_config(page_title="Huellitas NQN - Admin", layout="wide", page_icon="🐾")

# ===================== ESTILO VISUAL =====================
st.markdown("""
<style>
    .main { background-color: #F4F1DE; }
    .stButton>button { background-color: #E07A5F; color: white; border-radius: 20px; font-weight: bold; }
    .stButton>button:hover { background-color: #C94C4C; }
    h1, h2 { color: #3D405B; }
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
            msg['Subject'] = "¡Tu cuenta en Huellitas NQN ha sido aprobada!"
            body = "¡Bienvenido! Ya podés publicar y ver el mapa."
        elif tipo == "publicacion_aprobada":
            nombre = datos.get('nombre', 'tu mascota')
            msg['Subject'] = f"✅ {nombre} ya está visible"
            body = f"Tu publicación de {nombre} fue aprobada y ya aparece en el mapa."
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
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, hashed_password TEXT NOT NULL,
        telefono TEXT, is_approved INTEGER DEFAULT 0, role TEXT DEFAULT 'user'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS pets (
        id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT NOT NULL,
        especie TEXT, status TEXT, barrio TEXT, descripcion TEXT,
        latitud REAL, longitud REAL, image_url TEXT,
        is_approved INTEGER DEFAULT 0, created_at TEXT,
        edad TEXT, raza TEXT, necesita_medicacion INTEGER DEFAULT 0,
        esta_herido INTEGER DEFAULT 0, estado_resguardo TEXT, referencia TEXT
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
    st.caption("Ingreso Administrativo")
    email = st.text_input("Email")
    password = st.text_input("Contraseña", type="password")
    if st.button("Entrar como Admin", type="primary"):
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        if user and user['hashed_password'] == hash_password(password) and user['role'] == 'admin':
            st.session_state.user = dict(user)
            st.rerun()
        else:
            st.error("Solo el administrador puede acceder")
else:
    user = st.session_state.user
    st.sidebar.success(f"👋 Admin: {user['email']}")
    
    if st.sidebar.button("🚪 Cerrar Sesión"):
        st.session_state.user = None
        st.rerun()

    # ===================== PANEL ADMIN CENTRAL =====================
    st.title("🛠 Panel de Control Total - Huellitas NQN")

    tab_map, tab_users, tab_pets, tab_stats = st.tabs(["🗺️ Mapa General", "👥 Usuarios", "🐾 Mascotas", "📊 Estadísticas"])

    # --- MAPA GENERAL ---
    with tab_map:
        st.subheader("Mapa General de Mascotas")
        location = streamlit_geolocation()
        if location and location.get('latitude'):
            lat, lng = location['latitude'], location['longitude']
            m = folium.Map(location=[lat, lng], zoom_start=14)
        else:
            m = folium.Map(location=[-38.951, -68.059], zoom_start=13)

        conn = get_db_connection()
        pets = conn.execute("SELECT * FROM pets WHERE is_approved = 1").fetchall()
        conn.close()

        for p in pets:
            color = "red" if p["status"] == "perdido" else "green"
            folium.Marker([p["latitud"], p["longitud"]], 
                         popup=f"<b>{p['name']}</b><br>{p['especie']} • {p['barrio']}", 
                         icon=folium.Icon(color=color, icon="paw")).add_to(m)
        st_folium(m, width=900, height=600)

    # --- USUARIOS ---
    with tab_users:
        st.subheader("Gestión de Usuarios")
        conn = get_db_connection()
        users = conn.execute("SELECT * FROM users").fetchall()
        conn.close()
        for u in users:
            col1, col2, col3 = st.columns([3,2,2])
            with col1:
                st.write(f"**{u['email']}** | {u['telefono'] or 'Sin tel'}")
            with col2:
                st.write("✅ Aprobado" if u['is_approved'] else "⏳ Pendiente")
            with col3:
                if not u['is_approved']:
                    if st.button("Aprobar Usuario", key=f"u_{u['id']}"):
                        conn = get_db_connection()
                        conn.execute("UPDATE users SET is_approved=1 WHERE id=?", (u['id'],))
                        conn.commit()
                        conn.close()
                        enviar_mail(u['email'], "cuenta_aprobada")
                        st.success("Usuario aprobado")
                        st.rerun()
                if st.button("Eliminar Usuario", key=f"delu_{u['id']}"):
                    if st.checkbox("Confirmar", key=f"confu_{u['id']}"):
                        conn = get_db_connection()
                        conn.execute("DELETE FROM users WHERE id=?", (u['id'],))
                        conn.commit()
                        conn.close()
                        st.success("Usuario eliminado")
                        st.rerun()

    # --- MASCOTAS (con edición completa) ---
    with tab_pets:
        st.subheader("Gestión de Mascotas")
        search = st.text_input("Buscar por nombre o barrio")
        conn = get_db_connection()
        query = "SELECT p.*, u.email as user_email FROM pets p LEFT JOIN users u ON p.user_id = u.id"
        if search:
            query += f" WHERE p.name LIKE '%{search}%' OR p.barrio LIKE '%{search}%'"
        pets = conn.execute(query).fetchall()
        conn.close()

        for p in pets:
            col1, col2, col3 = st.columns([1, 5, 2])
            with col1:
                st.image(p["image_url"], width=100)
            with col2:
                st.write(f"**{p['name']}** ({p['especie']}) - {p['barrio']}")
                st.caption(f"Por: {p['user_email']} | {p['status']}")
                if p['descripcion']:
                    st.write(p['descripcion'][:150] + "...")
            with col3:
                if not p['is_approved']:
                    if st.button("✅ Aprobar", key=f"apr_{p['id']}"):
                        conn = get_db_connection()
                        conn.execute("UPDATE pets SET is_approved=1 WHERE id=?", (p['id'],))
                        conn.commit()
                        conn.close()
                        enviar_mail(p['user_email'], "publicacion_aprobada", {"nombre": p['name']})
                        st.success("Aprobado + email enviado")
                        st.rerun()
                if st.button("✏️ Editar", key=f"edit_{p['id']}"):
                    st.session_state.edit_pet = p
                    st.rerun()
                if st.button("🗑 Eliminar", key=f"del_{p['id']}"):
                    if st.checkbox("Confirmar eliminación", key=f"conf_{p['id']}"):
                        conn = get_db_connection()
                        conn.execute("DELETE FROM pets WHERE id=?", (p['id'],))
                        conn.commit()
                        conn.close()
                        st.success("Publicación eliminada")
                        st.rerun()

    # Modal de edición
    if 'edit_pet' in st.session_state:
        p = st.session_state.edit_pet
        st.subheader(f"Editando: {p['name']}")
        with st.form("edit_form"):
            new_name = st.text_input("Nombre", value=p['name'])
            new_especie = st.selectbox("Especie", ["perro","gato","otro"])
            new_status = st.selectbox("Estado", ["perdido","adopcion"])
            new_barrio = st.text_input("Barrio", value=p['barrio'])
            new_desc = st.text_area("Descripción", value=p.get('descripcion',''))
            if st.form_submit_button("Guardar Cambios"):
                conn = get_db_connection()
                conn.execute("""UPDATE pets SET name=?, especie=?, status=?, barrio=?, descripcion=? WHERE id=?""",
                           (new_name, new_especie, new_status, new_barrio, new_desc, p['id']))
                conn.commit()
                conn.close()
                st.success("Cambios guardados")
                del st.session_state.edit_pet
                st.rerun()

    # --- ESTADÍSTICAS ---
    with tab_stats:
        conn = get_db_connection()
        stats = {
            "usuarios": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "mascotas": conn.execute("SELECT COUNT(*) FROM pets").fetchone()[0],
            "aprobadas": conn.execute("SELECT COUNT(*) FROM pets WHERE is_approved=1").fetchone()[0],
            "pendientes": conn.execute("SELECT COUNT(*) FROM pets WHERE is_approved=0").fetchone()[0]
        }
        conn.close()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Usuarios Totales", stats["usuarios"])
        col2.metric("Publicaciones Totales", stats["mascotas"])
        col3.metric("Aprobadas", stats["aprobadas"])
        col4.metric("Pendientes", stats["pendientes"])

st.caption("Huellitas NQN - Panel de Administración Total © André Beloqui")
