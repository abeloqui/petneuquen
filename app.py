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
from math import radians, cos, sin, asin, sqrt

st.set_page_config(page_title="Huellitas NQN", layout="wide", page_icon="🐾")

# ===================== ESTILO VISUAL =====================
st.markdown("""
<style>
    .main { background-color: #F4F1DE; }
    .stButton>button { 
        background: linear-gradient(135deg, #E07A5F, #C94C4C); 
        color: white; 
        border-radius: 25px; 
        font-weight: bold; 
        height: 3.2em;
        transition: all 0.3s;
    }
    .stButton>button:hover { transform: scale(1.05); }
    h1 { color: #3D405B; text-align: center; }
    .subtitle { color: #81B29A; text-align: center; font-weight: 600; }
    .card { background: white; padding: 18px; border-radius: 20px; box-shadow: 0 8px 25px rgba(0,0,0,0.08); }
</style>
""", unsafe_allow_html=True)

# ===================== DISTANCIA =====================
def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return round(6371 * c, 2)

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
            body = "¡Bienvenido a la comunidad!"
        elif tipo == "publicacion_aprobada":
            nombre = datos.get('nombre', 'tu mascota')
            msg['Subject'] = f"✅ {nombre} ya está visible"
            body = f"Tu publicación de {nombre} fue aprobada."
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
    st.caption("Comunidad de Mascotas de Neuquén Capital")
    tab1, tab2 = st.tabs(["🔑 Iniciar Sesión", "📝 Registrarse"])
    
    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Contraseña", type="password", key="login_pass")
        if st.button("Iniciar Sesión", type="primary"):
            conn = get_db_connection()
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            conn.close()
            if user and user['hashed_password'] == hash_password(password) and user['is_approved']:
                st.session_state.user = dict(user)
                st.rerun()
            elif user and not user['is_approved']:
                st.warning("Tu cuenta está pendiente de aprobación")
            else:
                st.error("Credenciales incorrectas")
    
    with tab2:
        email_r = st.text_input("Email", key="reg_email")
        tel = st.text_input("WhatsApp", key="reg_tel")
        pass_r = st.text_input("Contraseña", type="password", key="reg_pass")
        if st.button("Solicitar Acceso", type="primary"):
            conn = get_db_connection()
            if conn.execute("SELECT id FROM users WHERE email=?", (email_r,)).fetchone():
                st.error("El email ya está registrado")
            else:
                hashed = hash_password(pass_r)
                conn.execute("INSERT INTO users (email, hashed_password, telefono) VALUES (?, ?, ?)",
                           (email_r, hashed, tel))
                conn.commit()
                conn.close()
                st.success("✅ Solicitud enviada!")

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
        st.title("🐾 Mascotas cerca tuyo")
        location = streamlit_geolocation()
        user_lat = user_lng = None
        if location and location.get('latitude'):
            user_lat = location['latitude']
            user_lng = location['longitude']
            st.success(f"📍 Ubicación detectada")
            m = folium.Map(location=[user_lat, user_lng], zoom_start=15)
            folium.Marker([user_lat, user_lng], popup="📍 Vos", icon=folium.Icon(color="blue")).add_to(m)
        else:
            user_lat, user_lng = -38.951, -68.059
            m = folium.Map(location=[user_lat, user_lng], zoom_start=13)

        col1, col2, col3 = st.columns([2,2,1])
        with col1: search = st.text_input("Buscar nombre o barrio")
        with col2: especie_filter = st.selectbox("Especie", ["Todos", "perro", "gato", "otro"])
        with col3: max_dist = st.slider("Distancia máx (km)", 1, 30, 10)

        conn = get_db_connection()
        pets = conn.execute("SELECT * FROM pets WHERE is_approved = 1").fetchall()
        conn.close()

        filtered = []
        for p in pets:
            if user_lat and user_lng:
                dist = haversine(user_lat, user_lng, p['latitud'], p['longitud'])
                if dist <= max_dist:
                    filtered.append((p, dist))
            else:
                filtered.append((p, None))

        if user_lat and user_lng:
            filtered.sort(key=lambda x: x[1] if x[1] is not None else 999)

        for p, dist in filtered:
            color = "red" if p["status"] == "perdido" else "green"
            popup = f"<b>{p['name']}</b><br>{p['especie']} • {p['barrio']}"
            if dist is not None:
                popup += f"<br>📍 {dist} km de ti"
            folium.Marker([p["latitud"], p["longitud"]], popup=popup, icon=folium.Icon(color=color, icon="paw")).add_to(m)
        
        st_folium(m, width=800, height=550)

    # ===================== NUEVA PUBLICACIÓN =====================
    elif page == "📸 Nueva Publicación":
        st.title("📸 Nueva Publicación")
        st.caption("Contanos sobre la mascota 🐾")
        with st.form("upload_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Nombre de la mascota *")
                especie = st.selectbox("Especie", ["perro", "gato", "otro"])
                raza = st.text_input("Raza (opcional)")
                edad = st.text_input("Edad aproximada")
            with col2:
                status = st.selectbox("Estado", ["perdido", "adopcion"])
                barrio = st.text_input("Barrio *")
                lat = st.number_input("Latitud", value=-38.951, format="%.6f")
                lng = st.number_input("Longitud", value=-68.059, format="%.6f")
            
            # Botón Geolocalización
            if st.button("📍 Usar mi ubicación actual"):
                loc = streamlit_geolocation()
                if loc and loc.get('latitude'):
                    st.session_state.temp_lat = loc['latitude']
                    st.session_state.temp_lng = loc['longitude']
                    st.success("✅ Ubicación capturada!")
                    st.rerun()

            if 'temp_lat' in st.session_state:
                lat = st.session_state.temp_lat
                lng = st.session_state.temp_lng

            descripcion = st.text_area("Descripción / Comentarios", height=100)
            
            col3, col4 = st.columns(2)
            with col3:
                necesita_medicacion = st.checkbox("Necesita medicación")
                esta_herido = st.checkbox("Está herido")
            with col4:
                estado_resguardo = st.selectbox("Estado de resguardo", ["calle", "en tránsito", "veterinaria", "rescatado"])
            
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
                         edad, raza, necesita_medicacion, esta_herido, estado_resguardo)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (user['id'], name, especie, status, barrio, descripcion, lat, lng, image_url, 
                         datetime.now().isoformat(), edad, raza, int(necesita_medicacion), int(esta_herido), estado_resguardo))
                    conn.commit()
                    conn.close()
                    st.success("✅ Reporte enviado correctamente!")
                    if 'temp_lat' in st.session_state:
                        del st.session_state.temp_lat
                        del st.session_state.temp_lng
                    st.rerun()

    # ===================== MIS REPORTES =====================
    elif page == "Mis Reportes":
        st.title("Mis Publicaciones")
        conn = get_db_connection()
        my_pets = conn.execute("SELECT * FROM pets WHERE user_id = ?", (user['id'],)).fetchall()
        conn.close()
        
        for p in my_pets:
            col1, col2 = st.columns([1, 5])
            with col1:
                st.image(p["image_url"], width=120)
            with col2:
                st.subheader(p["name"])
                st.caption(f"{p['especie']} • {p['barrio']} • {p['status']}")
                st.write(p.get('descripcion', ''))
            if st.button("✏️ Editar", key=f"edit_my_{p['id']}"):
                st.session_state.edit_pet = p
                st.rerun()
            if st.button("🗑 Eliminar", key=f"del_my_{p['id']}"):
                conn = get_db_connection()
                conn.execute("DELETE FROM pets WHERE id = ?", (p['id'],))
                conn.commit()
                conn.close()
                st.success("Eliminado")
                st.rerun()

        if 'edit_pet' in st.session_state:
            p = st.session_state.edit_pet
            st.subheader(f"Editando: {p['name']}")
            with st.form("edit_form"):
                new_name = st.text_input("Nombre", value=p['name'])
                new_especie = st.selectbox("Especie", ["perro", "gato", "otro"])
                new_status = st.selectbox("Estado", ["perdido", "adopcion"])
                new_barrio = st.text_input("Barrio", value=p['barrio'])
                new_desc = st.text_area("Descripción", value=p.get('descripcion', ''))
                if st.form_submit_button("Guardar Cambios"):
                    conn = get_db_connection()
                    conn.execute("""UPDATE pets SET name=?, especie=?, status=?, barrio=?, descripcion=? WHERE id=?""",
                               (new_name, new_especie, new_status, new_barrio, new_desc, p['id']))
                    conn.commit()
                    conn.close()
                    st.success("Cambios guardados")
                    del st.session_state.edit_pet
                    st.rerun()

    # ===================== PANEL ADMIN =====================
    elif page == "🛠 Panel Admin" and user.get('role') == 'admin':
        st.title("🛠 Panel de Administración Total")
        tab1, tab2, tab3 = st.tabs(["👥 Usuarios", "🐾 Mascotas", "📊 Estadísticas"])

        with tab1:
            st.subheader("Gestión de Usuarios")
            conn = get_db_connection()
            users = conn.execute("SELECT * FROM users").fetchall()
            conn.close()
            for u in users:
                col1, col2, col3 = st.columns([3,2,2])
                with col1: st.write(f"**{u['email']}**")
                with col2: st.write("✅ Aprobado" if u['is_approved'] else "⏳ Pendiente")
                with col3:
                    if not u['is_approved']:
                        if st.button("Aprobar", key=f"u_{u['id']}"):
                            conn = get_db_connection()
                            conn.execute("UPDATE users SET is_approved=1 WHERE id=?", (u['id'],))
                            conn.commit()
                            conn.close()
                            enviar_mail(u['email'], "cuenta_aprobada")
                            st.success("Usuario aprobado")
                            st.rerun()

        with tab2:
            st.subheader("Gestión de Mascotas")
            search = st.text_input("Buscar mascota o barrio")
            conn = get_db_connection()
            pets = conn.execute("SELECT p.*, u.email as user_email FROM pets p LEFT JOIN users u ON p.user_id = u.id").fetchall()
            conn.close()
            for p in pets:
                col1, col2, col3 = st.columns([1,5,2])
                with col1: st.image(p["image_url"], width=100)
                with col2: st.write(f"**{p['name']}** - {p['barrio']}")
                with col3:
                    if not p['is_approved']:
                        if st.button("✅ Aprobar", key=f"apr_{p['id']}"):
                            conn = get_db_connection()
                            conn.execute("UPDATE pets SET is_approved=1 WHERE id=?", (p['id'],))
                            conn.commit()
                            conn.close()
                            enviar_mail(p['user_email'], "publicacion_aprobada", {"nombre": p['name']})
                            st.success("Aprobado")
                            st.rerun()
                    if st.button("🗑 Eliminar", key=f"del_{p['id']}"):
                        if st.checkbox("Confirmar", key=f"conf_{p['id']}"):
                            conn = get_db_connection()
                            conn.execute("DELETE FROM pets WHERE id=?", (p['id'],))
                            conn.commit()
                            conn.close()
                            st.success("Eliminado")
                            st.rerun()

        with tab3:
            conn = get_db_connection()
            stats = {
                "usuarios": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
                "mascotas": conn.execute("SELECT COUNT(*) FROM pets").fetchone()[0],
                "aprobadas": conn.execute("SELECT COUNT(*) FROM pets WHERE is_approved=1").fetchone()[0],
                "pendientes": conn.execute("SELECT COUNT(*) FROM pets WHERE is_approved=0").fetchone()[0]
            }
            conn.close()
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Usuarios", stats["usuarios"])
            col2.metric("Publicaciones", stats["mascotas"])
            col3.metric("Aprobadas", stats["aprobadas"])
            col4.metric("Pendientes", stats["pendientes"])

st.caption("Huellitas NQN - Neuquén Capital ❤️ Desarrollado por André Beloqui")
