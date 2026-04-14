import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import hashlib
import base64
from datetime import datetime
from PIL import Image
import io

# ===================== CONFIGURACIÓN Y ESTILO =====================
st.set_page_config(page_title="Pet Neuquén Pro", layout="wide", page_icon="🐾")

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    .badge {
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: bold;
        color: white;
        margin-right: 5px;
        display: inline-block;
    }
    .badge-urgente { background-color: #ff4b4b; }
    .badge-nuevo { background-color: #007bff; }
    .stat-card {
        background-color: white;
        padding: 25px;
        border-radius: 15px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border: 1px solid #eee;
    }
    .stat-card h3 { margin: 0; color: #ff4b4b; font-size: 40px; }
    .stat-card p { margin: 0; color: #444; font-weight: 600; font-size: 18px; }
    .wa-button {
        background-color: #25D366;
        color: white !important;
        padding: 12px;
        border-radius: 10px;
        text-decoration: none;
        display: block;
        text-align: center;
        font-weight: bold;
        margin-top: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# ===================== CONEXIÓN A DB =====================
def get_db_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def img_to_base64(image_file):
    img = Image.open(image_file)
    img.thumbnail((600, 450))
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "username": None, "full_name": "Invitado"})

# ===================== VISTAS =====================

def vista_login():
    st.title("🔐 Acceso a la Comunidad")
    tab1, tab2 = st.tabs(["Ingresar", "Registrarse como Voluntario"])
    conn = get_db_connection()
    
    with tab1:
        u = st.text_input("Usuario", key="login_u")
        p = st.text_input("Contraseña", type="password", key="login_p")
        if st.button("Entrar", use_container_width=True):
            df = conn.read(ttl=0)
            # Buscamos en las columnas de usuario (asumiendo que las creaste en el Sheet)
            if not df.empty and 'username' in df.columns:
                user_row = df[(df['username'] == u) & (df['password'] == hash_password(p))]
                if not user_row.empty:
                    if user_row.iloc[0]['estado_usuario'] == 'aprobado':
                        st.session_state.update({"logged_in": True, "username": u, "full_name": user_row.iloc[0]['contacto_nombre']})
                        st.success(f"Bienvenido {u}")
                        st.rerun()
                    else:
                        st.warning("Tu cuenta está pendiente de aprobación por el administrador.")
                else:
                    st.error("Usuario o contraseña incorrectos.")
            else:
                # Login de emergencia para el primer admin
                if u == "admin" and p == "admin123":
                    st.session_state.update({"logged_in": True, "username": "admin", "full_name": "Admin Principal"})
                    st.rerun()

    with tab2:
        with st.form("registro_voluntario"):
            new_u = st.text_input("Elegí un nombre de usuario *")
            new_n = st.text_input("Nombre completo *")
            new_p = st.text_input("Contraseña *", type="password")
            new_t = st.text_input("WhatsApp de contacto *")
            submit = st.form_submit_button("Enviar Solicitud de Registro")
            
            if submit:
                if new_u and new_p and new_n and new_t:
                    df = conn.read(ttl=0)
                    # Creamos la fila del nuevo usuario
                    new_user = pd.DataFrame([{
                        "username": new_u,
                        "password": hash_password(new_p),
                        "contacto_nombre": new_n,
                        "contacto_tel": new_t,
                        "rol": "voluntario",
                        "estado_usuario": "pendiente", # El admin debe cambiar esto a 'aprobado' en el Excel
                        "estado_adopcion": "SISTEMA" # Marca para ignorar en la galería
                    }])
                    updated_df = pd.concat([df, new_user], ignore_index=True)
                    conn.update(data=updated_df)
                    st.success("✅ Solicitud enviada. El administrador te habilitará pronto.")
                else:
                    st.error("Por favor completá todos los campos.")

# ===================== RESTO DE FUNCIONES (INICIO, SUBIR, EXITOS) =====================
# (Aquí van las funciones vista_inicio, vista_exitos, vista_subir_mascota que ya teníamos)
# ... [Omitido por brevedad para no repetir 300 líneas, pero mantenelas igual] ...

def vista_inicio():
    st.title("🐾 Portal de Adopciones Pet Neuquén")
    conn = get_db_connection()
    df = conn.read(ttl=0)
    # IMPORTANTE: Filtrar para que no aparezcan los "usuarios" en la galería
    df_pets = df[df['estado_adopcion'].isin(['disponible', 'adoptado'])]
    
    # ... Lógica de Dashboard y Galería usando df_pets ...

# ===================== NAVEGACIÓN =====================
st.sidebar.title("Pet Neuquén")
if st.session_state.logged_in:
    st.sidebar.info(f"Hola, {st.session_state.full_name}")
    nav = st.sidebar.radio("Menú", ["Inicio", "Historias de Éxito", "Publicar Mascota", "Mis Publicaciones"])
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.clear()
        st.rerun()
else:
    nav = st.sidebar.radio("Navegación", ["Inicio", "Historias de Éxito", "Login"])

if nav == "Inicio": vista_inicio()
elif nav == "Historias de Éxito": vista_exitos()
elif nav == "Login": vista_login()
elif nav == "Publicar Mascota": vista_subir_mascota()
elif nav == "Mis Publicaciones": vista_gestion_usuario()
