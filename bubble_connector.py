"""
CEOP · bubble_connector.py
Carga paginada desde la Data API de Bubble con caché TTL.
Uso:
    from bubble_connector import get_encuestas
    df = get_encuestas(api_key="...", municipios=["ACAPULCO DE JUAREZ"])
"""
import json
import time
import logging
from datetime import datetime, timezone

import requests
import pandas as pd
import streamlit as st

from config import (
    BUBBLE_ENDPOINT, BUBBLE_PAGE_SIZE,
    CACHE_TTL_SEC, FIELD_MAP, CAMPOS_EXCLUIR,
)

logger = logging.getLogger(__name__)

# ── Paginación y carga bruta ───────────────────────────────────────────────────

def _fetch_all_raw(api_key: str) -> list[dict]:
    """
    Descarga todos los registros de Bubble usando paginación por cursor.
    Filtra en origen:
      - estatus_encuesta == 'Terminada'
      - Created Date >= 2026-04-18 (inicio oficial del operativo)
    Retorna lista de dicts tal como vienen de la API (campos Bubble).
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    constraints = json.dumps([
        {
            "key":              "estatus_encuesta",
            "constraint_type": "equals",
            "value":           "Terminada",
        },
        {
            "key":              "Created Date",
            "constraint_type": "greater than",
            "value":           "2026-04-17T23:59:59.000Z",  # desde 18 abril 2026 — inicio oficial del operativo
        },
    ])
    params   = {
        "limit":       BUBBLE_PAGE_SIZE,
        "cursor":      0,
        "constraints": constraints,
    }
    results  = []
    intentos = 0
    max_intentos = 3

    while True:
        try:
            resp = requests.get(
                BUBBLE_ENDPOINT, headers=headers, params=params, timeout=15
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            intentos += 1
            if intentos >= max_intentos:
                logger.error("Bubble API error tras %d intentos: %s", max_intentos, e)
                raise
            time.sleep(2 ** intentos)  # back-off exponencial
            continue

        data      = resp.json().get("response", {})
        chunk     = data.get("results", [])
        remaining = data.get("remaining", 0)
        results.extend(chunk)

        if remaining == 0:
            break
        params["cursor"] += len(chunk)

    return results


# ── Transformación y limpieza ──────────────────────────────────────────────────

def _transform(records: list[dict]) -> pd.DataFrame:
    """
    Aplica FIELD_MAP, excluye campos PII, deriva duracion_min,
    normaliza fechas y tipos.
    """
    rows = []
    for r in records:
        row = {}
        for bubble_key, app_key in FIELD_MAP.items():
            row[app_key] = r.get(bubble_key)           # None si campo ausente
        rows.append(row)

    df = pd.DataFrame(rows)

    # Fechas
    for col in ("fecha_inicio", "fecha_fin"):
        df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

    # Duración derivada (Modified - Created) en minutos, redondeada a 1 decimal
    df["duracion_min"] = (
        (df["fecha_fin"] - df["fecha_inicio"])
        .dt.total_seconds()
        .div(60)
        .round(1)
    )

    # Fecha de campo = solo la parte date de fecha_inicio (hora local MX)
    df["fecha"] = df["fecha_inicio"].dt.tz_convert("America/Mexico_City").dt.date

    # Sección electoral → int (puede ser None/NaN)
    df["seccion"] = pd.to_numeric(df["seccion"], errors="coerce").astype("Int64")

    # Edad → int
    df["edad"] = pd.to_numeric(df["edad"], errors="coerce").astype("Int64")

    # Municipio → mayúsculas y strip (normalizar vs. MUNICIPIOS dict)
    df["municipio"] = df["municipio"].str.strip().str.upper()

    # ID interno de encuestador (hash del nombre, hasta tener usuarios reales)
    df["encuestador_id"] = df["encuestador_nombre"].apply(
        lambda x: str(abs(hash(str(x)))) if pd.notna(x) else "sin_nombre"
    )

    # Columnas P11 → booleano: tiene valor = True
    p11_cols = [
        "p11_programas_sociales", "p11_empleo", "p11_seguridad",
        "p11_educacion", "p11_salud", "p11_infraestructura", "p11_otra",
    ]
    for col in p11_cols:
        if col in df.columns:
            df[col] = df[col].notna() & (df[col] != "")

    return df


# ── Caché con TTL usando st.session_state ──────────────────────────────────────

def _cache_key(municipios: list[str] | None) -> str:
    key = ",".join(sorted(municipios)) if municipios else "_todos_"
    return f"bubble_cache_{key}"

def _cache_ts_key(municipios: list[str] | None) -> str:
    return _cache_key(municipios) + "_ts"

def _cache_valid(municipios: list[str] | None) -> bool:
    ts = st.session_state.get(_cache_ts_key(municipios))
    if ts is None:
        return False
    return (time.time() - ts) < CACHE_TTL_SEC


# ── Función pública ────────────────────────────────────────────────────────────

def get_encuestas(
    api_key: str,
    municipios: list[str] | None = None,
    force_refresh: bool = False,
) -> tuple[pd.DataFrame, datetime | None]:
    """
    Retorna (df, ultima_actualizacion).

    Parámetros
    ----------
    api_key       : Bearer token de la Data API de Bubble.
    municipios    : Lista de nombres de municipio (tal como aparecen en Bubble,
                    ej. ['ACAPULCO DE JUAREZ']). None = todos.
    force_refresh : Ignora el caché y recarga desde la API.

    Retorna
    -------
    df                  : DataFrame con todos los registros terminados.
    ultima_actualizacion: datetime UTC de la última carga exitosa, o None.
    """
    ck = _cache_key(municipios)
    tk = _cache_ts_key(municipios)

    if not force_refresh and _cache_valid(municipios):
        return st.session_state[ck], _ts_to_dt(st.session_state[tk])

    try:
        raw = _fetch_all_raw(api_key)
        df  = _transform(raw)

        if municipios:
            munis_upper = [m.strip().upper() for m in municipios]
            df = df[df["municipio"].isin(munis_upper)].copy()

        ts = time.time()
        st.session_state[ck] = df
        st.session_state[tk] = ts
        return df, _ts_to_dt(ts)

    except Exception as e:
        logger.warning("No se pudo actualizar desde Bubble: %s. Usando caché.", e)
        cached = st.session_state.get(ck)
        ts     = st.session_state.get(tk)
        if cached is not None:
            return cached, _ts_to_dt(ts)
        # Sin caché ni datos: DataFrame vacío con columnas correctas
        return pd.DataFrame(columns=list(FIELD_MAP.values()) + ["duracion_min", "fecha", "encuestador_id"]), None


def _ts_to_dt(ts: float | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


# ── Script de prueba (ejecutar directamente desde terminal) ───────────────────
if __name__ == "__main__":
    import sys
    import os

    API_KEY = os.getenv("BUBBLE_API_KEY", "3e40b6cbea8e733fe3e6ac89f1f796b5")

    print("Conectando a Bubble...")
    raw = _fetch_all_raw(API_KEY)
    print(f"Registros descargados (estatus=Terminada): {len(raw)}")

    if raw:
        print("\nCampos en el primer registro:")
        for k, v in raw[0].items():
            print(f"  {k!r:35s} → {str(v)[:60]}")

    # Simular transform sin Streamlit
    import types
    mock_ss = {}
    class MockSS:
        def get(self, k, d=None): return mock_ss.get(k, d)
        def __setitem__(self, k, v): mock_ss[k] = v
        def __getitem__(self, k): return mock_ss[k]

    import bubble_connector as bc
    _orig = bc.st
    bc.st = types.SimpleNamespace(session_state=MockSS())

    df, ts = bc.get_encuestas(API_KEY)
    print(f"\nDataFrame generado: {df.shape[0]} filas × {df.shape[1]} columnas")
    print("\nColumnas:", df.columns.tolist())
    print("\nMunicipios encontrados:", df["municipio"].unique().tolist())
    print("\nDuración promedio:", df["duracion_min"].mean().round(2), "min")
    print("\nEstatus (todos deben ser Terminada):", df["estatus"].unique().tolist())

    if "p8_valores_4t" in df.columns:
        print("\n⚠️  Valores únicos de p8_valores_4t (verificar bug P8/P10):")
        print(df["p8_valores_4t"].value_counts().to_string())

    bc.st = _orig
    print("\n✅ Prueba completada.")