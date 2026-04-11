"""
CEOP – Conector Bubble API
Encuesta de Inducción Guerrero

Requiere en .streamlit/secrets.toml:
    BUBBLE_API_TOKEN = "tu-private-key"
    BUBBLE_BASE_URL  = "https://encuestaopguerrero.bubbleapps.io/version-test"
"""

import requests
import pandas as pd
import streamlit as st
from datetime import datetime

# ── Configuración ──────────────────────────────────────────────────────────────
DATATYPE   = "encuesta"   # tipo de dato en Bubble (minúsculas en Data API)
CACHE_TTL  = 600          # segundos (10 min)
PAGE_LIMIT = 100          # máximo por página en Bubble


# ── Columnas — nombres exactos del diccionario de variables ───────────────────
# Punto único de verdad: si Bubble cambia un nombre, solo se edita aquí.

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

COL_FECHA           = "Created Date"    # campo automático de Bubble
COL_ID              = "_id"             # campo automático de Bubble


# ── Helpers ───────────────────────────────────────────────────────────────────

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {st.secrets['BUBBLE_API_TOKEN']}",
        "Content-Type":  "application/json",
    }


def _base_url() -> str:
    base = st.secrets["BUBBLE_BASE_URL"].rstrip("/")
    return f"{base}/api/1.1/obj/{DATATYPE}"


# ── Carga con paginación automática ───────────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fetch_bubble_data() -> pd.DataFrame:
    """
    Descarga todos los registros paginando automáticamente (100 por request).
    Devuelve DataFrame con los campos tal como los nombra Bubble.
    """
    all_results = []
    cursor      = 0

    while True:
        response = requests.get(
            _base_url(),
            headers=_headers(),
            params={"cursor": cursor, "limit": PAGE_LIMIT},
            timeout=15,
        )

        if response.status_code != 200:
            st.error(f"Error Bubble — HTTP {response.status_code}: {response.text[:200]}")
            break

        page      = response.json().get("response", {})
        results   = page.get("results", [])
        remaining = page.get("remaining", 0)

        all_results.extend(results)

        if remaining == 0 or not results:
            break

        cursor += len(results)

    if not all_results:
        return pd.DataFrame()

    df = pd.DataFrame(all_results)

    # Coerciones de tipo
    if COL_FECHA in df.columns:
        df[COL_FECHA] = pd.to_datetime(df[COL_FECHA], errors="coerce").dt.date
    if COL_EDAD in df.columns:
        df[COL_EDAD] = pd.to_numeric(df[COL_EDAD], errors="coerce")
    if COL_SECCION in df.columns:
        df[COL_SECCION] = pd.to_numeric(df[COL_SECCION], errors="coerce").astype("Int64")

    return df


# ── Carga segura con fallback ─────────────────────────────────────────────────

def load_data() -> tuple[pd.DataFrame, str]:
    """
    Llama a fetch_bubble_data() con manejo de errores y fallback.

    Returns:
        (DataFrame, mensaje_estado)
        mensaje_estado es "" si todo fue bien.
    """
    CACHE_KEY = "ceop_last_df"
    TS_KEY    = "ceop_last_ts"

    try:
        df = fetch_bubble_data()

        if df.empty:
            return df, "⚠️ La API respondió pero no hay registros disponibles."

        st.session_state[CACHE_KEY] = df
        st.session_state[TS_KEY]    = datetime.now().strftime("%d/%m/%Y %H:%M")
        return df, ""

    except requests.ConnectionError:
        msg = "Sin conexión — no se pudo alcanzar Bubble."
    except requests.Timeout:
        msg = "Bubble no respondió en 15 s (timeout)."
    except Exception as e:
        msg = f"Error inesperado: {e}"

    fallback = st.session_state.get(CACHE_KEY)
    last_ts  = st.session_state.get(TS_KEY, "hora desconocida")

    if fallback is not None:
        return fallback, f"⚠️ {msg} Mostrando datos al {last_ts}."

    return pd.DataFrame(), f"🔴 {msg} Sin datos previos disponibles."


# ── Invalidar caché ───────────────────────────────────────────────────────────

def invalidate_cache():
    """Fuerza recarga desde Bubble en el próximo render."""
    fetch_bubble_data.clear()
