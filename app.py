"""
CEOP – Visualizador de Levantamiento Estatal
Guerrero · 2026 · Producción v1
Ejecutar: streamlit run app.py
"""
import json
import copy
import time
from datetime import date, datetime, timezone
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium

import streamlit_authenticator as stauth
from streamlit_authenticator.utilities import LoginError

from config import (
    VERDE, VERDE_L, AZUL, AZUL_L, NARANJA, ROJO, AMARILLO, GRIS_BG,
    META_DIA, UMBRAL_AMARILLO, DUR_MIN_MIN, DUR_MAX_MIN,
    META_POR_SECCION, AUTO_REFRESH_SEC, MUNICIPIOS, ESTADO_CENTRO,
    ESTADO_ZOOM, OPCIONES, COORDINADORES, MUNICIPIOS_POR_COORDINADOR,
    TODOS_COORDINADORES, ROLES,
)
from seccion_distrito_lookup import SECCION_DISTRITO, DISTRITOS_POR_MUNICIPIO
from bubble_connector import get_encuestas, normalizar_nombre

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CEOP · Guerrero 2026",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap');
html, body, [class*="css"] {{ font-family: 'IBM Plex Sans', sans-serif; background: {GRIS_BG}; }}
.block-container {{ padding-top: 1.2rem; padding-bottom: 2rem; }}

.ceop-header {{
    background: linear-gradient(120deg, {AZUL} 0%, {AZUL_L} 60%, {VERDE} 100%);
    color: white; padding: 16px 26px; border-radius: 10px;
    display: flex; align-items: center; gap: 18px; margin-bottom: 1.1rem;
}}
.ceop-header h1 {{ margin: 0; font-size: 1.5rem; font-weight: 700; line-height: 1.2; }}
.ceop-header p  {{ margin: 2px 0 0; font-size: 0.82rem; opacity: 0.82; }}

.kpi-card {{
    background: white; border-radius: 9px; padding: 14px 18px;
    border-left: 5px solid {VERDE}; box-shadow: 0 2px 6px rgba(0,0,0,.07);
    height: 100%;
}}
.kpi-val   {{ font-size: 2rem; font-weight: 700; color: {VERDE};
              font-family: 'IBM Plex Mono', monospace; line-height: 1; }}
.kpi-label {{ font-size: 0.73rem; color: #555; text-transform: uppercase;
              letter-spacing:.05em; margin-top:4px; }}
