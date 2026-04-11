"""
CEOP – Visualizador de Levantamiento Estatal
Guerrero · 2025
Ejecutar: streamlit run app.py
"""
import json
import copy
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium

from bubble_connector import load_data, invalidate_cache

# ══════════════════════════════════════════════════════════════════════════════
# COLUMNAS — nombres exactos del diccionario de variables de Bubble
# Si Bubble cambia un nombre, solo se edita aquí.
# ══════════════════════════════════════════════════════════════════════════════
COL_ID              = "_id"
COL_FECHA           = "Created Date"
COL_ENCUESTADOR     = "nombre_encuestador"
COL_MUNICIPIO       = "municipio"
COL_SECCION         = "seccion_electoral"

COL_P1              = "p1_amlo"
COL_P2              = "p2_claudia"
COL_P3              = "p3_programas_bienestar"
COL_P4              = "p4_delegado_bienestar"
COL_P5              = "p5_conoce_ivan_hernandez"
COL_P6              = "p6_opinion_ivan_hernandez"
COL_P7              = "p7_cercania_ivan_hernandez"
COL_P8              = "p8_valores_4t"
COL_P9              = "p9_votaria_ivan_hernandez"
COL_P10             = "p10_frase"
COL_P11_OPCION      = "p11_prioridad_opcion"
COL_P11_OTRA        = "p11_prioridad_otra"

COL_EDAD            = "edad"
COL_SEXO            = "sexo"
COL_NIVEL_EDU       = "nivel_educativo"
COL_BIENESTAR       = "recibe_programas_bienestar"

# Nota: el demo usaba encuestador_id y duracion_min — no están en Bubble.
# encuestador_id se deriva del nombre; duracion_min no se captura en campo.
# Los KPIs que los usaban se adaptan abajo.

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE PÁGINA
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="CEOP · Guerrero 2025",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

