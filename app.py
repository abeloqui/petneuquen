import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import base64
from datetime import datetime
from PIL import Image
import io

# ===================== CONFIGURACIÓN Y ESTILO PRO =====================
st.set_page_config(page_title="Pet Neuquén Pro", layout="wide", page_icon="🐾")

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    /* Estilo para las Badges */
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
    .badge-adoptado { background-color: #28a745; }
    
    /* Tarjetas de Estadísticas */
    .stat-card {
        background-color: white;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border: 1px solid #eee;
    }
    .stat-card h3 { margin: 0; color: #ff4b4b; font-size: 32px; }
    .stat-card p { margin: 0; color: #666; font-weight: 500; }

    /* Botón de WhatsApp */
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

# ===================== BASE DE DATOS =====================
@st.cache_resource
def get_connection():
    # Usamos un nombre de archivo único para esta versión pro
    return sqlite3.connect('pet_neuquen_v6_pro.db', check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # Tabla Usuarios (con tipo de entidad)
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, 
        nombre TEXT, email TEXT, telefono TEXT, role TEXT, estado TEXT, tipo_entidad TEXT)''')
    
    # Tabla Mascotas (con todos los campos nuevos)
    c.execute('''CREATE TABLE IF NOT EXISTS mascotas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, especie TEXT, edad TEXT, 
        descripcion TEXT, foto_base64 TEXT, contacto_nombre TEXT, contacto_tel TEXT, 
        fecha_pub TEXT, color TEXT, peso_rango TEXT, vacunado TEXT, lista_vacunas TEXT,
        urgente INTEGER DEFAULT 0, estado_adopcion TEXT DEFAULT 'disponible', 
        socia_con TEXT, subido_por TEXT)''')
    
    # Admin por defecto (admin / admin123)
    try:
        admin_pass = hashlib.sha256("admin123".encode()).hexdigest()
        c.execute("INSERT INTO usuarios (username, password, nombre, role, estado, tipo_entidad) VALUES (?,?,?,?,?,?)",
                  ('admin', admin_pass, 'Administrador Central', 'admin', 'aprobado', 'Entidad'))
    except sqlite3.IntegrityError:
        pass
    conn.commit()

init_db()

# ===================== UTILIDADES =====================
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
    st.session_state.update({"logged_in": False, "username": None, "role": None, "full_name": None})

# ===================== VISTAS =====================

def vista_inicio():
    st.title("🐾 Portal de Adopciones Pet Neuquén")
    
    conn = get_connection()
    df_stats = pd.read_sql_query("SELECT estado_adopcion FROM mascotas", conn)
    
    # --- DASHBOARD DE IMPACTO PÚBLICO ---
    s1, s2, s3 = st.columns(3)
    with s1:
        count_disp = len(df_stats[df_stats["estado_adopcion"]=="disponible"])
        st.markdown(f'<div class="stat-card"><h3>{count_disp}</h3><p>Buscan Hogar</p></div>', unsafe_allow_html=True)
    with s2:
        count_adopt = len(df_stats[df_stats["estado_adopcion"]=="adoptado"])
        st.markdown(f'<div class="stat-card"><h3>{count_adopt}</h3><p>Adoptados 🎉</p></div>', unsafe_allow_html=True)
    with s3:
        st.markdown(f'<div class="stat-card"><h3>GMT-3</h3><p>Neuquén, Argentina</p></div>', unsafe_allow_html=True)

    st.markdown("---")

    # --- FILTROS ---
    with st.expander("🔍 Filtrar búsqueda (Tamaño, Especie, Urgencia)"):
        f1, f2, f3 = st.columns(3)
        esp_f = f1.multiselect("Especie", ["Perro", "Gato", "Otro"], default=["Perro", "Gato", "Otro"])
        tam_f = f2.multiselect("Tamaño", ["Mini (0-5kg)", "Pequeño (5-15kg)", "Mediano (15-25kg)", "Grande (+25kg)"])
        solo_urg = f3.toggle("🔥 Mostrar solo casos URGENTES")

    # --- CARGA DE DATOS ---
    df = pd.read_sql_query("SELECT * FROM mascotas WHERE estado_adopcion = 'disponible' ORDER BY urgente DESC, id DESC", conn)
    
    if esp_f: df = df[df['especie'].isin(esp_f)]
    if tam_f: df = df[df['peso_rango'].isin(tam_f)]
    if solo_urg: df = df[df['urgente'] == 1]

    if df.empty:
        st.info("No hay mascotas disponibles con estos filtros en este momento.")
    else:
        cols = st.columns(3)
        for i, (_, row) in enumerate(df.iterrows()):
            with cols[i % 3]:
                with st.container(border=True):
                    # Badges dinámicas
                    badges = ""
                    if row['urgente']: badges += '<span class="badge badge-urgente">🔥 URGENTE</span>'
                    
                    # Lógica para "Nuevo" (Publicado hoy o ayer)
                    fecha_p = datetime.strptime(row['fecha_pub'], '%Y-%m-%d').date()
                    if (datetime.now().date() - fecha_p).days <= 2:
                        badges += '<span class="badge badge-nuevo">✨ NUEVO</span>'
                    
                    st.markdown(badges, unsafe_allow_html=True)

                    if row['foto_base64']:
                        st.markdown(f"""
                            <div style="border-radius: 12px; overflow: hidden; height: 220px; margin: 10px 0;">
                                <img src="data:image/png;base64,{row['foto_base64']}" style="width: 100%; height: 100%; object-fit: cover;">
                            </div>
                        """, unsafe_allow_html=True)
                    
                    st.subheader(row['nombre'])
                    st.write(f"**{row['especie']}** • {row['peso_rango']}")
                    
                    with st.expander("📋 Ver Ficha y Compartir"):
                        st.write(f"🎨 **Color:** {row['color']}")
                        st.write(f"🎂 **Edad:** {row['edad']}")
                        st.write(f"💉 **Vacunas:** {row['vacunado']} ({row['lista_vacunas']})")
                        st.write(f"🤝 **Socia con:** {row['socia_con']}")
                        st.write(f"📝 **Historia:** {row['descripcion']}")
                        
                        st.markdown("---")
                        # VIRALIZACIÓN
                        share_msg = f"¡Ayudame a difundir! {row['nombre']} busca hogar en Pet Neuquén. Info: {row['especie']}, {row['color']}. Contacto: {row['contacto_tel']}"
                        st.text_copy_button("🔗 Copiar info para compartir", share_msg)
                        
                        tel_num = "".join(filter(str.isdigit, str(row['contacto_tel'])))
                        st.markdown(f'<a href="https://wa.me/{tel_num}?text=Hola! Me interesa adoptar a {row['nombre']}" class="wa-button">📱 WhatsApp</a>', unsafe_allow_html=True)

def vista_login():
    st.title("🔐 Acceso Voluntarios")
    t1, t2 = st.tabs(["Ingresar", "Registrarse"])
    
    with t1:
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.button("Entrar", use_container_width=True):
            conn = get_connection()
            user = pd.read_sql_query("SELECT * FROM usuarios WHERE username=? AND password=?", conn, params=(u, hash_password(p)))
            if not user.empty:
                if user.iloc[0]['estado'] == 'aprobado':
                    st.session_state.update({
                        "logged_in": True, "username": u, 
                        "role": user.iloc[0]['role'], "full_name": user.iloc[0]['nombre']
                    })
                    st.rerun()
                else: st.warning("Cuenta pendiente de aprobación.")
            else: st.error("Usuario o clave incorrectos.")

    with t2:
        with st.form("reg_pro"):
            nu = st.text_input("Usuario *")
            np = st.text_input("Clave *", type="password")
            nn = st.text_input("Nombre Completo *")
            nt = st.text_input("WhatsApp (ej: 2991234567) *")
            te = st.selectbox("Tipo de Perfil", ["Particular", "Refugio / Entidad"])
            if st.form_submit_button("Solicitar Registro"):
                if nu and np and nn and nt:
                    try:
                        conn = get_connection()
                        conn.cursor().execute("INSERT INTO usuarios (username, password, nombre, telefono, role, estado, tipo_entidad) VALUES (?,?,?,?,?,?,?)",
                                              (nu, hash_password(np), nn, nt, 'voluntario', 'pendiente', te))
                        conn.commit()
                        st.success("✅ Solicitud enviada al administrador.")
                    except: st.error("El usuario ya existe.")

def vista_subir_mascota():
    st.title("📤 Publicar Mascota")
    
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT telefono FROM usuarios WHERE username=?", (st.session_state.username,))
    tel_perfil = c.fetchone()[0] or ""

    with st.form("carga_pro", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            nom = st.text_input("Nombre de la mascota *")
            esp = st.selectbox("Especie", ["Perro", "Gato", "Otro"])
            tam = st.selectbox("Tamaño", ["Mini (0-5kg)", "Pequeño (5-15kg)", "Mediano (15-25kg)", "Grande (+25kg)"])
            col = st.text_input("Color / Pelaje")
        with col2:
            foto = st.file_uploader("Foto *", type=['jpg','png','jpeg'])
            tel_w = st.text_input("WhatsApp de contacto *", value=tel_perfil)
            urg = st.toggle("🔥 ¿Es un caso URGENTE?")
            socia = st.multiselect("Se lleva bien con:", ["Niños", "Perros", "Gatos", "Cualquier hogar"])
        
        vac = st.radio("¿Vacunado?", ["Sí", "No", "No se sabe"], horizontal=True)
        v_list = []
        if vac == "Sí":
            v_cols = st.columns(3)
            if v_cols[0].checkbox("Antirrábica"): v_list.append("Antirrábica")
            if v_cols[1].checkbox("Sextuple"): v_list.append("Sextuple")
            if v_cols[2].checkbox("Desparasitado"): v_list.append("Desparasitado")
            
        desc = st.text_area("Historia y personalidad")
        
        if st.form_submit_button("🚀 Publicar Ahora"):
            if nom and foto and tel_w:
                img_b = img_to_base64(foto)
                c.execute('''INSERT INTO mascotas 
                    (nombre, especie, peso_rango, color, foto_base64, contacto_tel, urgente, socia_con, descripcion, fecha_pub, subido_por, contacto_nombre, vacunado, lista_vacunas) 
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (nom, esp, tam, col, img_b, tel_w, 1 if urg else 0, ", ".join(socia), desc, datetime.now().date(), st.session_state.username, st.session_state.full_name, vac, ", ".join(v_list)))
                conn.commit()
                st.balloons()
                st.success("¡Publicado! Ya se ve en el inicio.")
            else: st.error("Faltan campos obligatorios.")

def vista_gestion_usuario():
    st.title("🐾 Mis Publicaciones")
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM mascotas WHERE subido_por = ?", conn, params=(st.session_state.username,))
    
    if df.empty: st.info("No tienes publicaciones activas.")
    else:
        for _, row in df.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([1,3,1])
                if row['foto_base64']: c1.image(base64.b64decode(row['foto_base64']), width=100)
                c2.subheader(row['nombre'])
                c2.write(f"Estado: {row['estado_adopcion']}")
                if row['estado_adopcion'] == 'disponible':
                    if c3.button("🏠 ADOPTADO", key=f"btn_{row['id']}"):
                        conn.cursor().execute("UPDATE mascotas SET estado_adopcion = 'adoptado' WHERE id = ?", (row['id'],))
                        conn.commit()
                        st.rerun()

def vista_finales_felices():
    st.title("🏠 Historias con Final Feliz")
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM mascotas WHERE estado_adopcion = 'adoptado' ORDER BY id DESC", conn)
    if df.empty: st.info("Pronto veremos historias aquí.")
    else:
        cols = st.columns(4)
        for i, (_, row) in enumerate(df.iterrows()):
            with cols[i % 4]:
                st.image(base64.b64decode(row['foto_base64']), use_container_width=True)
                st.success(f"¡{row['nombre']} adoptado!")

# ===================== NAVEGACIÓN LATERAL =====================

st.sidebar.markdown("<h1 style='text-align: center;'>🐾</h1>", unsafe_allow_html=True)
st.sidebar.title("Pet Neuquén")

if st.session_state.logged_in:
    st.sidebar.info(f"Usuario: {st.session_state.full_name}")
    opciones = ["Inicio", "Finales Felices", "Publicar Mascota", "Mis Publicaciones"]
    if st.session_state.role == 'admin': opciones.append("Panel Admin")
    
    nav = st.sidebar.radio("Menú", opciones)
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.clear()
        st.rerun()
else:
    nav = st.sidebar.radio("Navegación", ["Inicio", "Finales Felices", "Ingreso Voluntarios"])

# Ruteador Principal
if nav == "Inicio": vista_inicio()
elif nav == "Finales Felices": vista_finales_felices()
elif nav == "Publicar Mascota": vista_subir_mascota()
elif nav == "Mis Publicaciones": vista_gestion_usuario()
elif nav == "Ingreso Voluntarios": vista_login()
elif nav == "Panel Admin":
    st.title("⚙️ Gestión de Usuarios")
    conn = get_connection()
    df_p = pd.read_sql_query("SELECT id, username, nombre, tipo_entidad FROM usuarios WHERE estado='pendiente'", conn)
    st.dataframe(df_p, use_container_width=True)
    uid = st.number_input("ID a aprobar", min_value=1, step=1)
    if st.button("Aprobar Voluntario"):
        conn.cursor().execute("UPDATE usuarios SET estado='aprobado' WHERE id=?", (uid,))
        conn.commit()
        st.rerun()