.kpi-sub   {{ font-size: 0.78rem; color: #888; margin-top: 3px; }}
.kpi-card.azul    {{ border-left-color: {AZUL_L}; }}
.kpi-card.azul .kpi-val {{ color: {AZUL_L}; }}
.kpi-card.naranja {{ border-left-color: {NARANJA}; }}
.kpi-card.naranja .kpi-val {{ color: {NARANJA}; }}
.kpi-card.rojo    {{ border-left-color: {ROJO}; }}
.kpi-card.rojo .kpi-val {{ color: {ROJO}; }}

.sec-title {{
    font-size: 1rem; font-weight: 600; color: {AZUL};
    border-bottom: 2px solid {VERDE_L}; padding-bottom: 3px; margin: 16px 0 10px;
}}
.ts-badge {{
    font-size: 0.72rem; color: #888; font-family: 'IBM Plex Mono', monospace;
    background: #eef1f5; border-radius: 4px; padding: 2px 8px; display: inline-block;
}}
section[data-testid="stSidebar"] {{ background: {AZUL}; }}
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] .stMarkdown p {{ color: #B8CDE0 !important; }}
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {{ color: white !important; }}
</style>
""", unsafe_allow_html=True)


# ── Autenticación ──────────────────────────────────────────────────────────────
# streamlit-authenticator intenta escribir en credentials (para registrar intentos
# fallidos), por lo que necesita un dict Python puro — NO el AttrDict de st.secrets
# que es de solo lectura. Convertimos todo a tipos nativos explícitamente.
_raw_users = st.secrets.get("auth", {}).get("credentials", {}).get("usernames", {})
_credentials = {
    "usernames": {
        str(u): {
            "name":     str(data["name"]),
            "password": str(data["password"]),
        }
        for u, data in _raw_users.items()
    }
}
_cookie_name   = str(st.secrets.get("auth", {}).get("cookie_name",        "ceop_session"))
_cookie_key    = str(st.secrets.get("auth", {}).get("cookie_key",         "ceop_dev_key"))
_cookie_expiry = int(st.secrets.get("auth", {}).get("cookie_expiry_days", 1))

authenticator = stauth.Authenticate(
    _credentials,
    _cookie_name,
    _cookie_key,
    _cookie_expiry,
)

try:
    authenticator.login(location="main", key="ceop_login")
except LoginError as e:
    st.error(str(e))
    st.stop()

if not st.session_state.get("authentication_status"):
    if st.session_state.get("authentication_status") is False:
        st.error("Usuario o contraseña incorrectos.")
    else:
        st.info("Ingresa tus credenciales para acceder al visualizador CEOP.")
    st.stop()

# ── Usuario autenticado — determinar rol y municipios permitidos ───────────────
_username         = st.session_state["username"]
_rol_cfg          = ROLES.get(_username, {})
_rol              = _rol_cfg.get("rol", "municipal")
_munis_permitidos = _rol_cfg.get("municipios", [])

# Botón de logout en sidebar
with st.sidebar:
    authenticator.logout(button_name="🔒 Cerrar sesión", location="sidebar", key="ceop_logout")
    st.markdown(f"**{st.session_state.get('name', _username)}**")
    _rol_label = "Coordinador Estatal" if _rol == "estatal" else "Coordinador Municipal"
    st.caption(_rol_label)
    st.markdown("---")


# ── Auto-refresh ───────────────────────────────────────────────────────────────
if "last_refresh" not in st.session_state:
    st.session_state["last_refresh"] = time.time()

if time.time() - st.session_state["last_refresh"] > AUTO_REFRESH_SEC:
    st.session_state["last_refresh"] = time.time()
    st.rerun()


# ── Carga de datos desde Bubble — filtrada por rol en capa de datos ────────────
API_KEY = st.secrets.get("BUBBLE_API_KEY", "3e40b6cbea8e733fe3e6ac89f1f796b5")

@st.cache_data(ttl=AUTO_REFRESH_SEC)
def load_geojson(path_str):
    p = Path(path_str)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))

DATA_DIR = Path(__file__).parent / "data" / "geojsons"

# Rol estatal: pasa None → recibe todos los municipios
# Rol municipal: pasa lista → Bubble filtra en origen
_filtro_munis = None if _rol == "estatal" else _munis_permitidos
df_raw, ultima_actualizacion = get_encuestas(API_KEY, municipios=_filtro_munis)


# ── Helpers ────────────────────────────────────────────────────────────────────
def kpi(col, val, label, sub="", cls=""):
    col.markdown(f"""
    <div class="kpi-card {cls}">
      <div class="kpi-val">{val}</div>
      <div class="kpi-label">{label}</div>
      <div class="kpi-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)

def sem_prod(v):
    if v >= META_DIA:        return "verde"
    if v >= UMBRAL_AMARILLO: return "amarillo"
    return "rojo"

def sem_dur(v):
    if DUR_MIN_MIN <= v <= DUR_MAX_MIN: return "verde"
    if v < DUR_MIN_MIN:                 return "rojo"
    return "amarillo"

def color_prod(val):
    s = sem_prod(val)
    if s == "verde":    return "background-color:#D4EDDA;color:#155724;font-weight:600"
    if s == "amarillo": return "background-color:#FFF3CD;color:#856404;font-weight:600"
    return                     "background-color:#F8D7DA;color:#721C24;font-weight:600"

def color_dur(val):
    s = sem_dur(val)
    if s == "verde":    return "background-color:#D4EDDA;color:#155724;font-weight:600"
    if s == "amarillo": return "background-color:#FFF3CD;color:#856404;font-weight:600"
    return                     "background-color:#F8D7DA;color:#721C24;font-weight:600"

def pct_bar(df_in, campo, titulo, orden=None, colors=None, height=260):
    if df_in[campo].dropna().empty:
        return None
    cnt = df_in[campo].value_counts(normalize=True).mul(100).round(1).reset_index()
    cnt.columns = ["Respuesta", "Porcentaje"]
    if orden:
        cnt["Respuesta"] = pd.Categorical(cnt["Respuesta"], categories=orden, ordered=True)
        cnt = cnt.sort_values("Respuesta")
    cs = colors or [VERDE_L, VERDE, AZUL_L, NARANJA, ROJO, "#aaa"]
    fig = px.bar(cnt, x="Porcentaje", y="Respuesta", orientation="h",
                 color="Respuesta", color_discrete_sequence=cs,
                 text=cnt["Porcentaje"].apply(lambda x: f"{x}%"),
                 title=titulo, height=height)
    fig.update_traces(textposition="outside")
    fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                      showlegend=False, font_family="IBM Plex Sans",
                      margin=dict(t=45, b=5, l=220), xaxis_range=[0, 105])
    return fig

def show_chart(fig, **kwargs):
    if fig:
        st.plotly_chart(fig, use_container_width=True, **kwargs)
    else:
        st.info("Sin datos suficientes para esta gráfica.")


# ── Sidebar — filtros (logout/nombre ya renderizado en bloque de auth) ─────────
with st.sidebar:
    st.markdown("## ⚙️ Filtros globales")
    st.markdown("---")

    # ── Coordinador (solo visible para rol estatal) ────────────────────────────
    bubble_tiene_coordinador = "coordinador" in df_raw.columns and df_raw["coordinador"].notna().any()

    if _rol == "estatal":
        if bubble_tiene_coordinador:
            coords_disponibles = sorted(df_raw["coordinador"].dropna().unique().tolist())
        else:
            coords_disponibles = TODOS_COORDINADORES
        coord_opts = ["Todos los coordinadores"] + coords_disponibles
        coord_sel  = st.selectbox("Coordinador", coord_opts)
    else:
        coord_sel = "Todos los coordinadores"   # municipales: cartera ya restringida en df_raw

    # ── Municipio ──────────────────────────────────────────────────────────────
    # Para roles municipales: el universo de municipios SIEMPRE está limitado
    # a _munis_permitidos — no puede expandirse vía filtro de coordinador.
    if _rol == "municipal":
        munis_con_datos = sorted([
            m for m in df_raw["municipio"].dropna().unique()
            if m in _munis_permitidos
        ])
    elif coord_sel == "Todos los coordinadores":
        munis_con_datos = sorted(df_raw["municipio"].dropna().unique().tolist())
    else:
        if bubble_tiene_coordinador:
            munis_con_datos = sorted(
                df_raw[df_raw["coordinador"] == coord_sel]["municipio"].dropna().unique().tolist()
            )
        else:
            munis_coord     = MUNICIPIOS_POR_COORDINADOR.get(coord_sel, [])
            munis_con_datos = sorted([m for m in df_raw["municipio"].dropna().unique() if m in munis_coord])

    if _rol == "municipal" and len(_munis_permitidos) == 1:
        # Un solo municipio: fijar sin mostrar selectbox
        muni_sel = _munis_permitidos[0]
        st.markdown(f"**Municipio:** {muni_sel.title()}")
    else:
        muni_opts = ["Todos los municipios"] + munis_con_datos
        muni_sel  = st.selectbox("Municipio", muni_opts)

    # ── Distrito ───────────────────────────────────────────────────────────────
    if muni_sel == "Todos los municipios":
        distritos_disponibles = sorted(set(
            d for m in munis_con_datos
            for d in DISTRITOS_POR_MUNICIPIO.get(m, [])
        ))
    else:
        distritos_disponibles = sorted(DISTRITOS_POR_MUNICIPIO.get(muni_sel, []))

    if distritos_disponibles:
        dist_opts = ["Todos los distritos"] + [f"Distrito {d}" for d in distritos_disponibles]
        dist_sel  = st.selectbox("Distrito", dist_opts)
    else:
        dist_sel = "Todos los distritos"

    # ── Filtro temporal — tres modos ───────────────────────────────────────────
    if not df_raw.empty and "fecha" in df_raw.columns:
        fechas_disp = sorted(df_raw["fecha"].dropna().unique())
        f_min = fechas_disp[0]
        f_max = fechas_disp[-1]
    else:
        f_min = f_max = date.today()

    import datetime as _dt_sb

    def _inicio_semana_sb(d):
        dow = d.isoweekday()
        if dow == 6:
            return d
        dias_atras = (dow % 7) + 1 if dow != 7 else 1
        return d - _dt_sb.timedelta(days=dias_atras)

    modo_tiempo = st.radio(
        "Vista temporal",
        ["📅 Día", "📆 Semana", "📊 Acumulado"],
        index=1,
        key="modo_tiempo",
    )

    if modo_tiempo == "📅 Día":
        dia_sel = st.date_input(
            "Fecha",
            value=f_max,
            min_value=f_min,
            max_value=f_max,
            key="dia_sel",
        )
        f_ini_global = dia_sel
        f_fin_global = dia_sel

    elif modo_tiempo == "📆 Semana":
        semanas_sb = sorted(set(_inicio_semana_sb(f) for f in fechas_disp), reverse=True)
        semana_sb_sel = st.selectbox(
            "Semana operativa",
            options=semanas_sb,
            format_func=lambda d: (
                f"{d.strftime('%d %b')} – "
                f"{(d + _dt_sb.timedelta(days=6)).strftime('%d %b %Y')}"
            ),
            key="semana_sb_sel",
        )
        f_ini_global = semana_sb_sel
        f_fin_global = semana_sb_sel + _dt_sb.timedelta(days=6)

    else:  # Acumulado
        st.caption(f"Operativo completo: {f_min.strftime('%d %b')} – {f_max.strftime('%d %b %Y')}")
        f_ini_global = f_min
        f_fin_global = f_max

    # ── Encuestador ────────────────────────────────────────────────────────────
    df_muni = df_raw if muni_sel == "Todos los municipios" \
              else df_raw[df_raw["municipio"] == muni_sel]
    enc_opts = ["Todos"] + sorted(df_muni["encuestador_nombre"].dropna().unique().tolist())
    enc_sel  = st.selectbox("Encuestador", enc_opts)

    st.markdown("---")

    # ── Refresh manual ─────────────────────────────────────────────────────────
    if st.button("🔄 Actualizar datos", use_container_width=True):
        get_encuestas(API_KEY, municipios=_filtro_munis, force_refresh=True)
        st.session_state["last_refresh"] = time.time()
        st.rerun()

    if ultima_actualizacion:
        ts_local = ultima_actualizacion.astimezone().strftime("%H:%M:%S")
        st.markdown(f'<div class="ts-badge">⏱ Actualizado: {ts_local}</div>',
                    unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**CEOP** · Guerrero · 2026")



# ── Aplicar filtros ────────────────────────────────────────────────────────────
f_ini, f_fin = f_ini_global, f_fin_global

df = df_raw.copy()

# Coordinador → filtra por municipios asignados
if coord_sel != "Todos los coordinadores":
    if bubble_tiene_coordinador:
        df = df[df["coordinador"] == coord_sel]
    else:
        munis_coord = MUNICIPIOS_POR_COORDINADOR.get(coord_sel, [])
        df = df[df["municipio"].isin(munis_coord)]

# Municipio
if muni_sel != "Todos los municipios":
    df = df[df["municipio"] == muni_sel]

# Distrito — mapear sección → distrito y filtrar
if dist_sel != "Todos los distritos":
    num_dist = int(dist_sel.replace("Distrito ", ""))
    secs_del_distrito = {s for s, d in SECCION_DISTRITO.items() if d == num_dist}
    df = df[df["seccion"].isin(secs_del_distrito)]

# Fechas
df = df[(df["fecha"] >= f_ini) & (df["fecha"] <= f_fin)]

# Encuestador
if enc_sel != "Todos":
    df = df[df["encuestador_nombre"] == enc_sel]


# ── Header ─────────────────────────────────────────────────────────────────────
titulo_geo = muni_sel if muni_sel != "Todos los municipios" else "Estado de Guerrero"
st.markdown(f"""
<div class="ceop-header">
  <div style="font-size:2.2rem">📋</div>
  <div>
    <h1>Monitoreo de Levantamiento — {titulo_geo}</h1>
    <p>Centro de Estudios de Opinión Pública · Producción · {len(df):,} registros en vista actual</p>
  </div>
</div>
""", unsafe_allow_html=True)


# ── KPIs globales ──────────────────────────────────────────────────────────────
total       = len(df)
terminadas  = int(df["terminada"].sum()) if "terminada" in df.columns else total
n_enc       = df["encuestador_id"].nunique()
dias        = df["fecha"].nunique()
prom_dia    = round(total / max(dias * max(n_enc, 1), 1), 1)
# Duración promedio solo sobre registros con timestamp confiable
df_conf     = df[df["duracion_confiable"]] if "duracion_confiable" in df.columns else df
prom_t      = round(df_conf["duracion_min"].mean(), 1) if len(df_conf) else 0
secs_cub    = df["seccion"].dropna().nunique()

# Total secciones del municipio seleccionado (o suma estatal)
if muni_sel != "Todos los municipios":
    total_secs = MUNICIPIOS.get(muni_sel, {}).get("secciones") or secs_cub
else:
    total_secs = sum(
        v.get("secciones") or 0 for v in MUNICIPIOS.values()
        if v.get("secciones")
    )

pct_cobert = round(secs_cub / max(total_secs, 1) * 100, 1)

# Fila 1 — Volumen y calidad
r1c1, r1c2, r1c3, _ = st.columns([1, 1, 1, 1])
kpi(r1c1, f"{total:,}",      "Encuestas levantadas",  f"{dias} días de campo")
kpi(r1c2, f"{terminadas:,}", "Encuestas terminadas",  f"{round(terminadas/max(total,1)*100,1)}% · completaron todo el cuestionario", "azul")
kpi(r1c3, f"~{n_enc}",       "Encuestadores activos ⚠️", "nombre libre — puede incluir duplicados", "azul")

st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)

# Fila 2 — Territorio y tiempo
r2c1, r2c2, r2c3, _ = st.columns([1, 1, 1, 1])
kpi(r2c1, f"{prom_t}'",      "Duración promedio",     f"rango esperado: {DUR_MIN_MIN}–{DUR_MAX_MIN} min")
kpi(r2c2, f"{secs_cub}",     "Secciones cubiertas",   f"de {total_secs} en el territorio", "naranja")
kpi(r2c3, f"{pct_cobert}%",  "Cobertura territorial", f"{total_secs - secs_cub} secciones pendientes", "naranja")

st.markdown("<br>", unsafe_allow_html=True)


# ── Tabs ───────────────────────────────────────────────────────────────────────
# ── Tabs — visibilidad por rol ──────────────────────────────────────────────────
# Rol estatal  : Tab 1, 2, 3, 4, 5
# Rol municipal: Tab 1, 2 únicamente — Tab 3, 4 y 5 no se renderizan
if _rol == "estatal":
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈  Desempeño de Brigada",
        "🗺️  Mapa de Cobertura",
        "👤  Perfil de Entrevistados",
        "📊  Resultados del Instrumento",
        "📉  Evolución Semanal",
    ])
