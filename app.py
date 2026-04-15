import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import hashlib
import base64
from datetime import datetime
from PIL import Image
import io

# ===================== CONFIGURACIÓN Y ESTÉTICA PREMIUM =====================
st.set_page_config(page_title="Pet Neuquén", layout="wide", page_icon="🐾", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .stApp { background: linear-gradient(180deg, #f8f9fa 0%, #e6f0e8 100%); }
    .main-header { font-size: 42px; font-weight: 700; color: #1a3c34; text-align: center; margin-bottom: 10px; }
    .sub-header { font-size: 24px; color: #ff6b4a; text-align: center; margin-bottom: 30px; }
    .pet-card { background: white; border-radius: 20px; padding: 15px; box-shadow: 0 8px 25px rgba(0,0,0,0.08); transition: all 0.3s; }
    .pet-card:hover { transform: translateY(-8px); box-shadow: 0 15px 35px rgba(255,107,74,0.2); }
    .badge { padding: 6px 14px; border-radius: 50px; font-size: 13px; font-weight: 700; color: white; }
    .badge-disponible { background: #00c853; }
    .badge-adoptado { background: #ff9800; }
    .wa-button { background: #25D366; color: white; padding: 14px; border-radius: 12px; text-align: center; font-weight: bold; text-decoration: none; display: block; margin-top: 10px; }
    .stat-card { background: white; padding: 20px; border-radius: 18px; text-align: center; box-shadow: 0 6px 20px rgba(0,0,0,0.07); }
    </style>
    """, unsafe_allow_html=True)

# ===================== UTILIDADES =====================
def get_db_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def img_to_base64(image_file):
    img = Image.open(image_file)
    img.thumbnail((700, 500))
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# ===================== SESIÓN =====================
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "username": None, "full_name": "Invitado", "rol": None})

# ===================== LOGIN =====================
def vista_login():
    st.title("🔐 Bienvenido a Pet Neuquén")
    tab1, tab2 = st.tabs(["Ingresar", "Registrarse como Voluntario"])
    conn = get_db_connection()

    with tab1:
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.button("Entrar", use_container_width=True, type="primary"):
            df = conn.read(ttl=0)
            if not df.empty and 'username' in df.columns:
                user_row = df[(df['username'] == u) & (df['password'] == hash_password(p))]
                if not user_row.empty:
                    if user_row.iloc[0]['estado_usuario'] == 'aprobado':
                        st.session_state.update({
                            "logged_in": True, "username": u,
                            "full_name": user_row.iloc[0]['contacto_nombre'],
                            "rol": user_row.iloc[0].get('rol', 'voluntario')
                        })
                        st.success(f"¡Bienvenido de nuevo, {st.session_state.full_name}! 🐾")
                        st.rerun()
                    else:
                        st.warning("Tu cuenta aún está pendiente de aprobación.")
                else:
                    st.error("Usuario o contraseña incorrectos.")

    with tab2:
        with st.form("registro"):
            new_u = st.text_input("Nombre de usuario *")
            new_n = st.text_input("Nombre completo *")
            new_p = st.text_input("Contraseña *", type="password")
            new_t = st.text_input("WhatsApp (sin +54) *")
            if st.form_submit_button("Enviar solicitud"):
                if new_u and new_n and new_p and new_t:
                    df = conn.read(ttl=0)
                    if new_u in df['username'].values:
                        st.error("Ese usuario ya existe")
                    else:
                        new_row = pd.DataFrame([{
                            "tipo": "usuario", "username": new_u, "password": hash_password(new_p),
                            "contacto_nombre": new_n, "contacto_tel": new_t, "rol": "voluntario",
                            "estado_usuario": "pendiente", "estado_adopcion": "SISTEMA"
                        }])
                        conn.update(data=pd.concat([df, new_row], ignore_index=True))
                        st.success("✅ Solicitud enviada. Te avisaremos cuando estés aprobado.")

# ===================== INICIO - CON BÚSQUEDA AVANZADA =====================
def vista_inicio():
    st.markdown('<h1 class="main-header">🐾 Pet Neuquén</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Adopciones con amor en Neuquén</p>', unsafe_allow_html=True)

    conn = get_db_connection()
    df = conn.read(ttl=0)
    df_pets = df[(df.get('tipo') == 'mascota') & (df.get('estado_adopcion') == 'disponible')]

    # Estadísticas bonitas
    c1, c2, c3 = st.columns(3)
    c1.metric("🐶 En adopción", len(df_pets))
    c2.metric("❤️ Adoptadas", len(df[df.get('estado_adopcion') == 'adoptado']))
    c3.metric("👥 Voluntarios", len(df[df.get('tipo') == 'usuario']))

    # Búsqueda avanzada
    st.subheader("🔎 Buscá tu nuevo mejor amigo")
    col1, col2, col3, col4 = st.columns([3,1,1,1])
    with col1:
        search = st.text_input("Nombre o descripción", placeholder="Ej: Luna, juguetón...")
    with col2:
        edad_min, edad_max = st.slider("Edad (años)", 0, 15, (0, 15))
    with col3:
        especie = st.selectbox("Especie", ["Todas", "Perro", "Gato", "Otro"])
    with col4:
        tamano = st.selectbox("Tamaño", ["Todos", "Pequeño", "Mediano", "Grande"])

    # Aplicar filtros
    if search:
        df_pets = df_pets[df_pets['nombre_mascota'].str.contains(search, case=False, na=False) |
                         df_pets['descripcion'].str.contains(search, case=False, na=False)]
    df_pets = df_pets[(df_pets['edad'] >= edad_min) & (df_pets['edad'] <= edad_max)]
    if especie != "Todas": df_pets = df_pets[df_pets['especie'] == especie]
    if tamano != "Todos": df_pets = df_pets[df_pets['tamano'] == tamano]

    # Galería hermosa
    if df_pets.empty:
        st.info("😔 No encontramos mascotas con esos filtros.")
    else:
        cols = st.columns(3)
        for i, (_, pet) in enumerate(df_pets.iterrows()):
            with cols[i % 3]:
                st.markdown('<div class="pet-card">', unsafe_allow_html=True)
                if pet['imagen_base64']:
                    st.image(f"data:image/png;base64,{pet['imagen_base64']}", use_column_width=True)
                st.subheader(pet['nombre_mascota'])
                st.caption(f"{pet['especie']} • {pet['edad']} años • {pet['tamano']} • {pet['sexo']}")
                st.write(pet['descripcion'][:110] + "..." if len(str(pet.get('descripcion', ''))) > 110 else pet.get('descripcion', ''))
                wa_link = f"https://wa.me/54{pet.get('contacto_tel', '')}?text=Hola! Me enamoré de {pet['nombre_mascota']} ❤️"
                st.markdown(f'<a href="{wa_link}" target="_blank" class="wa-button">💬 Contactar por WhatsApp</a>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

# ===================== HISTORIAS DE ÉXITO =====================
def vista_exitos():
    st.title("🏆 Historias que nos llenan el corazón")
    conn = get_db_connection()
    df = conn.read(ttl=0)
    df_exitos = df[(df.get('tipo') == 'mascota') & (df.get('estado_adopcion') == 'adoptado')]

    for _, pet in df_exitos.iterrows():
        st.markdown(f'<div class="pet-card"><h3>🎉 {pet["nombre_mascota"]} ya tiene su hogar feliz!</h3>', unsafe_allow_html=True)
        if pet.get('imagen_base64'):
            st.image(f"data:image/png;base64,{pet['imagen_base64']}", width=500)
        st.write(pet.get('historia_exito', 'Adoptado con mucho amor ❤️'))
        st.divider()

# ===================== PUBLICAR MASCOTA =====================
def vista_subir_mascota():
    st.title("📸 Publicar nueva mascota")
    conn = get_db_connection()
    with st.form("subir"):
        nombre = st.text_input("Nombre de la mascota *")
        especie = st.selectbox("Especie", ["Perro", "Gato", "Otro"])
        edad = st.number_input("Edad (años)", 0, 20, 2)
        tamano = st.selectbox("Tamaño", ["Pequeño", "Mediano", "Grande"])
        sexo = st.selectbox("Sexo", ["Macho", "Hembra"])
        desc = st.text_area("Descripción")
        foto = st.file_uploader("Foto", type=["png","jpg","jpeg"])
        if st.form_submit_button("Publicar", type="primary") and nombre and foto:
            img_b64 = img_to_base64(foto)
            new_pet = pd.DataFrame([{
                "tipo": "mascota", "username": st.session_state.username,
                "contacto_nombre": st.session_state.full_name,
                "contacto_tel": None, "estado_adopcion": "disponible",
                "nombre_mascota": nombre, "especie": especie, "edad": edad,
                "descripcion": desc, "tamano": tamano, "sexo": sexo,
                "imagen_base64": img_b64, "fecha_publicacion": datetime.now().strftime("%Y-%m-%d")
            }])
            df = conn.read(ttl=0)
            conn.update(data=pd.concat([df, new_pet], ignore_index=True))
            st.success("¡Mascota publicada! 🎉")
            st.rerun()

# ===================== MODERACIÓN ADMIN =====================
def vista_moderacion():
    st.title("🛡️ Panel de Moderación - Admin")
    conn = get_db_connection()
    df = conn.read(ttl=0)

    st.subheader("Solicitudes de Voluntarios pendientes")
    pendientes = df[(df.get('tipo') == 'usuario') & (df.get('estado_usuario') == 'pendiente')]
    if pendientes.empty:
        st.success("No hay solicitudes pendientes")
    else:
        for i, row in pendientes.iterrows():
            col1, col2, col3 = st.columns([3,1,1])
            with col1:
                st.write(f"**{row['contacto_nombre']}** (@{row['username']}) - {row['contacto_tel']}")
            with col2:
                if st.button("✅ Aprobar", key=f"apr{i}"):
                    df.loc[i, 'estado_usuario'] = 'aprobado'
                    conn.update(data=df)
                    st.success("Aprobado")
                    st.rerun()
            with col3:
                if st.button("❌ Rechazar", key=f"rej{i}"):
                    df = df.drop(i)
                    conn.update(data=df)
                    st.success("Rechazado")
                    st.rerun()

    st.subheader("Mascotas publicadas")
    mascotas = df[df.get('tipo') == 'mascota']
    for i, row in mascotas.iterrows():
        col1, col2 = st.columns([4,2])
        with col1:
            st.write(f"{row['nombre_mascota']} - {row.get('estado_adopcion')}")
        with col2:
            if st.button("Marcar como Adoptado", key=f"ad{i}"):
                df.loc[i, 'estado_adopcion'] = 'adoptado'
                df.loc[i, 'historia_exito'] = st.text_input("Historia de adopción", key=f"h{i}")
                conn.update(data=df)
                st.rerun()

# ===================== NAVEGACIÓN =====================
st.sidebar.title("🐾 Pet Neuquén")
if st.session_state.logged_in:
    st.sidebar.success(f"Hola {st.session_state.full_name}")
    opciones = ["Inicio", "Historias de Éxito", "Publicar Mascota", "Mis Publicaciones"]
    if st.session_state.rol == "admin" or st.session_state.username == "admin":
        opciones.append("🛡️ Moderación")
    nav = st.sidebar.radio("Menú", opciones)
    if st.sidebar.button("Cerrar sesión"):
        st.session_state.clear()
        st.rerun()
else:
    nav = st.sidebar.radio("Navegación", ["Inicio", "Historias de Éxito", "Login"])

if nav == "Inicio": vista_inicio()
elif nav == "Historias de Éxito": vista_exitos()
elif nav == "Login": vista_login()
elif nav == "Publicar Mascota": vista_subir_mascota()
elif nav == "Mis Publicaciones": st.info("Mis publicaciones (próximamente)")
elif nav == "🛡️ Moderación": vista_moderacion()

st.caption("❤️ Hecho con amor para las mascotas de Neuquén")
