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
from bubble_connector import get_encuestas

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
    if coord_sel == "Todos los coordinadores":
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

    # ── Rango de fechas ────────────────────────────────────────────────────────
    if not df_raw.empty and "fecha" in df_raw.columns:
        fechas_disp = sorted(df_raw["fecha"].dropna().unique())
        f_min = fechas_disp[0]
        f_max = fechas_disp[-1]
    else:
        f_min = f_max = date.today()

    rango = st.date_input("Rango de fechas", value=(f_min, f_max),
                          min_value=f_min, max_value=f_max)

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
f_ini, f_fin = (rango[0], rango[-1]) if len(rango) == 2 else (rango[0], rango[0])

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
tab1, tab2, tab3, tab4 = st.tabs([
    "📈  Desempeño de Brigada",
    "🗺️  Mapa de Cobertura",
    "👤  Perfil de Entrevistados",
    "📊  Resultados del Instrumento",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 – DESEMPEÑO
# ══════════════════════════════════════════════════════════════════════════════
with tab1:

    if total == 0:
        st.info("Sin registros para los filtros seleccionados.")
    else:
        # ── Resumen por coordinador (fuente confiable) ───────────────────────
        coord_resumen = (
            df[df["coordinador"].notna()]
            .groupby("coordinador")
            .agg(
                total      =("folio",      "count"),
                terminadas =("terminada",  "sum"),
                secciones  =("seccion",    "nunique"),
                encuestadores=("encuestador_nombre", "nunique"),
                municipios =("municipio",  lambda x: ", ".join(sorted(x.dropna().unique()))),
            ).reset_index()
        )
        coord_resumen["terminadas"]  = coord_resumen["terminadas"].astype(int)
        coord_resumen["pct_complet"] = (coord_resumen["terminadas"] / coord_resumen["total"] * 100).round(1)
        coord_resumen = coord_resumen.sort_values("total", ascending=False).reset_index(drop=True)

        st.markdown('<div class="sec-title">Resumen por coordinador</div>',
                    unsafe_allow_html=True)

        def color_complet(val):
            if val >= 95:  return "background-color:#D4EDDA;color:#155724;font-weight:600"
            if val >= 85:  return "background-color:#FFF3CD;color:#856404;font-weight:600"
            return                "background-color:#F8D7DA;color:#721C24;font-weight:600"

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

        # ── Detalle por encuestador (colapsado) ───────────────────────────────
        with st.expander("📋 Ver detalle por encuestador", expanded=False):
            st.caption(
                "⚠️ El nombre del encuestador es texto libre en Bubble. "
                "Si un encuestador usa variantes de su nombre, sus registros aparecerán "
                "en filas separadas y las métricas individuales estarán subestimadas. "
                "Usa la tabla de coordinadores como referencia principal."
            )

            resumen = (
                df.groupby(["encuestador_id", "encuestador_nombre"])
                .agg(
                    total          =("folio",         "count"),
                    terminadas     =("terminada",      "sum"),
                    dias_activo    =("fecha",          "nunique"),
                    dur_prom       =("duracion_min",   "mean"),
                    secciones      =("seccion",        "nunique"),
                    municipios_lista=("municipio",     lambda x: x.dropna().unique().tolist()),
                ).reset_index()
            )
            resumen["prom_dia"]   = (resumen["total"] / resumen["dias_activo"]).round(1)
            resumen["dur_prom"]   = pd.to_numeric(resumen["dur_prom"], errors="coerce").round(1)
            resumen["terminadas"] = resumen["terminadas"].astype(int)
            resumen["pct_complet"]= (resumen["terminadas"] / resumen["total"] * 100).round(1)

            if bubble_tiene_coordinador and "coordinador" in df.columns:
                coord_map = (df.groupby("encuestador_id")["coordinador"]
                             .agg(lambda x: x.dropna().mode()[0] if not x.dropna().empty else "Sin asignar")
                             .to_dict())
                resumen["coordinador"] = resumen["encuestador_id"].map(coord_map).fillna("Sin asignar")
            else:
                def coord_desde_config(munis):
                    if not munis: return "Sin asignar"
                    coords = COORDINADORES.get(munis[0], ["Sin asignar"])
                    return coords[0] if len(coords) == 1 else "Múltiple"
                resumen["coordinador"] = resumen["municipios_lista"].apply(coord_desde_config)

            resumen["meta"]     = resumen["dias_activo"] * META_DIA
            resumen["pct_meta"] = (resumen["total"] / resumen["meta"] * 100).round(1)

            def distrito_predominante(enc_id):
                secs = df[df["encuestador_id"] == enc_id]["seccion"].dropna()
                if secs.empty: return "—"
                distritos = secs.map(lambda s: SECCION_DISTRITO.get(int(s), None)).dropna()
                if distritos.empty: return "—"
                moda = distritos.mode()
                return f"D{int(moda.iloc[0])}" if len(moda) == 1 else f"D{int(moda.iloc[0])}+"
            resumen["distrito"] = resumen["encuestador_id"].apply(distrito_predominante)

            resumen = resumen.sort_values("pct_meta", ascending=False).reset_index(drop=True)

            n_verde    = (resumen["pct_meta"] >= 100).sum()
            n_amarillo = ((resumen["pct_meta"] >= 75) & (resumen["pct_meta"] < 100)).sum()
            n_rojo     = (resumen["pct_meta"] < 75).sum()

            m1, m2, m3, _ = st.columns([1, 1, 1, 3])
            m1.metric("🟢 En meta",   int(n_verde),    help=f"≥ 100% de meta ({META_DIA} enc/día)")
            m2.metric("🟡 En riesgo", int(n_amarillo), help="75–99% de meta")
            m3.metric("🔴 Bajo meta", int(n_rojo),     help="< 75% de meta")

            def color_pct(val):
                if val >= 100: return "background-color:#D4EDDA;color:#155724;font-weight:600"
                if val >= 75:  return "background-color:#FFF3CD;color:#856404;font-weight:600"
                return                "background-color:#F8D7DA;color:#721C24;font-weight:600"

            tbl = resumen[[
                "encuestador_nombre", "coordinador", "distrito",
                "total", "terminadas", "pct_complet",
                "meta", "pct_meta", "dur_prom", "dias_activo", "secciones"
            ]].copy()
            tbl.columns = [
                "Encuestador", "Coordinador", "Distrito",
                "Levantadas", "Terminadas", "% Complet.",
                "Meta", "% Meta", "Dur. prom (min)", "Días activo", "Secciones"
            ]
            tbl_styled = (tbl.style
                .map(color_pct,     subset=["% Meta"])
                .map(color_complet, subset=["% Complet."])
                .map(color_dur,     subset=["Dur. prom (min)"])
                .format({"% Meta": "{:.1f}%", "% Complet.": "{:.1f}%", "Dur. prom (min)": "{:.1f}"})
                .set_properties(**{"font-family": "IBM Plex Sans", "font-size": "13px"})
            )
            st.dataframe(tbl_styled, use_container_width=True, hide_index=True, height=360)
            st.caption(
                f"🟢 En meta: ≥100% · Meta = días activo × {META_DIA} enc/día   "
                f"🟡 En riesgo: 75–99%   🔴 Bajo meta: <75%   "
                f"· Duración esperada: {DUR_MIN_MIN}–{DUR_MAX_MIN} min"
            )

            st.markdown('<div class="sec-title">Distribución estadística del equipo</div>',
                        unsafe_allow_html=True)
            d1, d2 = st.columns(2)

            with d1:
                fig = px.histogram(
                    resumen, x="prom_dia", nbins=max(len(resumen), 5),
                    color_discrete_sequence=[AZUL_L],
                    labels={"prom_dia": "Encuestas promedio / día"},
                    title="Productividad diaria — distribución del equipo",
                )
                fig.add_vline(x=META_DIA, line_dash="dash", line_color=VERDE,
                              annotation_text=f"Meta ({META_DIA})", annotation_position="top right")
                fig.add_vline(x=UMBRAL_AMARILLO, line_dash="dot", line_color=ROJO,
                              annotation_text=f"Mínimo ({UMBRAL_AMARILLO})", annotation_position="top left")
                fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                  font_family="IBM Plex Sans", margin=dict(t=50, b=10))
                st.plotly_chart(fig, use_container_width=True)

            with d2:
                df_conf_plot = df[df["duracion_confiable"]] if "duracion_confiable" in df.columns else df
                fig2 = px.box(
                    df_conf_plot, y="duracion_min",
                    color_discrete_sequence=[VERDE],
                    labels={"duracion_min": "Minutos"},
                    title="Duración de entrevistas — solo timestamps confiables",
                )
                fig2.add_hline(y=DUR_MAX_MIN, line_dash="dash", line_color=AMARILLO,
                               annotation_text=f"Máx recomendado ({DUR_MAX_MIN} min)")
                fig2.add_hline(y=DUR_MIN_MIN, line_dash="dot",  line_color=ROJO,
                               annotation_text=f"Mín recomendado ({DUR_MIN_MIN} min)")
                fig2.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                   font_family="IBM Plex Sans", margin=dict(t=50, b=10))
                st.plotly_chart(fig2, use_container_width=True)

        # ── Ficha individual ───────────────────────────────────────────────────
        st.markdown('<div class="sec-title">Ficha individual de encuestador</div>',
                    unsafe_allow_html=True)

        enc_nombres = sorted(df["encuestador_nombre"].dropna().unique().tolist())
        if enc_nombres:
            enc_pick = st.selectbox("Seleccionar encuestador", enc_nombres, key="ficha_enc")
            df_enc   = df[df["encuestador_nombre"] == enc_pick]

            fi1, fi2, fi3, fi4 = st.columns(4)
            fi1.metric("Total encuestas", len(df_enc))
            fi2.metric("Días trabajados", df_enc["fecha"].nunique())
            fi3.metric("Prom/día",        round(len(df_enc) / max(df_enc["fecha"].nunique(), 1), 1))
            fi4.metric("Dur. prom (min)", round(df_enc["duracion_min"].mean(), 1) if len(df_enc) else 0)

            fa1, fa2 = st.columns(2)
            with fa1:
                diario_enc = df_enc.groupby("fecha").size().reset_index(name="n")
                fig3 = px.bar(diario_enc, x="fecha", y="n",
                              color_discrete_sequence=[AZUL_L],
                              labels={"fecha": "Fecha", "n": "Encuestas"},
                              title=f"Encuestas por día — {enc_pick}")
                fig3.add_hline(y=META_DIA, line_dash="dash", line_color=VERDE,
                               annotation_text="Meta")
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
# TAB 3 – PERFIL
# ══════════════════════════════════════════════════════════════════════════════
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
# TAB 4 – RESULTADOS
# ══════════════════════════════════════════════════════════════════════════════
with tab4:

    if total == 0:
        st.info("Sin registros para los filtros seleccionados.")
    else:
        orden_sat = ["Muy satisfecho", "Satisfecho", "Regular", "Insatisfecho"]
        col_sat   = [VERDE, VERDE_L, NARANJA, ROJO]

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