else:
    tab1, tab2 = st.tabs([
        "📈  Desempeño de Brigada",
        "🗺️  Mapa de Cobertura",
    ])
    # Placeholders para que el resto del código no falle con referencias a tab3/tab4/tab5
    tab3 = None
    tab4 = None
    tab5 = None



# ── Función global de semana operativa (sábado → viernes) ────────────────────
# Disponible para todos los tabs. Tab 1 usa su propia copia local (inicio_semana_op)
# por razones históricas; Tab 5 usa esta versión global.
def semana_operativo(fecha):
    """Devuelve el sábado que abre la semana operativa de `fecha`."""
    import datetime as _dt2
    dow = fecha.isoweekday()
    if dow == 6:
        return fecha
    dias_atras = (dow % 7) + 1 if dow != 7 else 1
    return fecha - _dt2.timedelta(days=dias_atras)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 – DESEMPEÑO  (semáforo semanal)
# ══════════════════════════════════════════════════════════════════════════════
with tab1:

    import datetime as _dt

    # ── Umbrales semanales ────────────────────────────────────────────────────
    META_SEMANAL  = 20   # encuestas/semana objetivo
    AMARILLO_MIN  = 13   # mínimo para semáforo amarillo

    # ── Semana operativa: sábado → viernes ───────────────────────────────────
    def inicio_semana_op(fecha):
        """Devuelve el sábado que abre la semana operativa de `fecha`.
        isoweekday: Lun=1 … Sáb=6, Dom=7
        """
        dow = fecha.isoweekday()
        if dow == 6:
            return fecha          # ya es sábado
        # Días desde el sábado anterior:
        # Dom=7→1, Lun=1→2, Mar=2→3, Mié=3→4, Jue=4→5, Vie=5→6
        dias_atras = (dow % 7) + 1 if dow != 7 else 1
        return fecha - _dt.timedelta(days=dias_atras)

    # ── Abreviaturas de días activos ──────────────────────────────────────────
    ABREV_DIA = {1: "L", 2: "M", 3: "X", 4: "J", 5: "V", 6: "S", 7: "D"}

    def dias_activos_str(fechas):
        """Ej.: [sábado, lunes, miércoles] → 'S · L · X'"""
        dow_unicos = sorted(set(f.isoweekday() for f in fechas))
        return " · ".join(ABREV_DIA[d] for d in dow_unicos)

    # ── Funciones de semáforo ─────────────────────────────────────────────────
    def sem_semanal(n):
        if n >= META_SEMANAL: return "verde"
        if n >= AMARILLO_MIN: return "amarillo"
        return "rojo"

    def color_semanal(val):
        s = sem_semanal(val)
        if s == "verde":    return "background-color:#D4EDDA;color:#155724;font-weight:700"
        if s == "amarillo": return "background-color:#FFF3CD;color:#856404;font-weight:700"
        return                     "background-color:#F8D7DA;color:#721C24;font-weight:700"

    def color_complet(val):
        if val >= 95: return "background-color:#D4EDDA;color:#155724;font-weight:600"
        if val >= 85: return "background-color:#FFF3CD;color:#856404;font-weight:600"
        return               "background-color:#F8D7DA;color:#721C24;font-weight:600"

    if total == 0:
        st.info("Sin registros para los filtros seleccionados.")
    else:
        # ── Filtro de coordinador por rol ─────────────────────────────────────
        if _rol == "municipal" and bubble_tiene_coordinador:
            _nombre_coord = normalizar_nombre(st.session_state.get("name", ""))
            df_t1 = df[df["coordinador"].apply(normalizar_nombre) == _nombre_coord].copy()
            if df_t1.empty:
                st.warning(
                    f"No se encontraron registros con coordinador "
                    f"**'{_nombre_coord}'** en Bubble. "
                    "Verifica que el campo `coordinador` esté capturado correctamente. "
                    "Mostrando todos los registros del municipio como respaldo."
                )
                df_t1 = df.copy()
        else:
            df_t1 = df.copy()

        # ── Añadir semana operativa al dataframe ──────────────────────────────
        df_t1 = df_t1.copy()
        df_t1["semana_op"] = df_t1["fecha"].apply(inicio_semana_op)

        # ── Resumen por coordinador (fuente confiable — sin cambios) ──────────
        coord_resumen = (
            df_t1[df_t1["coordinador"].notna()]
            .groupby("coordinador")
            .agg(
                total         =("folio",             "count"),
                terminadas    =("terminada",          "sum"),
                secciones     =("seccion",            "nunique"),
                encuestadores =("encuestador_nombre", "nunique"),
            ).reset_index()
        )
        muni_por_coord = (
            df_t1[df_t1["coordinador"].notna()]
            .groupby("coordinador")["municipio"]
            .apply(lambda x: ", ".join(sorted([str(v) for v in x.dropna().unique()])))
            .reset_index()
            .rename(columns={"municipio": "municipios"})
        )
        coord_resumen = coord_resumen.merge(muni_por_coord, on="coordinador", how="left")
        coord_resumen["terminadas"]  = coord_resumen["terminadas"].astype(int)
        coord_resumen["pct_complet"] = (coord_resumen["terminadas"] / coord_resumen["total"] * 100).round(1)
        coord_resumen = coord_resumen.sort_values("total", ascending=False).reset_index(drop=True)

        st.markdown('<div class="sec-title">Resumen por coordinador</div>',
                    unsafe_allow_html=True)

        tbl_coord = coord_resumen[[
            "coordinador", "municipios", "encuestadores",
            "total", "terminadas", "pct_complet", "secciones"
        ]].copy()
        tbl_coord.columns = [
            "Coordinador", "Municipios", "Encuestadores (aprox.)",
            "Levantadas", "Terminadas", "% Complet.", "Secciones"
        ]
        tbl_coord_styled = (tbl_coord.style
            .map(color_complet, subset=["% Complet."])
            .format({"% Complet.": "{:.1f}%"})
            .set_properties(**{"font-family": "IBM Plex Sans", "font-size": "13px"})
        )
        st.dataframe(tbl_coord_styled, use_container_width=True, hide_index=True,
                     height=min(80 + len(coord_resumen) * 35, 320))
        st.caption("🟢 ≥95% completitud · 🟡 85–94% · 🔴 <85%  "
                   "· 'Encuestadores (aprox.)' cuenta variantes de nombre — puede estar sobreestimado.")

        # ══════════════════════════════════════════════════════════════════════
        # SEMÁFORO SEMANAL — núcleo del nuevo Tab 1
        # ══════════════════════════════════════════════════════════════════════
        st.markdown('<div class="sec-title">Semáforo semanal por encuestador</div>',
                    unsafe_allow_html=True)

        # Selector de semana
        semanas_disponibles = sorted(df_t1["semana_op"].unique(), reverse=True)
        sw_col, _, _ = st.columns([2, 2, 2])
        with sw_col:
            semana_sel = st.selectbox(
                "Semana operativa (inicio sábado)",
                options=semanas_disponibles,
                format_func=lambda d: (
                    f"Sem. {d.strftime('%d %b')} – "
                    f"{(d + _dt.timedelta(days=6)).strftime('%d %b %Y')}"
                ),
                key="semana_sel_tab1",
            )

        df_sem = df_t1[df_t1["semana_op"] == semana_sel]

        # Agregar por encuestador para la semana seleccionada
        grp_sem = df_sem.groupby(["encuestador_id", "encuestador_nombre"])
        resumen_sem = grp_sem.agg(
            enc_semana  =("folio",        "count"),
            terminadas  =("terminada",    "sum"),
            dur_prom    =("duracion_min", "mean"),
            secciones   =("seccion",      "nunique"),
            ultima_act  =("fecha",        "max"),
        ).reset_index()

        # Días activos como string (S · L · X …)
        fechas_por_enc = df_sem.groupby("encuestador_id")["fecha"].apply(list)
        resumen_sem["dias_activos"] = resumen_sem["encuestador_id"].map(
            lambda eid: dias_activos_str(fechas_por_enc.get(eid, []))
        )

        resumen_sem["dur_prom"]   = pd.to_numeric(resumen_sem["dur_prom"], errors="coerce").round(1)
        resumen_sem["terminadas"] = resumen_sem["terminadas"].astype(int)
        resumen_sem["pct_complet"]= (resumen_sem["terminadas"] / resumen_sem["enc_semana"] * 100).round(1)
        resumen_sem["_sem"]       = resumen_sem["enc_semana"].apply(sem_semanal)

        # Orden: verde → amarillo → rojo, dentro de cada grupo por enc_semana desc
        _orden_sem = {"verde": 0, "amarillo": 1, "rojo": 2}
        resumen_sem = resumen_sem.sort_values(
            ["_sem", "enc_semana"],
            key=lambda col: col.map(_orden_sem) if col.name == "_sem" else col,
            ascending=[True, False],
        ).reset_index(drop=True)

        # KPIs rápidos del semáforo
        n_verde    = (resumen_sem["_sem"] == "verde").sum()
        n_amarillo = (resumen_sem["_sem"] == "amarillo").sum()
        n_rojo     = (resumen_sem["_sem"] == "rojo").sum()

        m1, m2, m3, _ = st.columns([1, 1, 1, 3])
        m1.metric("🟢 Cumplieron meta",  int(n_verde),
                  help=f"≥ {META_SEMANAL} encuestas esta semana")
        m2.metric("🟡 En progreso",      int(n_amarillo),
                  help=f"{AMARILLO_MIN}–{META_SEMANAL - 1} encuestas esta semana")
        m3.metric("🔴 Bajo meta",        int(n_rojo),
                  help=f"< {AMARILLO_MIN} encuestas esta semana")

        # Tabla semáforo semanal
        resumen_sem["meta"]     = META_SEMANAL
        resumen_sem["pct_meta"] = (resumen_sem["enc_semana"] / META_SEMANAL * 100).round(1)

        tbl_sem = resumen_sem[[
            "encuestador_nombre", "enc_semana", "meta", "pct_meta",
            "dias_activos", "pct_complet", "dur_prom", "secciones", "ultima_act",
        ]].copy()
        tbl_sem.columns = [
            "Encuestador", "Enc. semana", "Meta", "% Meta",
            "Días activos", "% Complet.", "Dur. prom (min)", "Secciones", "Última actividad",
        ]

        def color_pct_meta(val):
            if val >= 100: return "background-color:#D4EDDA;color:#155724;font-weight:700"
            if val >= 65:  return "background-color:#FFF3CD;color:#856404;font-weight:700"
            return               "background-color:#F8D7DA;color:#721C24;font-weight:700"

        tbl_sem_styled = (
            tbl_sem.style
            .map(color_semanal,  subset=["Enc. semana"])
            .map(color_pct_meta, subset=["% Meta"])
            .map(color_complet,  subset=["% Complet."])
            .map(color_dur,      subset=["Dur. prom (min)"])
            .format({
                "Enc. semana":     "{:.0f}",
                "Meta":            "{:.0f}",
                "% Meta":          "{:.1f}%",
                "% Complet.":      "{:.1f}%",
                "Dur. prom (min)": "{:.1f}",
            })
            .set_properties(**{"font-family": "IBM Plex Sans", "font-size": "13px"})
        )
        st.dataframe(tbl_sem_styled, use_container_width=True, hide_index=True,
                     height=min(80 + len(resumen_sem) * 35, 460))
        st.caption(
            f"🟢 ≥100% de meta ({META_SEMANAL} enc/semana)   "
            f"🟡 65–99%   🔴 <65%   "
            "· Días: S=Sábado L=Lunes M=Martes X=Miércoles J=Jueves V=Viernes D=Domingo"
        )

        # ── Distribuciones del equipo (semana seleccionada) ───────────────────
        with st.expander("📊 Ver distribuciones del equipo — semana seleccionada", expanded=False):
            d1, d2 = st.columns(2)

            with d1:
                fig_hist = px.histogram(
                    resumen_sem, x="enc_semana", nbins=max(len(resumen_sem), 5),
                    color_discrete_sequence=[AZUL_L],
                    labels={"enc_semana": "Encuestas en la semana"},
                    title="Distribución de encuestas por encuestador — semana seleccionada",
                )
                fig_hist.add_vline(x=META_SEMANAL, line_dash="dash", line_color=VERDE,
                                   annotation_text=f"Meta ({META_SEMANAL})",
                                   annotation_position="top right")
                fig_hist.add_vline(x=AMARILLO_MIN, line_dash="dot", line_color=ROJO,
                                   annotation_text=f"Mínimo ({AMARILLO_MIN})",
                                   annotation_position="top left")
                fig_hist.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                       font_family="IBM Plex Sans", margin=dict(t=50, b=10))
                st.plotly_chart(fig_hist, use_container_width=True)

            with d2:
                df_conf_plot = df_sem[df_sem["duracion_confiable"]] \
                    if "duracion_confiable" in df_sem.columns else df_sem
                fig_box = px.box(
                    df_conf_plot, y="duracion_min",
                    color_discrete_sequence=[VERDE],
                    labels={"duracion_min": "Minutos"},
                    title="Duración de entrevistas — solo timestamps confiables",
                )
                fig_box.add_hline(y=DUR_MAX_MIN, line_dash="dash", line_color=AMARILLO,
                                  annotation_text=f"Máx ({DUR_MAX_MIN} min)")
                fig_box.add_hline(y=DUR_MIN_MIN, line_dash="dot",  line_color=ROJO,
                                  annotation_text=f"Mín ({DUR_MIN_MIN} min)")
                fig_box.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                      font_family="IBM Plex Sans", margin=dict(t=50, b=10))
                st.plotly_chart(fig_box, use_container_width=True)

        # ── Ficha individual ───────────────────────────────────────────────────
        st.markdown('<div class="sec-title">Ficha individual de encuestador</div>',
                    unsafe_allow_html=True)

        enc_nombres = sorted(df_t1["encuestador_nombre"].dropna().unique().tolist())
        if enc_nombres:
            enc_pick = st.selectbox("Seleccionar encuestador", enc_nombres, key="ficha_enc")
            df_enc   = df[df["encuestador_nombre"] == enc_pick]
            df_enc_t1 = df_t1[df_t1["encuestador_nombre"] == enc_pick].copy()

            # Resumen semanal del encuestador
            sem_enc = (
                df_enc_t1.groupby("semana_op")
                .agg(enc_sem=("folio", "count"), fechas=("fecha", list))
                .reset_index()
            )
            sem_enc["dias_activos"] = sem_enc["fechas"].apply(dias_activos_str)
            sem_enc["semana_str"]   = sem_enc["semana_op"].apply(
                lambda d: f"{d.strftime('%d %b')} – {(d + _dt.timedelta(days=6)).strftime('%d %b')}"
            )
            sem_enc["_sem"] = sem_enc["enc_sem"].apply(sem_semanal)

            fi1, fi2, fi3, fi4 = st.columns(4)
            fi1.metric("Total encuestas",  len(df_enc))
            fi2.metric("Días trabajados",  df_enc["fecha"].nunique())
            fi3.metric("Semanas activas",  len(sem_enc))
            fi4.metric("Dur. prom (min)",
                       round(pd.to_numeric(df_enc["duracion_min"],
                                           errors="coerce").mean(), 1))

            # Mini-tabla semanal
            st.markdown("**Avance por semana operativa**")
            tbl_enc_sem = sem_enc[["semana_str", "enc_sem", "dias_activos"]].copy()
            tbl_enc_sem.columns = ["Semana", "Enc. semana", "Días activos"]
            tbl_enc_sem_styled = (
                tbl_enc_sem.style
                .map(color_semanal, subset=["Enc. semana"])
                .format({"Enc. semana": "{:.0f}"})
                .set_properties(**{"font-family": "IBM Plex Sans", "font-size": "13px"})
            )
            st.dataframe(tbl_enc_sem_styled, use_container_width=True,
                         hide_index=True, height=min(80 + len(sem_enc) * 35, 280))

            # Curva diaria + histograma de duraciones
            fa1, fa2 = st.columns(2)
            with fa1:
                diario_enc = df_enc.groupby("fecha").size().reset_index(name="n")
                fig3 = px.bar(diario_enc, x="fecha", y="n",
                              color_discrete_sequence=[AZUL_L],
                              labels={"fecha": "Fecha", "n": "Encuestas"},
                              title=f"Encuestas por día — {enc_pick}")
                fig3.add_hline(y=META_DIA, line_dash="dash", line_color=VERDE,
                               annotation_text=f"Ref. diaria ({META_DIA})")
                fig3.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                   font_family="IBM Plex Sans", margin=dict(t=50, b=10))
                st.plotly_chart(fig3, use_container_width=True)

            with fa2:
                fig4 = px.histogram(df_enc, x="duracion_min", nbins=12,
                                    color_discrete_sequence=[VERDE],
                                    labels={"duracion_min": "Minutos"},
                                    title=f"Distribución de duraciones — {enc_pick}")
                fig4.add_vline(x=prom_t, line_dash="dash", line_color=AZUL,
                               annotation_text=f"Prom. equipo ({prom_t}')")
                fig4.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                   font_family="IBM Plex Sans", margin=dict(t=50, b=10))
                st.plotly_chart(fig4, use_container_width=True)

            sec_enc = (df_enc.groupby("seccion").size()
                       .reset_index(name="n").sort_values("n", ascending=False))
            if not sec_enc.empty:
                st.caption(
                    f"Secciones trabajadas por {enc_pick}: " +
                    ", ".join([f"**{int(r['seccion'])}** ({r['n']})"
                               for _, r in sec_enc.iterrows() if pd.notna(r["seccion"])])
                )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 – MAPA