VERDE    = "#2E7D5E"
VERDE_L  = "#52B788"
AZUL     = "#1A3A5C"
AZUL_L   = "#2C6E9E"
NARANJA  = "#E07B39"
ROJO     = "#C0392B"
AMARILLO = "#F5A623"
GRIS_BG  = "#F2F4F7"

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
.kpi-val   {{ font-size: 2rem; font-weight: 700; color: {VERDE}; font-family: 'IBM Plex Mono', monospace; line-height: 1; }}
.kpi-label {{ font-size: 0.73rem; color: #555; text-transform: uppercase; letter-spacing:.05em; margin-top:4px; }}
.kpi-sub   {{ font-size: 0.78rem; color: #888; margin-top: 3px; }}

.kpi-card.azul    {{ border-left-color: {AZUL_L}; }}
.kpi-card.azul .kpi-val {{ color: {AZUL_L}; }}
.kpi-card.naranja {{ border-left-color: {NARANJA}; }}
.kpi-card.naranja .kpi-val {{ color: {NARANJA}; }}

.sec-title {{
    font-size: 1rem; font-weight: 600; color: {AZUL};
    border-bottom: 2px solid {VERDE_L}; padding-bottom: 3px; margin: 16px 0 10px;
}}

section[data-testid="stSidebar"] {{ background: {AZUL}; }}
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] .stMarkdown p {{ color: #B8CDE0 !important; }}
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {{ color: white !important; }}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# CARGA DE DATOS DESDE BUBBLE
# ══════════════════════════════════════════════════════════════════════════════
with st.spinner("Cargando datos desde Bubble..."):
    df_raw, status_msg = load_data()

# Banner de estado si hay advertencia o error
if status_msg:
    st.warning(status_msg) if status_msg.startswith("⚠️") else st.error(status_msg)

if df_raw.empty:
    st.error("No hay datos disponibles. Verifica la conexión con Bubble.")
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# GeoJSON (por ahora Iguala — se expande por municipio en Fase multi-municipio)
# ══════════════════════════════════════════════════════════════════════════════
DATA_DIR = Path(__file__).parent / "data"

@st.cache_data
def load_geojson(fname):
    return json.loads((DATA_DIR / fname).read_text(encoding="utf-8"))

geojson_sec = load_geojson("secciones_iguala.geojson")
geojson_mz  = load_geojson("manzanas_iguala.geojson")


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — FILTROS
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ⚙️ Filtros globales")
    st.markdown("---")

    # Rango de fechas
    fechas = sorted(df_raw[COL_FECHA].dropna().unique())
    if fechas:
        rango = st.date_input("Rango de fechas",
                              value=(fechas[0], fechas[-1]),
                              min_value=fechas[0], max_value=fechas[-1])
    else:
        rango = None

    # Encuestador
    enc_opts = ["Todos"] + sorted(df_raw[COL_ENCUESTADOR].dropna().unique().tolist())
    enc_sel  = st.selectbox("Encuestador", enc_opts)

    # Sección electoral
    sec_opts = ["Todas"] + sorted(df_raw[COL_SECCION].dropna().unique().tolist())
    sec_sel  = st.selectbox("Sección electoral", sec_opts)

    st.markdown("---")

    # Botón de recarga manual
    if st.button("🔄 Recargar datos"):
        invalidate_cache()
        st.rerun()

    st.markdown("**CEOP** · Guerrero · 2025")


# ── Aplicar filtros ───────────────────────────────────────────────────────────
df = df_raw.copy()

if rango and len(rango) == 2:
    df = df[(df[COL_FECHA] >= rango[0]) & (df[COL_FECHA] <= rango[1])]
elif rango and len(rango) == 1:
    df = df[df[COL_FECHA] == rango[0]]

if enc_sel != "Todos":
    df = df[df[COL_ENCUESTADOR] == enc_sel]

if sec_sel != "Todas":
    df = df[df[COL_SECCION] == sec_sel]


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div class="ceop-header">
  <div style="font-size:2.2rem">📋</div>
  <div>
    <h1>Monitoreo de Levantamiento — Guerrero</h1>
    <p>Centro de Estudios de Opinión Pública · {len(df):,} registros en vista actual</p>
  </div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# KPIs GLOBALES
# ══════════════════════════════════════════════════════════════════════════════
total      = len(df)
n_enc      = df[COL_ENCUESTADOR].nunique()
dias       = df[COL_FECHA].nunique()
prom_dia   = round(total / max(dias, 1), 1)
secs_cub   = df[COL_SECCION].nunique()
total_secs = 87   # secciones Iguala — actualizar por municipio en Fase multi
pct_cobert = round(secs_cub / total_secs * 100, 1)

def kpi(col, val, label, sub="", cls=""):
    col.markdown(f"""
    <div class="kpi-card {cls}">
      <div class="kpi-val">{val}</div>
      <div class="kpi-label">{label}</div>
      <div class="kpi-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)

c1, c2, c3, c4, c5 = st.columns(5)
kpi(c1, f"{total:,}",     "Encuestas levantadas",   f"{dias} días de campo")
kpi(c2, n_enc,            "Encuestadores activos",   f"de {df_raw[COL_ENCUESTADOR].nunique()} total", "azul")
kpi(c3, f"{prom_dia}",    "Promedio diario",         "encuestas / día", "azul")
kpi(c4, f"{secs_cub}",    "Secciones cubiertas",     f"de {total_secs} en el municipio", "naranja")
kpi(c5, f"{pct_cobert}%", "Cobertura territorial",   f"{total_secs - secs_cub} secciones pendientes", "naranja")

st.markdown("<br>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
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

    META_DIA = 12
    MIN_DIA  = 8

    resumen = (
        df.groupby(COL_ENCUESTADOR)
        .agg(
            total       = (COL_ID, "count"),
            dias_activo = (COL_FECHA, "nunique"),
            secciones   = (COL_SECCION, "nunique"),
        ).reset_index()
    )
    resumen["prom_dia"] = (resumen["total"] / resumen["dias_activo"]).round(1)
    resumen = resumen.sort_values("prom_dia", ascending=False).reset_index(drop=True)

    def sem_prom(v):
        if v >= META_DIA:  return "verde"
        if v >= MIN_DIA:   return "amarillo"
        return "rojo"

    def color_prod(val):
        s = sem_prom(val)
        if s == "verde":    return "background-color:#D4EDDA; color:#155724; font-weight:600"
        if s == "amarillo": return "background-color:#FFF3CD; color:#856404; font-weight:600"
        return                     "background-color:#F8D7DA; color:#721C24; font-weight:600"

    # Semáforo rápido
    st.markdown('<div class="sec-title">Semáforo de desempeño — equipo completo</div>',
                unsafe_allow_html=True)

    n_verde    = (resumen["prom_dia"].apply(sem_prom) == "verde").sum()
    n_amarillo = (resumen["prom_dia"].apply(sem_prom) == "amarillo").sum()
    n_rojo     = (resumen["prom_dia"].apply(sem_prom) == "rojo").sum()
    m1, m2, m3, _ = st.columns([1, 1, 1, 3])
    m1.metric("🟢 En meta",   n_verde,    help=f"≥ {META_DIA} enc/día")
    m2.metric("🟡 En riesgo", n_amarillo, help=f"{MIN_DIA}–{META_DIA-1} enc/día")
    m3.metric("🔴 Bajo meta", n_rojo,     help=f"< {MIN_DIA} enc/día")

    # Tabla
    tbl = resumen.copy()
    tbl.columns = ["Encuestador", "Total enc.", "Días activo", "Secciones", "Prom/día"]
    tbl = tbl[["Encuestador", "Total enc.", "Días activo", "Prom/día", "Secciones"]]
    tbl_styled = (tbl.style
        .map(color_prod, subset=["Prom/día"])
        .format({"Prom/día": "{:.1f}"})
        .set_properties(**{"font-family": "IBM Plex Sans", "font-size": "13px"})
    )
    st.dataframe(tbl_styled, use_container_width=True, hide_index=True, height=380)
    st.caption(f"🟢 Meta: ≥{META_DIA} enc/día   🟡 En riesgo: {MIN_DIA}–{META_DIA-1}   🔴 Bajo meta: <{MIN_DIA}")

    # Distribución de productividad
    st.markdown('<div class="sec-title">Distribución de productividad del equipo</div>',
                unsafe_allow_html=True)
    fig = px.histogram(resumen, x="prom_dia", nbins=15,
                       color_discrete_sequence=[AZUL_L],
                       labels={"prom_dia": "Encuestas promedio / día"},
                       title="Productividad diaria por encuestador")
    fig.add_vline(x=META_DIA, line_dash="dash", line_color=VERDE,
                  annotation_text=f"Meta ({META_DIA})", annotation_position="top right")
    fig.add_vline(x=MIN_DIA,  line_dash="dot",  line_color=ROJO,
                  annotation_text=f"Mínimo ({MIN_DIA})", annotation_position="top left")
    fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                      font_family="IBM Plex Sans", margin=dict(t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # Ficha individual
    st.markdown('<div class="sec-title">Ficha individual de encuestador</div>',
                unsafe_allow_html=True)
    enc_pick = st.selectbox("Seleccionar encuestador",
                            sorted(df[COL_ENCUESTADOR].unique().tolist()),
                            key="ficha_enc")
    df_enc = df[df[COL_ENCUESTADOR] == enc_pick]

    if df_enc.empty:
        st.info("Sin datos para el encuestador seleccionado con los filtros actuales.")
    else:
        fi1, fi2, fi3 = st.columns(3)
        fi1.metric("Total encuestas", len(df_enc))
        fi2.metric("Días trabajados", df_enc[COL_FECHA].nunique())
        fi3.metric("Prom/día", round(len(df_enc) / df_enc[COL_FECHA].nunique(), 1))

        diario_enc = df_enc.groupby(COL_FECHA).size().reset_index(name="n")
        fig3 = px.bar(diario_enc, x=COL_FECHA, y="n",
                      color_discrete_sequence=[AZUL_L],
                      labels={COL_FECHA: "Fecha", "n": "Encuestas"},
                      title=f"Encuestas por día — {enc_pick}")
        fig3.add_hline(y=META_DIA, line_dash="dash", line_color=VERDE,
                       annotation_text="Meta")
        fig3.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                           font_family="IBM Plex Sans", margin=dict(t=50, b=10))
        st.plotly_chart(fig3, use_container_width=True)

        sec_enc = (df_enc.groupby(COL_SECCION).size()
                   .reset_index(name="n").sort_values("n", ascending=False))
        st.caption(f"Secciones trabajadas: " +
                   ", ".join([f"**{r[COL_SECCION]}** ({r['n']})"
                              for _, r in sec_enc.iterrows()]))


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 – MAPA DE COBERTURA
# ══════════════════════════════════════════════════════════════════════════════
with tab2:

    sec_cnt = df.groupby(COL_SECCION).agg(
        n_enc_total     = (COL_ID, "count"),
        n_encuestadores = (COL_ENCUESTADOR, "nunique"),
    ).reset_index()

    st.markdown('<div class="sec-title">Cobertura territorial por sección electoral</div>',
                unsafe_allow_html=True)

    mk1, mk2, mk3, mk4 = st.columns(4)
    secs_con_data = sec_cnt[COL_SECCION].nunique()
    secs_sin_data = total_secs - secs_con_data
    max_sec = sec_cnt.loc[sec_cnt["n_enc_total"].idxmax()] if len(sec_cnt) else None

    def mk(col, val, label, sub="", cls=""):
        col.markdown(f"""
        <div class="kpi-card {cls}" style="margin-bottom:12px">
          <div class="kpi-val">{val}</div>
          <div class="kpi-label">{label}</div>
          <div class="kpi-sub">{sub}</div>
        </div>""", unsafe_allow_html=True)

    mk(mk1, secs_con_data, "Secciones con levantamiento", f"de {total_secs} totales")
    mk(mk2, secs_sin_data, "Secciones sin cobertura", "pendientes de visitar",
       "naranja" if secs_sin_data > 0 else "")
    mk(mk3, int(max_sec["n_enc_total"]) if max_sec is not None else 0,
            "Máx. encuestas en sección",
            f"Sección {int(max_sec[COL_SECCION])}" if max_sec is not None else "")
    mk(mk4, round(sec_cnt["n_enc_total"].mean(), 1) if len(sec_cnt) else 0,
            "Promedio por sección", "encuestas")

    # Mapa coroplético
    mapa = folium.Map(location=[18.34, -99.54], zoom_start=12,
                      tiles="CartoDB positron")

    folium.GeoJson(
        geojson_mz,
        style_function=lambda f: {
            "fillColor": "#E8EEF4", "color": "#C5D0DC",
            "weight": 0.4, "fillOpacity": 0.5,
        },
        name="Manzanas", show=True,
    ).add_to(mapa)

    sec_lookup = sec_cnt.set_index(COL_SECCION)["n_enc_total"].to_dict()
    enc_lookup = sec_cnt.set_index(COL_SECCION)["n_encuestadores"].to_dict()
    max_val    = sec_cnt["n_enc_total"].max() if len(sec_cnt) else 1

    geojson_sec_enriq = copy.deepcopy(geojson_sec)
    for feature in geojson_sec_enriq["features"]:
        sec = int(feature["properties"]["SECCION"])
        n   = sec_lookup.get(sec, 0)
        feature["properties"]["enc_total"]     = int(n)
        feature["properties"]["encuestadores"] = int(enc_lookup.get(sec, 0))
        feature["properties"]["estado"]        = "Con levantamiento" if n > 0 else "Sin levantamiento"

    def style_sec(feature):
        n = feature["properties"].get("enc_total", 0)
        if n == 0:
            return {"fillColor": "#E8E8E8", "color": "#BBBBBB",
                    "weight": 0.8, "fillOpacity": 0.65}
        intensity = n / max_val
        r = int(255 - intensity * (255 - 46))
        g = int(255 - intensity * (255 - 125))
        b = int(255 - intensity * (255 - 94))
        return {"fillColor": f"#{r:02X}{g:02X}{b:02X}", "color": "#1A5C42",
                "weight": 1.4, "fillOpacity": 0.78}

    folium.GeoJson(
        geojson_sec_enriq,
        style_function=style_sec,
        highlight_function=lambda f: {"fillOpacity": 0.95, "weight": 2.5, "color": "#1A3A5C"},
        tooltip=folium.GeoJsonTooltip(
            fields=["SECCION", "estado", "enc_total", "encuestadores"],
            aliases=["Sección:", "Estado:", "Encuestas:", "Encuestadores:"],
            localize=True, sticky=True,
            style=(
                "background-color:white; border:1px solid #2E7D5E; border-radius:6px;"
                "padding:8px 12px; font-family:'IBM Plex Sans',sans-serif; font-size:13px;"
            ),
        ),
        name="Secciones electorales",
    ).add_to(mapa)

    folium.LayerControl().add_to(mapa)
    st_folium(mapa, width="100%", height=540, returned_objects=[])

    if secs_sin_data > 0:
        all_secs = {int(f["properties"]["SECCION"]) for f in geojson_sec["features"]}
        covered  = set(sec_cnt[COL_SECCION].dropna().astype(int).tolist())
        pending  = sorted(all_secs - covered)
        st.markdown('<div class="sec-title">Secciones sin encuestas levantadas</div>',
                    unsafe_allow_html=True)
        st.write(f"{len(pending)} secciones pendientes: " +
                 ", ".join(str(s) for s in pending))


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 – PERFIL DE ENTREVISTADOS
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<div class="sec-title">Perfil sociodemográfico de entrevistados</div>',
                unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)

    with c1:
        cnt = df[COL_SEXO].value_counts().reset_index()
        cnt.columns = ["Sexo", "n"]
        fig = px.pie(cnt, names="Sexo", values="n", hole=0.42,
                     color_discrete_sequence=[AZUL_L, NARANJA, "#ccc"],
                     title="Distribución por sexo")
        fig.update_layout(font_family="IBM Plex Sans", margin=dict(t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        edu_order = ["Primaria", "Secundaria", "Preparatoria", "Universidad", "Posgrado"]
        cnt = df[COL_NIVEL_EDU].value_counts().reindex(edu_order).reset_index()
        cnt.columns = ["Nivel", "n"]
        fig2 = px.bar(cnt, x="Nivel", y="n", text="n",
                      color_discrete_sequence=[VERDE],
                      title="Nivel educativo")
        fig2.update_traces(textposition="outside")
        fig2.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                           font_family="IBM Plex Sans", margin=dict(t=40, b=0))
        st.plotly_chart(fig2, use_container_width=True)

    with c3:
        cnt = df[COL_BIENESTAR].value_counts().reset_index()
        cnt.columns = ["Recibe Bienestar", "n"]
        fig3 = px.pie(cnt, names="Recibe Bienestar", values="n", hole=0.42,
                      color_discrete_sequence=[VERDE, "#ccc"],
                      title="¿Recibe programa Bienestar?")
        fig3.update_layout(font_family="IBM Plex Sans", margin=dict(t=40, b=0))
        st.plotly_chart(fig3, use_container_width=True)

    # Pirámide de edades
    st.markdown('<div class="sec-title">Pirámide de edades</div>', unsafe_allow_html=True)
    df_pir = df.copy()
    df_pir["grupo_edad"] = pd.cut(df_pir[COL_EDAD],
                                   bins=[18, 25, 35, 45, 55, 65, 100],
                                   labels=["18-25", "26-35", "36-45", "46-55", "56-65", "65+"])
    pir = df_pir.groupby(["grupo_edad", COL_SEXO]).size().reset_index(name="n")
    pir = pir[pir[COL_SEXO].isin(["Hombre", "Mujer"])]
    pir.loc[pir[COL_SEXO] == "Hombre", "n"] *= -1
    fig_p = px.bar(pir, x="n", y="grupo_edad", color=COL_SEXO, orientation="h",
                   color_discrete_map={"Hombre": AZUL_L, "Mujer": NARANJA},
                   labels={"n": "Conteo", "grupo_edad": ""},
                   title="Pirámide de edades", height=300)
    fig_p.update_xaxes(tickvals=[-300, -200, -100, 0, 100, 200, 300],
                        ticktext=[300, 200, 100, 0, 100, 200, 300])
    fig_p.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                        font_family="IBM Plex Sans", margin=dict(t=40, b=10))
    st.plotly_chart(fig_p, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 – RESULTADOS DEL INSTRUMENTO
# ══════════════════════════════════════════════════════════════════════════════
with tab4:

    def pct_bar(df_in, campo, titulo, orden=None, colors=None, height=260):
        cnt = df_in[campo].value_counts(normalize=True).mul(100).round(1).reset_index()
        cnt.columns = ["Respuesta", "Porcentaje"]
        if orden:
            cnt["Respuesta"] = pd.Categorical(cnt["Respuesta"], categories=orden, ordered=True)
            cnt = cnt.sort_values("Respuesta")
        cs  = colors or [VERDE_L, VERDE, AZUL_L, NARANJA, ROJO, "#aaa"]
        fig = px.bar(cnt, x="Porcentaje", y="Respuesta", orientation="h",
                     color="Respuesta", color_discrete_sequence=cs,
                     text=cnt["Porcentaje"].apply(lambda x: f"{x}%"),
                     title=titulo, height=height)
        fig.update_traces(textposition="outside")
        fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                          showlegend=False, font_family="IBM Plex Sans",
                          margin=dict(t=45, b=5, l=220), xaxis_range=[0, 70])
        return fig

    orden_sat = ["Muy satisfecho", "Satisfecho", "Regular", "Insatisfecho"]
    col_sat   = [VERDE, VERDE_L, NARANJA, ROJO]

    # Sección A
    st.markdown('<div class="sec-title">Sección A – Contexto de Gobierno y 4T</div>',
                unsafe_allow_html=True)
    a1, a2 = st.columns(2)
    with a1:
        st.plotly_chart(pct_bar(df, COL_P1, "P1. Satisfacción con AMLO",
                                orden_sat, col_sat), use_container_width=True)
    with a2:
        st.plotly_chart(pct_bar(df, COL_P2, "P2. Satisfacción con Claudia Sheinbaum",
                                orden_sat, col_sat), use_container_width=True)
    st.plotly_chart(pct_bar(df, COL_P3,
                            "P3. ¿Los Programas del Bienestar han mejorado la vida en Guerrero?",
                            ["Mucho", "Algo", "Poco", "Nada"], col_sat, height=220),
                    use_container_width=True)

    # Sección B
    st.markdown('<div class="sec-title">Sección B – Posicionamiento de Iván Hernández</div>',
                unsafe_allow_html=True)
    b1, b2 = st.columns(2)
    with b1:
        st.plotly_chart(pct_bar(df, COL_P5, "P5. ¿Ha escuchado de Iván Hernández?",
                                colors=[VERDE, "#ccc"]), use_container_width=True)
        df_conoce = df[df[COL_P6].notna() & (df[COL_P6] != "No aplica")]
        if not df_conoce.empty:
            st.plotly_chart(pct_bar(df_conoce, COL_P6,
                                    "P6. Opinión sobre Iván H. (entre quienes lo conocen)",
                                    ["Muy buena", "Buena", "Regular", "Mala", "No sabe / No contesta"],
                                    [VERDE, VERDE_L, NARANJA, ROJO, "#aaa"]),
                            use_container_width=True)
    with b2:
        st.plotly_chart(pct_bar(df, COL_P7, "P7. Cercanía percibida con la gente",
                                ["Muy cercano", "Algo cercano", "Poco cercano", "No sabe / No contesta"],
                                [VERDE, VERDE_L, NARANJA, "#aaa"]), use_container_width=True)
        st.plotly_chart(pct_bar(df, COL_P8, "P8. ¿Representa los valores de la 4T?",
                                ["Sí, totalmente", "En parte", "No", "No sabe / No contesta"],
                                [VERDE, VERDE_L, ROJO, "#aaa"]), use_container_width=True)

    # Sección C
    st.markdown('<div class="sec-title">Sección C – Intención de Voto y Percepción</div>',
                unsafe_allow_html=True)
    st.plotly_chart(pct_bar(df, COL_P9,
                            "P9. Si hubiera elecciones para gobernador con Iván Hernández, ¿votaría por él?",
                            ["Sí, con seguridad", "Probablemente sí", "Probablemente no", "No", "No sabe / No contesta"],
                            [VERDE, VERDE_L, NARANJA, ROJO, "#aaa"], height=240),
                    use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(pct_bar(df, COL_P10,
                                "P10. ¿Qué frase describe mejor a Iván Hernández?"),
                        use_container_width=True)
    with c2:
        st.plotly_chart(pct_bar(df, COL_P11_OPCION,
                                "P11. Prioridad #1 para el próximo gobernador"),
                        use_container_width=True)

    st.markdown("---")
    csv_out = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Descargar datos filtrados (CSV)", csv_out,
                       "ceop_guerrero_filtrado.csv", "text/csv")