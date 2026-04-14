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

# ===================== CONEXIÓN A BASE DE DATOS (NUBE) =====================
def get_db_connection():
    # Conexión a Google Sheets
    return st.connection("gsheets", type=GSheetsConnection)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def img_to_base64(image_file):
    img = Image.open(image_file)
    img.thumbnail((600, 450))
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# ===================== ESTADO DE SESIÓN =====================
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "username": None, "full_name": "Invitado"})

# ===================== VISTAS =====================

def vista_inicio():
    st.title("🐾 Portal de Adopciones Pet Neuquén")
    conn = get_db_connection()
    
    try:
        df = conn.read(ttl=0)
    except:
        st.error("Error al conectar con la base de datos. Verifica la configuración de Google Sheets.")
        return

    # --- DASHBOARD SIMPLIFICADO ---
    col_a, col_b = st.columns(2)
    with col_a:
        count_disp = len(df[df["estado_adopcion"]=="disponible"]) if not df.empty else 0
        st.markdown(f'<div class="stat-card"><h3>{count_disp}</h3><p>Buscan Hogar</p></div>', unsafe_allow_html=True)
    with col_b:
        count_adopt = len(df[df["estado_adopcion"]=="adoptado"]) if not df.empty else 0
        st.markdown(f'<div class="stat-card"><h3>{count_adopt}</h3><p>Adoptados</p></div>', unsafe_allow_html=True)

    st.markdown("---")

    # --- FILTROS ---
    with st.expander("🔍 Filtrar búsqueda"):
        f1, f2 = st.columns(2)
        esp_f = f1.multiselect("Especie", ["Perro", "Gato", "Otro"], default=["Perro", "Gato", "Otro"])
        solo_urg = f2.toggle("🔥 Mostrar solo casos URGENTES")

    if not df.empty:
        df_view = df[df['estado_adopcion'] == 'disponible']
        if esp_f: df_view = df_view[df_view['especie'].isin(esp_f)]
        if solo_urg: df_view = df_view[df_view['urgente'].astype(int) == 1]

        if df_view.empty:
            st.info("No hay mascotas que coincidan con los filtros.")
        else:
            cols = st.columns(3)
            for i, (_, row) in enumerate(df_view.iterrows()):
                with cols[i % 3]:
                    with st.container(border=True):
                        badges = ""
                        if int(row['urgente']): badges += '<span class="badge badge-urgente">🔥 URGENTE</span>'
                        
                        # Marca de nuevo si es de los últimos 2 días
                        try:
                            fecha_p = datetime.strptime(str(row['fecha_pub']), '%Y-%m-%d').date()
                            if (datetime.now().date() - fecha_p).days <= 2:
                                badges += '<span class="badge badge-nuevo">✨ NUEVO</span>'
                        except: pass
                        
                        st.markdown(badges, unsafe_allow_html=True)
                        if row['foto_base64']:
                            st.markdown(f'<div style="border-radius:12px; overflow:hidden; height:220px; margin:10px 0;"><img src="data:image/png;base64,{row["foto_base64"]}" style="width:100%; height:100%; object-fit:cover;"></div>', unsafe_allow_html=True)
                        
                        st.subheader(row['nombre'])
                        st.caption(f"{row['especie']} • {row['peso_rango']}")
                        
                        with st.expander("📋 Ver detalles y compartir"):
                            st.write(f"🎨 **Color:** {row['color']}")
                            st.write(f"🎂 **Edad:** {row['edad']}")
                            st.write(f"💉 **Vacunas:** {row['vacunado']}")
                            st.write(f"📝 **Historia:** {row['descripcion']}")
                            st.markdown("---")
                            share_msg = f"¡Ayudame a difundir! {row['nombre']} busca hogar. Contacto WhatsApp: {row['contacto_tel']}"
                            st.text_copy_button("🔗 Copiar para compartir", share_msg)
                            tel_num = "".join(filter(str.isdigit, str(row['contacto_tel'])))
                            st.markdown(f'<a href="https://wa.me/{tel_num}" target="_blank" class="wa-button">📱 WhatsApp</a>', unsafe_allow_html=True)

