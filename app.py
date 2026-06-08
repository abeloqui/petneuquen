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
from database import get_db_connection

st.set_page_config(page_title="Huellitas NQN", layout="wide", page_icon="🐾")

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
        
        if tipo == "bienvenida":
            msg['Subject'] = "¡Bienvenido a Huellitas NQN! 🐾"
            body = "Tu cuenta está en revisión. Te avisaremos cuando esté aprobada."
        elif tipo == "cuenta_aprobada":
            msg['Subject'] = "¡Cuenta Activada! Ya podés ayudar 🐶"
            body = "Tu cuenta fue aprobada. ¡Bienvenido!"
        elif tipo == "publicacion_exitosa":
            msg['Subject'] = f"Recibimos el reporte de {datos.get('nombre', 'la mascota')}"
            body = "¡Gracias! Tu publicación pronto estará visible."
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
        st.error(f"Error enviando mail: {e}")
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
            st.warning("Tu cuenta aún está pendiente de aprobación.")
            return None
    return None

# ===================== MAIN APP =====================
if 'user' not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    tab1, tab2 = st.tabs(["Iniciar Sesión", "Registrarse"])
    
    with tab1:
        email = st.text_input("Email")
        password = st.text_input("Contraseña", type="password")
        if st.button("Entrar"):
            user = login_user(email, password)
            if user:
                st.session_state.user = user
                st.rerun()
    
    with tab2:
        email_r = st.text_input("Email", key="reg_email")
        tel = st.text_input("WhatsApp")
        pass_r = st.text_input("Contraseña", type="password", key="reg_pass")
        if st.button("Solicitar Acceso"):
            conn = get_db_connection()
            if conn.execute("SELECT id FROM users WHERE email=?", (email_r,)).fetchone():
                st.error("El email ya existe")
            else:
                hashed = hash_password(pass_r)
                conn.execute("INSERT INTO users (email, hashed_password, telefono) VALUES (?, ?, ?)",
                           (email_r, hashed, tel))
                conn.commit()
                conn.close()
                enviar_mail(email_r, "bienvenida")
                st.success("¡Solicitud enviada! Esperá la aprobación.")
else:
    user = st.session_state.user
    st.sidebar.success(f"👋 {user['email']}")
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.user = None
        st.rerun()
    
    # ===================== NAVEGACIÓN =====================
    page = st.sidebar.radio("Ir a", ["Mapa Principal", "Nueva Publicación", "Mis Reportes", "Admin"] if user.get('role') == 'admin' else ["Mapa Principal", "Nueva Publicación", "Mis Reportes"])

    if page == "Mapa Principal":
        st.title("🐾 Huellitas NQN - Neuquén")
        
        conn = get_db_connection()
        pets = conn.execute("SELECT * FROM pets WHERE is_approved = 1").fetchall()
        conn.close()
        
        m = folium.Map(location=[-38.95, -68.06], zoom_start=13)
        
        for p in pets:
            color = "red" if p["status"] == "perdido" else "green"
            folium.Marker(
                [p["latitud"], p["longitud"]],
                popup=f"<b>{p['name']}</b><br>{p['barrio']}",
                icon=folium.Icon(color=color)
            ).add_to(m)
        
        st_folium(m, width=700, height=500)
        
        # Lista de mascotas
        for p in pets:
            col1, col2 = st.columns([1, 3])
            with col1:
                st.image(p["image_url"], use_column_width=True)
            with col2:
                st.subheader(p["name"])
                st.caption(f"{p['especie']} • {p['barrio']}")
                if p["descripcion"]:
                    st.write(p["descripcion"][:150] + "...")
                st.markdown(f"📞 [WhatsApp](https://wa.me/{user.get('telefono', '2996894360')})")

    elif page == "Nueva Publicación":
        st.title("📸 Nueva Publicación")
        
        with st.form("upload_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Nombre de la mascota")
                especie = st.selectbox("Especie", ["perro", "gato", "otro"])
            with col2:
                status = st.selectbox("Estado", ["perdido", "adopcion"])
                barrio = st.text_input("Barrio")
            
            descripcion = st.text_area("Descripción", placeholder="Collar, comportamiento, etc...")
            
            col3, col4 = st.columns(2)
            with col3:
                lat = st.number_input("Latitud", value=-38.95)
                lng = st.number_input("Longitud", value=-68.06)
            
            file = st.file_uploader("Foto", type=["jpg", "png", "jpeg"])
            
            if st.form_submit_button("Publicar 🐾"):
                if file:
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
                    st.success("¡Reporte enviado! Esperá aprobación.")
                    st.rerun()

    elif page == "Mis Reportes":
        st.title("Mis Publicaciones")
        conn = get_db_connection()
        my_pets = conn.execute("SELECT * FROM pets WHERE user_id = ?", (user['id'],)).fetchall()
        conn.close()
        
        for p in my_pets:
            col1, col2 = st.columns([1, 4])
            with col1:
                st.image(p["image_url"], width=120)
            with col2:
                st.subheader(p["name"])
                st.caption(f"{p['status']} • {p['barrio']}")
                st.write("✅ Aprobado" if p["is_approved"] else "⏳ Pendiente")
    
    elif page == "Admin" and user.get('role') == 'admin':
        st.title("Panel de Administración")
        # (puedes expandir esto con tabs para usuarios y mascotas pendientes)

st.caption("Huellitas NQN © 2026 - Hecho con ❤️ para Neuquén")