# ══════════════════════════════════════════════════════════════════════════════
with tab2:

    st.markdown('<div class="sec-title">Cobertura territorial por sección electoral</div>',
                unsafe_allow_html=True)

    # KPIs territoriales — calculados sobre df filtrado
    sec_cnt = df.groupby("seccion").agg(
        n_enc_total     =("folio",         "count"),
        n_encuestadores =("encuestador_id","nunique"),
        dur_prom        =("duracion_min",  "mean"),
    ).reset_index()
    sec_cnt["dur_prom"] = pd.to_numeric(sec_cnt["dur_prom"], errors="coerce").round(1)
    sec_cnt["pct_meta"] = (sec_cnt["n_enc_total"] / META_POR_SECCION * 100).round(1)

    # Municipios con levantamiento
    munis_con_lev   = df["municipio"].dropna().nunique()
    total_munis_cfg = len([m for m in MUNICIPIOS if MUNICIPIOS[m].get("secciones")])

    # Determinar municipio para el mapa
    if muni_sel == "Todos los municipios":
        muni_mapa = None
    else:
        muni_mapa = muni_sel

    cfg_mapa      = MUNICIPIOS.get(muni_mapa, {}) if muni_mapa else {}
    geojson_fname = cfg_mapa.get("geojson")
    centro        = cfg_mapa.get("centro", ESTADO_CENTRO)
    zoom          = cfg_mapa.get("zoom",   ESTADO_ZOOM)
    n_secs        = cfg_mapa.get("secciones") or 0

    geojson_sec = load_geojson(str(DATA_DIR / geojson_fname)) if geojson_fname else None

    secs_con_data = sec_cnt["seccion"].dropna().nunique()
    secs_sin_data = max(n_secs - secs_con_data, 0)
    secs_verde    = (sec_cnt["pct_meta"] >= 80).sum()
    secs_amarillo = ((sec_cnt["pct_meta"] >= 50) & (sec_cnt["pct_meta"] < 80)).sum()
    secs_rojo     = (sec_cnt["pct_meta"] < 50).sum()

    def mk(col, val, label, sub="", cls=""):
        col.markdown(f"""
        <div class="kpi-card {cls}" style="margin-bottom:12px">
          <div class="kpi-val">{val}</div>
          <div class="kpi-label">{label}</div>
          <div class="kpi-sub">{sub}</div>
        </div>""", unsafe_allow_html=True)

    mk1, mk2, mk3, mk4 = st.columns(4)
    mk(mk1, f"{munis_con_lev} / {total_munis_cfg}",
       "Municipios con levantamiento", "sobre municipios configurados")
    mk(mk2, secs_con_data,
       "Secciones con levantamiento",
       f"de {n_secs} en {muni_mapa or 'el estado'}" if n_secs else "secciones únicas")
    mk(mk3, secs_sin_data,
       "Secciones sin cobertura", "pendientes de visitar",
       "naranja" if secs_sin_data > 0 else "")
    mk(mk4, f"🟢{int(secs_verde)} 🟡{int(secs_amarillo)} 🔴{int(secs_rojo)}",
       "Semáforo de secciones", f"meta: {META_POR_SECCION} enc/sección")

    # ── Vista estatal: tabla resumen por municipio ─────────────────────────────
    if muni_sel == "Todos los municipios":
        st.markdown('<div class="sec-title">Resumen de avance por municipio</div>',
                    unsafe_allow_html=True)

        muni_resumen = df.groupby("municipio").agg(
            encuestas   =("folio",         "count"),
            encuestadores=("encuestador_id","nunique"),
            secciones   =("seccion",       "nunique"),
            dur_prom    =("duracion_min",  "mean"),
        ).reset_index()
        muni_resumen["dur_prom"] = pd.to_numeric(muni_resumen["dur_prom"], errors="coerce").round(1)

        # Agregar total de secciones por municipio desde config
        muni_resumen["total_secs"] = muni_resumen["municipio"].map(
            lambda m: MUNICIPIOS.get(m, {}).get("secciones") or "—"
        )
        muni_resumen["cobertura"] = muni_resumen.apply(
            lambda r: f"{round(r['secciones'] / r['total_secs'] * 100, 1)}%"
            if isinstance(r["total_secs"], int) and r["total_secs"] > 0 else "—", axis=1
        )

        def color_muni_enc(val):
            if val >= 50:  return "background-color:#D4EDDA;color:#155724;font-weight:600"
            if val >= 20:  return "background-color:#FFF3CD;color:#856404;font-weight:600"
            return                "background-color:#F8D7DA;color:#721C24;font-weight:600"

        tbl_m = muni_resumen[[
            "municipio", "encuestas", "encuestadores", "secciones", "total_secs", "cobertura", "dur_prom"
        ]].copy()
        tbl_m.columns = [
            "Municipio", "Encuestas", "Encuestadores", "Secciones cubiertas",
            "Total secciones", "% Cobertura", "Dur. prom (min)"
        ]
        tbl_m_styled = (tbl_m.style
            .map(color_muni_enc, subset=["Encuestas"])
            .format({"Dur. prom (min)": "{:.1f}"})
            .set_properties(**{"font-family": "IBM Plex Sans", "font-size": "13px"})
        )
        st.dataframe(tbl_m_styled, use_container_width=True, hide_index=True)
        st.caption("Selecciona un municipio en el sidebar para ver el mapa de secciones.")

    # Mapa Folium
    if geojson_sec:
        mapa = folium.Map(location=centro, zoom_start=zoom, tiles="CartoDB positron")

        sec_lookup  = sec_cnt.set_index("seccion")["n_enc_total"].to_dict()
        enc_lookup  = sec_cnt.set_index("seccion")["n_encuestadores"].to_dict()
        dur_lookup  = sec_cnt.set_index("seccion")["dur_prom"].to_dict()
        pct_lookup  = sec_cnt.set_index("seccion")["pct_meta"].to_dict()

        geojson_enriq = copy.deepcopy(geojson_sec)
        for feature in geojson_enriq["features"]:
            sec = feature["properties"].get("seccion") or feature["properties"].get("SECCION")
            try:
                sec = int(sec)
            except (TypeError, ValueError):
                sec = -1
            n   = sec_lookup.get(sec, 0)
            pct = pct_lookup.get(sec, 0)
            feature["properties"].update({
                "enc_total":     int(n),
                "encuestadores": int(enc_lookup.get(sec, 0)),
                "dur_prom":      float(dur_lookup.get(sec, 0)),
                "pct_meta":      float(pct),
                "semaforo":      "🟢 En meta" if pct >= 80 else ("🟡 En riesgo" if pct >= 50 else "🔴 Bajo meta"),
                "estado":        "Con levantamiento" if n > 0 else "Sin levantamiento",
            })

        def style_sec(feature):
            pct = feature["properties"].get("pct_meta", 0)
            n   = feature["properties"].get("enc_total", 0)
            if n == 0:
                return {"fillColor": "#E8E8E8", "color": "#BBBBBB",
                        "weight": 0.8, "fillOpacity": 0.65}
            if pct >= 80:
                return {"fillColor": VERDE,   "color": "#1A5C42",
                        "weight": 1.4, "fillOpacity": 0.78}
            if pct >= 50:
                return {"fillColor": AMARILLO, "color": "#8a6200",
                        "weight": 1.4, "fillOpacity": 0.78}
            return     {"fillColor": ROJO,     "color": "#7b1a14",
                        "weight": 1.4, "fillOpacity": 0.78}

        tooltip_html = folium.GeoJsonTooltip(
            fields=["seccion", "semaforo", "enc_total", "pct_meta", "encuestadores", "dur_prom"],
            aliases=["Sección:", "Estado:", "Encuestas:", "% meta:", "Encuestadores:", "Dur. prom (min):"],
            localize=True, sticky=True, labels=True,
            style=(
                "background-color:white;border:1px solid #2E7D5E;"
                "border-radius:6px;padding:8px 12px;"
                "font-family:'IBM Plex Sans',sans-serif;font-size:13px;"
                "box-shadow:0 2px 8px rgba(0,0,0,0.15);"
            ),
        )

        folium.GeoJson(
            geojson_enriq,
            style_function=style_sec,
            highlight_function=lambda f: {"fillOpacity": 0.95, "weight": 2.5, "color": AZUL},
            tooltip=tooltip_html,
            name="Secciones electorales",
        ).add_to(mapa)

        folium.LayerControl().add_to(mapa)
        st_folium(mapa, width="100%", height=540, returned_objects=[])

        # Leyenda semáforo
        st.caption(
            f"🟢 En meta: ≥80% de {META_POR_SECCION} enc/sección   "
            f"🟡 En riesgo: 50–79%   🔴 Bajo meta: <50%   "
            f"⬜ Sin levantamiento"
        )

        # Secciones sin cobertura
        if secs_sin_data > 0 and geojson_sec:
            prop_key = "seccion" if "seccion" in geojson_sec["features"][0]["properties"] else "SECCION"
            all_secs = {int(f["properties"][prop_key]) for f in geojson_sec["features"]}
            covered  = set(sec_cnt["seccion"].dropna().astype(int).tolist())
            pending  = sorted(all_secs - covered)
            st.markdown('<div class="sec-title">Secciones sin encuestas levantadas</div>',
                        unsafe_allow_html=True)
            st.write(f"{len(pending)} secciones pendientes: " + ", ".join(str(s) for s in pending))
    elif muni_mapa:
        st.warning(f"GeoJSON no disponible para {muni_mapa}. Verifica que el archivo exista en data/geojsons/")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 – PERFIL  (solo rol estatal)