def vista_exitos():
    st.title("🏠 Historias de Éxito")
    conn = get_db_connection()
    df = conn.read(ttl=0)
    if not df.empty:
        df_adoptados = df[df['estado_adopcion'] == 'adoptado']
        if df_adoptados.empty:
            st.info("Aún no tenemos historias registradas.")
        else:
            cols = st.columns(4)
            for i, (_, row) in enumerate(df_adoptados.iterrows()):
                with cols[i % 4]:
                    if row['foto_base64']:
                        st.image(base64.b64decode(row['foto_base64']), use_container_width=True)
                    st.success(f"¡{row['nombre']} ya tiene hogar!")

def vista_subir_mascota():
    st.title("📤 Publicar Mascota")
    conn = get_db_connection()
    
    with st.form("carga_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        nom = c1.text_input("Nombre *")
        esp = c1.selectbox("Especie", ["Perro", "Gato", "Otro"])
        tam = c1.selectbox("Tamaño", ["Pequeño", "Mediano", "Grande"])
        col = c1.text_input("Color")
        
        foto = c2.file_uploader("Foto *", type=['jpg','png','jpeg'])
        tel_w = c2.text_input("WhatsApp contacto *")
        urg = c2.toggle("🔥 ¿Es URGENTE?")
        vac = st.radio("¿Vacunado?", ["Sí", "No", "No se sabe"], horizontal=True)
        
        desc = st.text_area("Descripción")
        
        if st.form_submit_button("🚀 Publicar Ahora"):
            if nom and foto and tel_w:
                img_b = img_to_base64(foto)
                new_data = pd.DataFrame([{
                    "nombre": nom, "especie": esp, "peso_rango": tam, "color": col,
                    "foto_base64": img_b, "contacto_tel": tel_w, "urgente": 1 if urg else 0,
                    "descripcion": desc, "fecha_pub": str(datetime.now().date()),
                    "estado_adopcion": "disponible", "subido_por": st.session_state.username,
                    "contacto_nombre": st.session_state.full_name, "vacunado": vac
                }])
                old_df = conn.read(ttl=0)
                updated_df = pd.concat([old_df, new_data], ignore_index=True)
                conn.update(data=updated_df)
                st.balloons()
                st.success("¡Publicado en la nube!")
            else: st.error("Faltan campos obligatorios.")

def vista_gestion_usuario():
    st.title("🐾 Mis Publicaciones")
    conn = get_db_connection()
    df = conn.read(ttl=0)
    if not df.empty:
        mis_mascotas = df[df['subido_por'] == st.session_state.username]
        if mis_mascotas.empty: st.info("No tienes publicaciones.")
        else:
            for i, row in mis_mascotas.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([1,3,1])
                    if row['foto_base64']: c1.image(base64.b64decode(row['foto_base64']), width=100)
                    c2.subheader(row['nombre'])
                    if row['estado_adopcion'] == 'disponible':
                        if c3.button("🏠 MARCAR ADOPTADO", key=f"btn_{i}"):
                            df.at[i, 'estado_adopcion'] = 'adoptado'
                            conn.update(data=df)
                            st.rerun()
                    else: c3.success("Adoptado")

# ===================== NAVEGACIÓN =====================
st.sidebar.title("Pet Neuquén")
if st.session_state.logged_in:
    st.sidebar.info(f"Usuario: {st.session_state.full_name}")
    nav = st.sidebar.radio("Menú", ["Inicio", "Historias de Éxito", "Publicar Mascota", "Mis Publicaciones"])
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.clear()
        st.rerun()
else:
    nav = st.sidebar.radio("Navegación", ["Inicio", "Historias de Éxito", "Login"])
    if nav == "Login":
        u = st.sidebar.text_input("Usuario")
        p = st.sidebar.text_input("Clave", type="password")
        if st.sidebar.button("Entrar"):
            # Para simplificar con GSheets, puedes validar contra una lista fija o una hoja de usuarios
            if u == "admin" and p == "admin123":
                st.session_state.update({"logged_in": True, "username": u, "full_name": "Administrador"})
                st.rerun()

if nav == "Inicio": vista_inicio()
elif nav == "Historias de Éxito": vista_exitos()
elif nav == "Publicar Mascota": vista_subir_mascota()
elif nav == "Mis Publicaciones": vista_gestion_usuario()