# ══════════════════════════════════════════════════════════════════════════════
if tab3 is not None:
    with tab3:
      st.markdown('<div class="sec-title">Perfil sociodemográfico de entrevistados</div>',
                  unsafe_allow_html=True)

      if total == 0:
          st.info("Sin registros para los filtros seleccionados.")
      else:
          c1, c2, c3 = st.columns(3)

          with c1:
              cnt = df["sexo"].value_counts().reset_index()
              cnt.columns = ["Sexo", "n"]
              fig = px.pie(cnt, names="Sexo", values="n", hole=0.42,
                           color_discrete_sequence=[AZUL_L, NARANJA, "#ccc"],
                           title="Distribución por sexo")
              fig.update_layout(font_family="IBM Plex Sans", margin=dict(t=40, b=0))
              st.plotly_chart(fig, use_container_width=True)

          with c2:
              edu_order = ["Primaria", "Secundaria", "Preparatoria", "Universidad", "Posgrado"]
              cnt = df["nivel_educativo"].value_counts().reindex(edu_order).reset_index()
              cnt.columns = ["Nivel", "n"]
              fig2 = px.bar(cnt, x="Nivel", y="n", text="n",
                            color_discrete_sequence=[VERDE], title="Nivel educativo")
              fig2.update_traces(textposition="outside")
              fig2.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                 font_family="IBM Plex Sans", margin=dict(t=40, b=0))
              st.plotly_chart(fig2, use_container_width=True)

          with c3:
              cnt = df["recibe_bienestar"].value_counts().reset_index()
              cnt.columns = ["Recibe Bienestar", "n"]
              fig3 = px.pie(cnt, names="Recibe Bienestar", values="n", hole=0.42,
                            color_discrete_sequence=[VERDE, "#ccc"],
                            title="¿Recibe programa Bienestar?")
              fig3.update_layout(font_family="IBM Plex Sans", margin=dict(t=40, b=0))
              st.plotly_chart(fig3, use_container_width=True)

          # Pirámide
          st.markdown('<div class="sec-title">Pirámide de edades</div>', unsafe_allow_html=True)
          df_pir = df.copy()
          df_pir["edad"] = pd.to_numeric(df_pir["edad"], errors="coerce")
          df_pir = df_pir.dropna(subset=["edad"])
          if len(df_pir) > 0:
              df_pir["grupo_edad"] = pd.cut(
                  df_pir["edad"], bins=[17, 25, 35, 45, 55, 65, 120],
                  labels=["18-25", "26-35", "36-45", "46-55", "56-65", "65+"]
              )
              pir = df_pir.groupby(["grupo_edad", "sexo"]).size().reset_index(name="n")
              pir = pir[pir["sexo"].isin(["Hombre", "Mujer"])]
              pir.loc[pir["sexo"] == "Hombre", "n"] *= -1
              max_val = pir["n"].abs().max()
              ticks_pos = list(range(0, int(max_val) + 5, max(int(max_val // 4), 1)))
              ticks_val = [-t for t in reversed(ticks_pos[1:])] + ticks_pos

              fig_p = px.bar(pir, x="n", y="grupo_edad", color="sexo", orientation="h",
                             color_discrete_map={"Hombre": AZUL_L, "Mujer": NARANJA},
                             labels={"n": "Conteo", "grupo_edad": ""},
                             title="Pirámide de edades", height=300)
              fig_p.update_xaxes(tickvals=ticks_val, ticktext=[abs(t) for t in ticks_val])
              fig_p.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                  font_family="IBM Plex Sans", margin=dict(t=40, b=10))
              st.plotly_chart(fig_p, use_container_width=True)


  # ══════════════════════════════════════════════════════════════════════════════
# TAB 4 – RESULTADOS  (solo rol estatal)
# ══════════════════════════════════════════════════════════════════════════════
if tab4 is not None:
    with tab4:

      if total == 0:
          st.info("Sin registros para los filtros seleccionados.")
      else:
          orden_sat = ["Muy satisfecho", "Satisfecho", "Regular", "Insatisfecho"]
          col_sat   = [VERDE, VERDE_L, NARANJA, ROJO]

          # ── Evolución temporal por semana ──────────────────────────────────
          st.markdown('<div class="sec-title">Evolución semanal de percepciones</div>',
                      unsafe_allow_html=True)

          df_trend = df.copy()
          df_trend["semana"] = df_trend["fecha"].apply(semana_operativo)
          semanas_disp = sorted(df_trend["semana"].unique(), key=lambda s: int(s[1:]))

          if len(semanas_disp) < 2:
              st.info(
                  f"Aún solo hay datos de **{semanas_disp[0] if semanas_disp else 'una semana'}**. "
                  "La evolución temporal estará disponible cuando haya al menos dos semanas de campo."
              )
          else:
              PREGUNTAS_TREND = {
                  "P5 — ¿Ha escuchado de Iván Hernández?":   ("p5_conoce",     OPCIONES["p5_conoce"]),
                  "P7 — Cercanía con la gente":               ("p7_cercania",   OPCIONES["p7_cercania"]),
                  "P8 — Representa valores de la 4T":         ("p8_valores_4t", OPCIONES["p8_valores_4t"]),
                  "P9 — Intención de voto":                   ("p9_voto",       OPCIONES["p9_voto"]),
                  "P1 — Satisfacción con AMLO":               ("p1_amlo",       OPCIONES["p1_amlo"]),
                  "P2 — Satisfacción con Claudia Sheinbaum":  ("p2_sheinbaum",  OPCIONES["p2_sheinbaum"]),
                  "P3 — Programas Bienestar mejoran la vida": ("p3_bienestar",  OPCIONES["p3_bienestar"]),
              }

              tc1, tc2 = st.columns([2, 1])
              with tc1:
                  preg_label = st.selectbox(
                      "Pregunta a visualizar", list(PREGUNTAS_TREND.keys()), key="trend_pregunta"
                  )
              with tc2:
                  granularidad = st.radio(
                      "Granularidad", ["Semana", "Día"], horizontal=True, key="trend_gran"
                  )

              campo_trend, opciones_trend = PREGUNTAS_TREND[preg_label]

              if granularidad == "Semana":
                  df_trend["grupo"] = df_trend["semana"]
                  grupos_ord = semanas_disp
              else:
                  df_trend["grupo"] = df_trend["fecha"].astype(str)
                  grupos_ord = sorted(df_trend["grupo"].unique())

              trend_rows = []
              for grp in grupos_ord:
                  sub = df_trend[df_trend["grupo"] == grp][campo_trend].dropna()
                  n_grp = len(sub)
                  if n_grp == 0:
                      continue
                  for opc in opciones_trend:
                      pct = round((sub == opc).sum() / n_grp * 100, 1)
                      trend_rows.append({"Período": str(grp), "Opción": opc,
                                         "Porcentaje": pct, "n": n_grp})

              if trend_rows:
                  df_tp = pd.DataFrame(trend_rows)
                  n_por_grupo = df_tp.groupby("Período")["n"].first().to_dict()
                  df_tp["Período_label"] = df_tp["Período"].apply(
                      lambda g: f"{g}  (n={n_por_grupo.get(g,0):,})"
                  )
                  periodos_label_ord = [
                      f"{g}  (n={n_por_grupo.get(g,0):,})"
                      for g in grupos_ord if g in n_por_grupo
                  ]
                  paleta = [VERDE, VERDE_L, AZUL_L, NARANJA, ROJO, AMARILLO, "#aaa"]
                  color_map = {opc: paleta[i % len(paleta)] for i, opc in enumerate(opciones_trend)}

                  fig_trend = px.line(
                      df_tp, x="Período_label", y="Porcentaje", color="Opción",
                      markers=True, color_discrete_map=color_map,
                      category_orders={"Período_label": periodos_label_ord},
                      labels={"Porcentaje": "%", "Período_label": ""},
                      title=f"Evolución — {preg_label}", height=380,
                  )
                  fig_trend.update_traces(line=dict(width=2.5), marker=dict(size=8))
                  fig_trend.update_layout(
                      plot_bgcolor="white", paper_bgcolor="white",
                      font_family="IBM Plex Sans", margin=dict(t=50, b=10),
                      yaxis=dict(range=[0, 105], ticksuffix="%"),
                      legend=dict(orientation="h", yanchor="bottom", y=-0.4, xanchor="left", x=0),
                  )
                  st.plotly_chart(fig_trend, use_container_width=True)

                  # Tabla delta (solo granularidad Semana con ≥2 semanas)
                  if granularidad == "Semana":
                      st.markdown(
                          '<div class="sec-title">Cambio semana a semana (puntos porcentuales)</div>',
                          unsafe_allow_html=True)
                      pivot = df_tp.pivot_table(
                          index="Opción", columns="Período", values="Porcentaje"
                      ).reindex(opciones_trend)
                      pivot = pivot[[s for s in semanas_disp if s in pivot.columns]]
                      sem_cols = list(pivot.columns)
                      for i in range(1, len(sem_cols)):
                          d_col = f"Δ {sem_cols[i-1]}→{sem_cols[i]}"
                          pivot[d_col] = (pivot[sem_cols[i]] - pivot[sem_cols[i-1]]).round(1)

                      def color_delta(val):
                          if pd.isna(val): return ""
                          if val > 0:  return "color:#155724;font-weight:600"
                          if val < 0:  return "color:#721C24;font-weight:600"
                          return "color:#555"

                      fmt = {c: "{:.1f}%" for c in sem_cols}
                      fmt.update({c: "{:+.1f}pp" for c in pivot.columns if c.startswith("Δ")})
                      d_cols = [c for c in pivot.columns if c.startswith("Δ")]
                      st.dataframe(
                          pivot.reset_index().style
                          .format(fmt, na_rep="—")
                          .map(color_delta, subset=d_cols)
                          .set_properties(**{"font-family": "IBM Plex Sans", "font-size": "13px"}),
                          use_container_width=True, hide_index=True,
                      )
                      st.caption("pp = puntos porcentuales.  🟢 Sube · 🔴 Baja")

          st.markdown("---")

          # ── Sección A ──────────────────────────────────────────────────────────
          st.markdown('<div class="sec-title">Sección A — Contexto de Gobierno y 4T</div>',
                      unsafe_allow_html=True)
          a1, a2 = st.columns(2)
          with a1:
              show_chart(pct_bar(df, "p1_amlo", "P1. Satisfacción con AMLO", orden_sat, col_sat))
          with a2:
              show_chart(pct_bar(df, "p2_sheinbaum", "P2. Satisfacción con Claudia Sheinbaum",
                                 orden_sat, col_sat))
          show_chart(pct_bar(df, "p3_bienestar",
                             "P3. ¿Los Programas del Bienestar han mejorado la vida en Guerrero?",
                             ["Mucho", "Algo", "Poco", "Nada"], col_sat, height=220))

          # ── Sección B ──────────────────────────────────────────────────────────
          st.markdown('<div class="sec-title">Sección B — Posicionamiento de Iván Hernández</div>',
                      unsafe_allow_html=True)

          # P4a y P4b por separado
          b0a, b0b = st.columns(2)
          orden_p4 = OPCIONES["p4a_delegado_amlo"]
          col_p4   = [VERDE, VERDE_L, NARANJA, "#aaa"]
          with b0a:
              show_chart(pct_bar(df, "p4a_delegado_amlo",
                                 "P4a. ¿Sabía que AMLO designó a Iván Hernández como Delegado Bienestar?",
                                 orden_p4, col_p4))
          with b0b:
              show_chart(pct_bar(df, "p4b_delegado_csp",
                                 "P4b. ¿Sabía que Claudia Sheinbaum lo ratificó en el cargo?",
                                 orden_p4, col_p4))

          b1, b2 = st.columns(2)
          with b1:
              show_chart(pct_bar(df, "p5_conoce",
                                 "P5. ¿Ha escuchado hablar de Iván Hernández Díaz?",
                                 ["Sí", "No"], [VERDE, "#ccc"]))
              df_conoce = df[df["p5_conoce"] == "Sí"]
              show_chart(pct_bar(df_conoce, "p6_opinion",
                                 "P6. Opinión sobre su trabajo como Delegado (entre quienes lo conocen)",
                                 OPCIONES["p6_opinion"], [VERDE, VERDE_L, NARANJA, ROJO, "#aaa"]))
          with b2:
              show_chart(pct_bar(df, "p7_cercania",
                                 "P7. ¿Qué tan cercano considera que es a la gente de Guerrero?",
                                 OPCIONES["p7_cercania"], [VERDE, VERDE_L, NARANJA, "#aaa"]))
              show_chart(pct_bar(df, "p8_valores_4t",
                                 "P8. ¿Representa los valores de la Cuarta Transformación?",
                                 OPCIONES["p8_valores_4t"], [VERDE, VERDE_L, ROJO, "#aaa"]))

          # ── Sección C ──────────────────────────────────────────────────────────
          st.markdown('<div class="sec-title">Sección C — Intención de Voto y Percepción</div>',
                      unsafe_allow_html=True)

          show_chart(pct_bar(df, "p9_voto",
                             "P9. Si hoy fueran las elecciones para gobernador, ¿votaría por Iván Hernández?",
                             OPCIONES["p9_voto"], [VERDE, VERDE_L, NARANJA, ROJO, "#aaa"], height=240))

          c1, c2 = st.columns(2)
          with c1:
              show_chart(pct_bar(df, "p10_frase",
                                 "P10. ¿Qué frase describe mejor lo que piensa de Iván Hernández?",
                                 OPCIONES["p10_frase"]))

          # ── P11 — multi-respuesta ──────────────────────────────────────────────
          with c2:
              p11_cols = list(OPCIONES["p11_labels"].keys())
              p11_labels = OPCIONES["p11_labels"]
              p11_disponibles = [c for c in p11_cols if c in df.columns]

              if p11_disponibles:
                  p11_freq = pd.DataFrame({
                      "Opción": [p11_labels[c] for c in p11_disponibles],
                      "Menciones": [int(df[c].sum()) for c in p11_disponibles],
                  }).sort_values("Menciones", ascending=True)

                  p11_freq["Porcentaje"] = (p11_freq["Menciones"] / max(total, 1) * 100).round(1)

                  fig_p11 = px.bar(
                      p11_freq, x="Porcentaje", y="Opción", orientation="h",
                      text=p11_freq["Porcentaje"].apply(lambda x: f"{x}%"),
                      color_discrete_sequence=[VERDE_L],
                      title="P11. Prioridad #1 para el próximo gobernador (multi-respuesta)",
                      height=300,
                  )
                  fig_p11.update_traces(textposition="outside")
                  fig_p11.update_layout(
                      plot_bgcolor="white", paper_bgcolor="white",
                      showlegend=False, font_family="IBM Plex Sans",
                      margin=dict(t=45, b=5, l=160), xaxis_range=[0, 105],
                  )
                  st.plotly_chart(fig_p11, use_container_width=True)
                  st.caption("Porcentaje sobre total de encuestas. Respuesta múltiple — la suma puede superar 100%.")

          # ── Datos de contacto capturados ──────────────────────────────────────
          st.markdown('<div class="sec-title">Datos de contacto capturados</div>',
                      unsafe_allow_html=True)

          df_term      = df[df["terminada"]] if "terminada" in df.columns else df
          n_term       = len(df_term)
          n_cel        = int(df_term["tiene_celular"].sum()) if "tiene_celular" in df_term.columns else 0
          n_cor        = int(df_term["tiene_correo"].sum())  if "tiene_correo"  in df_term.columns else 0
          pct_cel      = round(n_cel / max(n_term, 1) * 100, 1)
          pct_cor      = round(n_cor / max(n_term, 1) * 100, 1)

          ct1, ct2, _ = st.columns([1, 1, 2])
          kpi(ct1, f"{n_cel:,}", "Celulares capturados",
              f"{pct_cel}% de {n_term:,} enc. terminadas")
          kpi(ct2, f"{n_cor:,}", "Correos capturados",
              f"{pct_cor}% de {n_term:,} enc. terminadas", "azul")

          # ── Descarga ───────────────────────────────────────────────────────────
          st.markdown("---")
          # Excluir PII y columnas internas antes de exportar
          cols_excluir_csv = {"tiene_celular", "tiene_correo", "terminada",
                              "duracion_confiable", "fecha_inicio", "fecha_fin"}
          cols_csv = [c for c in df.columns if c not in cols_excluir_csv]
          csv_out = df[cols_csv].to_csv(index=False).encode("utf-8")
          st.download_button(
              "⬇️ Descargar datos filtrados (CSV)", csv_out,
              f"ceop_guerrero_{muni_sel.lower().replace(' ','_')}.csv", "text/csv"
          )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 – EVOLUCIÓN SEMANAL  (solo rol estatal)
# ══════════════════════════════════════════════════════════════════════════════
if tab5 is not None:
    with tab5:

        if total == 0:
            st.info("Sin registros para los filtros seleccionados.")
        else:
            # ── Preparar columna de semana ─────────────────────────────────────
            df_ev = df.copy()
            df_ev["semana"] = df_ev["fecha"].apply(semana_operativo)
            semanas_ord = sorted(df_ev["semana"].unique(), key=lambda s: int(s[1:]))

            # Base para P6: solo quienes conocen a Iván
            df_ev_conoce = df_ev[df_ev["p5_conoce"] == "Sí"]

            # ── Helper: mini-gráfica de líneas por semana ──────────────────────
            def mini_trend(df_base, campo, titulo, opciones, nota=None):
                """
                Retorna un go.Figure de líneas % por semana.
                df_base: DataFrame ya filtrado (ej. solo quienes conocen a Iván para P6).
                """
                import plotly.graph_objects as go

                paleta = [VERDE, NARANJA, AZUL_L, ROJO, VERDE_L, AMARILLO, "#aaa"]
                rows = []
                for sem in semanas_ord:
                    sub = df_base[df_base["semana"] == sem][campo].dropna()
                    n = len(sub)
                    if n == 0:
                        continue
                    for opc in opciones:
                        rows.append({
                            "semana": sem,
                            "Opción": opc,
                            "pct": round((sub == opc).sum() / n * 100, 1),
                            "n": n,
                        })

                if not rows:
                    return None

                df_p = pd.DataFrame(rows)
                fig = go.Figure()
                for i, opc in enumerate(opciones):
                    sub_opc = df_p[df_p["Opción"] == opc]
                    if sub_opc.empty:
                        continue
                    fig.add_trace(go.Scatter(
                        x=sub_opc["semana"],
                        y=sub_opc["pct"],
                        mode="lines+markers",
                        name=opc,
                        line=dict(color=paleta[i % len(paleta)], width=2),
                        marker=dict(size=7),
                        hovertemplate=f"<b>{opc}</b><br>%{{y:.1f}}%<br>n=%{{customdata}}<extra></extra>",
                        customdata=sub_opc["n"],
                    ))

                fig.update_layout(
                    title=dict(text=titulo, font=dict(size=13, family="IBM Plex Sans"), x=0),
                    plot_bgcolor="white", paper_bgcolor="white",
                    font_family="IBM Plex Sans",
                    margin=dict(t=40, b=60, l=10, r=10),
                    height=280,
                    yaxis=dict(range=[0, 105], ticksuffix="%", tickfont=dict(size=10)),
                    xaxis=dict(tickfont=dict(size=10)),
                    legend=dict(
                        orientation="h", font=dict(size=9),
                        yanchor="top", y=-0.18, xanchor="left", x=0,
                    ),
                    showlegend=True,
                )
                if nota:
                    fig.add_annotation(
                        text=nota, xref="paper", yref="paper",
                        x=0, y=-0.32, showarrow=False,
                        font=dict(size=9, color="#888"), xanchor="left",
                    )
                return fig

            # ── Definición de preguntas estratégicas ───────────────────────────
            PANEL = [
                {
                    "campo":   "p3_bienestar",
                    "titulo":  "P3 — Bienestar mejora la vida",
                    "opciones": OPCIONES["p3_bienestar"],
                    "base":    df_ev,
                    "nota":    None,
                },
                {
                    "campo":   "p4a_delegado_amlo",
                    "titulo":  "P4a — Sabía que AMLO designó a Iván",
                    "opciones": OPCIONES["p4a_delegado_amlo"],
                    "base":    df_ev,
                    "nota":    None,
                },
                {
                    "campo":   "p4b_delegado_csp",
                    "titulo":  "P4b — Sabía que Sheinbaum lo ratificó",
                    "opciones": OPCIONES["p4b_delegado_csp"],
                    "base":    df_ev,
                    "nota":    None,
                },
                {
                    "campo":   "p5_conoce",
                    "titulo":  "P5 — ¿Ha escuchado de Iván Hernández?",
                    "opciones": OPCIONES["p5_conoce"],
                    "base":    df_ev,
                    "nota":    None,
                },
                {
                    "campo":   "p6_opinion",
                    "titulo":  "P6 — Opinión sobre su trabajo",
                    "opciones": OPCIONES["p6_opinion"],
                    "base":    df_ev_conoce,
                    "nota":    f"Solo entre quienes lo conocen (P5=Sí, n={len(df_ev_conoce):,})",
                },
                {
                    "campo":   "p7_cercania",
                    "titulo":  "P7 — Cercanía con la gente",
                    "opciones": OPCIONES["p7_cercania"],
                    "base":    df_ev,
                    "nota":    None,
                },
                {
                    "campo":   "p8_valores_4t",
                    "titulo":  "P8 — Representa valores de la 4T",
                    "opciones": OPCIONES["p8_valores_4t"],
                    "base":    df_ev,
                    "nota":    None,
                },
                {
                    "campo":   "p9_voto",
                    "titulo":  "P9 — Intención de voto",
                    "opciones": OPCIONES["p9_voto"],
                    "base":    df_ev,
                    "nota":    None,
                },
            ]

            # ── Una sola semana: aviso ─────────────────────────────────────────
            if len(semanas_ord) < 2:
                st.info(
                    f"Aún solo hay datos de **{semanas_ord[0] if semanas_ord else 'una semana'}**. "
                    "El panel de evolución activará automáticamente cuando haya al menos "
                    "dos semanas de campo."
                )
                # Mostrar distribución actual como referencia de línea base
                st.markdown(
                    f'<div class="sec-title">Línea base — {semanas_ord[0] if semanas_ord else ""}</div>',
                    unsafe_allow_html=True,
                )
                for i in range(0, len(PANEL), 2):
                    cols = st.columns(2)
                    for j, cfg in enumerate(PANEL[i:i+2]):
                        sub = cfg["base"][cfg["campo"]].dropna()
                        if sub.empty:
                            continue
                        cnt = (sub.value_counts(normalize=True)
                               .mul(100).round(1).reindex(cfg["opciones"]).reset_index())
                        cnt.columns = ["Opción", "%"]
                        fig_base = px.bar(
                            cnt, x="%", y="Opción", orientation="h",
                            color="Opción",
                            color_discrete_sequence=[VERDE, VERDE_L, AZUL_L, NARANJA, ROJO, "#aaa"],
                            text=cnt["%"].apply(lambda v: f"{v}%" if pd.notna(v) else ""),
                            title=cfg["titulo"], height=240,
                        )
                        fig_base.update_traces(textposition="outside")
                        fig_base.update_layout(
                            plot_bgcolor="white", paper_bgcolor="white",
                            showlegend=False, font_family="IBM Plex Sans",
                            margin=dict(t=40, b=5, l=200), xaxis_range=[0, 105],
                        )
                        with cols[j]:
                            st.plotly_chart(fig_base, use_container_width=True)
                            if cfg["nota"]:
                                st.caption(cfg["nota"])

            else:
                # ── Panel ejecutivo 2×4 ───────────────────────────────────────
                st.markdown(
                    '<div class="sec-title">Panel ejecutivo — evolución por semana</div>',
                    unsafe_allow_html=True,
                )
                st.caption(
                    f"Semanas disponibles: {' · '.join(semanas_ord)}  "
                    f"| Granularidad fija en semana para comparación consistente."
                )

                for i in range(0, len(PANEL), 2):
                    cols = st.columns(2)
                    for j, cfg in enumerate(PANEL[i:i+2]):
                        fig = mini_trend(
                            cfg["base"], cfg["campo"],
                            cfg["titulo"], cfg["opciones"],
                            nota=cfg["nota"],
                        )
                        with cols[j]:
                            if fig:
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info(f"Sin datos: {cfg['titulo']}")

                # ── Tabla de deltas semana a semana ───────────────────────────
                st.markdown("---")
                st.markdown(
                    '<div class="sec-title">Análisis por pregunta — tabla de cambios</div>',
                    unsafe_allow_html=True,
                )

                preg_opts = {cfg["titulo"]: cfg for cfg in PANEL}
                preg_sel = st.selectbox(
                    "Seleccionar pregunta para análisis detallado",
                    list(preg_opts.keys()),
                    key="evol_preg_sel",
                )
                cfg_sel = preg_opts[preg_sel]

                # Calcular pivot con deltas
                rows_det = []
                for sem in semanas_ord:
                    sub = cfg_sel["base"][cfg_sel["base"]["semana"] == sem][cfg_sel["campo"]].dropna()
                    n = len(sub)
                    if n == 0:
                        continue
                    for opc in cfg_sel["opciones"]:
                        rows_det.append({
                            "Opción": opc,
                            "semana": sem,
                            "pct": round((sub == opc).sum() / n * 100, 1),
                            "n": n,
                        })

                if rows_det:
                    df_det = pd.DataFrame(rows_det)
                    pivot_det = df_det.pivot_table(
                        index="Opción", columns="semana", values="pct"
                    ).reindex(cfg_sel["opciones"])
                    pivot_det = pivot_det[[s for s in semanas_ord if s in pivot_det.columns]]

                    sem_cols = list(pivot_det.columns)
                    for i in range(1, len(sem_cols)):
                        d_col = f"Δ {sem_cols[i-1]}→{sem_cols[i]}"
                        pivot_det[d_col] = (pivot_det[sem_cols[i]] - pivot_det[sem_cols[i-1]]).round(1)

                    def color_delta(val):
                        if pd.isna(val): return ""
                        if val > 0:  return "color:#155724;font-weight:600"
                        if val < 0:  return "color:#721C24;font-weight:600"
                        return "color:#555"

                    fmt = {c: "{:.1f}%" for c in sem_cols}
                    fmt.update({c: "{:+.1f}pp" for c in pivot_det.columns if c.startswith("Δ")})
                    d_cols = [c for c in pivot_det.columns if c.startswith("Δ")]

                    # n por semana como fila de contexto
                    n_row = df_det.groupby("semana")["n"].first().reindex(semanas_ord)
                    n_df  = pd.DataFrame([["n (encuestas)"] + [
                        f"{int(n_row[s]):,}" if s in n_row and pd.notna(n_row[s]) else "—"
                        for s in sem_cols
                    ] + [""] * len(d_cols)],
                    columns=["Opción"] + sem_cols + d_cols)

                    st.dataframe(
                        pivot_det.reset_index().style
                        .format(fmt, na_rep="—")
                        .map(color_delta, subset=d_cols)
                        .set_properties(**{"font-family": "IBM Plex Sans", "font-size": "13px"}),
                        use_container_width=True, hide_index=True,
                    )
                    # Fila de n como caption
                    n_labels = "  |  ".join(
                        f"**{s}**: n={int(n_row[s]):,}" for s in sem_cols
                        if s in n_row and pd.notna(n_row[s])
                    )
                    st.caption(f"pp = puntos porcentuales.  🟢 Sube · 🔴 Baja  |  {n_labels}")
                    if cfg_sel["nota"]:
                        st.caption(cfg_sel["nota"])