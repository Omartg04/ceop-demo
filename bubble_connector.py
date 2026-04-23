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
import re
import unicodedata
from datetime import datetime, timezone

import requests
import pandas as pd
import streamlit as st

from config import (
    BUBBLE_ENDPOINT, BUBBLE_PAGE_SIZE,
    CACHE_TTL_SEC, FIELD_MAP, CAMPOS_EXCLUIR,
)

logger = logging.getLogger(__name__)

# ── Constantes de corte temporal ──────────────────────────────────────────────
# A partir de esta fecha los encuestadores usan login individual en Bubble.
# Los registros anteriores usan hash(nombre_normalizado) como encuestador_id.
# Los registros de esta fecha en adelante usan Created By (ID estable de Bubble).
INICIO_LOGIN_BUBBLE = pd.Timestamp("2026-04-25").date()

# ── Normalización de nombres ───────────────────────────────────────────────────

def normalizar_nombre(s: str | None) -> str:
    """
    Normalización agresiva para colapsar variantes del mismo nombre.
    Pasos: strip → mayúsculas → quitar acentos → solo ASCII → espacios múltiples → 1.
    Ejemplos:
      "Maricela Pineda  Pita" → "MARICELA PINEDA PITA"
      "Samir Ávila"           → "SAMIR AVILA"
      "SAMIR AVILA"           → "SAMIR AVILA"
    """
    if not s or str(s).strip() in ("", "None", "nan"):
        return "SIN NOMBRE"
    s = str(s).strip().upper()
    # Quitar acentos y diacríticos (ñ → N, á → A, etc.)
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    # Solo letras, números y espacios
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    # Colapsar espacios múltiples
    s = re.sub(r"\s+", " ", s).strip()
    return s or "SIN NOMBRE"


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
        # Campos de contacto como booleanos — PII nunca sale del transform
        row["tiene_celular"] = bool(r.get("celular_encuestado"))
        row["tiene_correo"]  = bool(r.get("email_encuestado"))
        # Email del encuestador (perfil Bubble) — no es PII del entrevistado
        row["encuestador_email"] = r.get("email_encuestador", "")
        # ID de usuario Bubble — usado como encuestador_id desde INICIO_LOGIN_BUBBLE
        row["_created_by"] = r.get("Created By", "")
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

    # Excluir registros anteriores al inicio oficial del operativo (18 abril 2026).
    # El registro del 17 abril es una prueba que se coló — no pertenece al levantamiento.
    INICIO_OPERATIVO = pd.Timestamp("2026-04-18").date()
    df = df[df["fecha"] >= INICIO_OPERATIVO].copy()

    # duracion_confiable: False para el batch manual subido el 19 de abril.
    # Esos 565 registros fueron capturados en vivo el 18 pero subidos un día después,
    # por lo que sus timestamps no reflejan la duración real de la entrevista.
    # Se excluyen del semáforo de duración pero se mantienen en todos los demás conteos.
    FECHA_BATCH_MANUAL = pd.Timestamp("2026-04-19").date()
    df["duracion_confiable"] = df["fecha"] != FECHA_BATCH_MANUAL

    # Sección electoral → int (puede ser None/NaN)
    df["seccion"] = pd.to_numeric(df["seccion"], errors="coerce").astype("Int64")

    # Edad → int
    df["edad"] = pd.to_numeric(df["edad"], errors="coerce").astype("Int64")

    # Encuesta terminada — columna booleana derivada del estatus
    # Se usa como indicador de completitud; el filtro operativo ya no está en origen.
    df["terminada"] = df["estatus"].astype(str).str.strip() == "Terminada"

    # Municipio → mayúsculas y strip (normalizar vs. MUNICIPIOS dict)
    df["municipio"] = df["municipio"].str.strip().str.upper()

    # Nombre encuestador — normalización agresiva para colapsar variantes
    # (doble espacio, acentos, mayúsculas/minúsculas, caracteres especiales)
    df["encuestador_nombre"] = df["encuestador_nombre"].apply(normalizar_nombre)

    # ID de encuestador — lógica dual según período:
    # · Antes del 25 abril (texto libre): hash del nombre normalizado
    # · Desde el 25 abril (login Bubble): Created By — estable, único por usuario
    # Esto permite que ambos períodos coexistan sin mezclar identidades.
    def _enc_id(row):
        if row["fecha"] is not None and row["fecha"] >= INICIO_LOGIN_BUBBLE:
            cb = str(row.get("_created_by", "")).strip()
            if cb and cb not in ("", "None"):
                return cb
        return str(abs(hash(row["encuestador_nombre"])))

    df["encuestador_id"] = df.apply(_enc_id, axis=1)
    # _created_by fue auxiliar — no lo exponemos fuera del conector
    df.drop(columns=["_created_by"], inplace=True)

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

    # ── Desglose de estatus ────────────────────────────────────────────────────
    total      = len(df)
    terminadas = df["terminada"].sum()
    iniciadas  = total - terminadas
    print(f"\n── Estatus ──────────────────────────────")
    print(f"  Total levantadas : {total}")
    print(f"  Terminadas       : {terminadas}  ({terminadas/total*100:.1f}% del total)" if total else "  Sin registros")
    print(f"  Iniciadas        : {iniciadas}")
    print(f"  Valores únicos   : {df['estatus'].unique().tolist()}")

    # ── Datos de contacto (sobre terminadas) ──────────────────────────────────
    df_t = df[df["terminada"]]
    n_t  = len(df_t)
    if n_t:
        cel = df_t["tiene_celular"].sum()
        cor = df_t["tiene_correo"].sum()
        print(f"\n── Contacto (sobre {n_t} terminadas) ────")
        print(f"  Con celular : {cel}  ({cel/n_t*100:.1f}%)")
        print(f"  Con correo  : {cor}  ({cor/n_t*100:.1f}%)")
    else:
        print("\n  Sin encuestas terminadas para calcular contacto.")

    if "p8_valores_4t" in df.columns:
        print("\n⚠️  Valores únicos de p8_valores_4t (verificar bug P8/P10):")
        print(df["p8_valores_4t"].value_counts().to_string())

    # ── Distribución de duraciones (solo timestamps confiables) ───────────────
    df_conf  = df[df["terminada"] & df["duracion_confiable"]]
    df_batch = df[df["terminada"] & ~df["duracion_confiable"]]
    print(f"\n── Duraciones (terminadas con timestamp confiable: {len(df_conf)}) ──")
    if len(df_conf):
        print(df_conf["duracion_min"].describe().round(1))
        bins   = [-1, 0, 2, 5, 10, 20, 30, 60, 9999]
        labels = ["negativa","0-2 min","2-5 min","5-10 min","10-20 min","20-30 min","30-60 min",">60 min"]
        print(df_conf["duracion_min"].pipe(
            lambda s: pd.cut(s, bins=bins, labels=labels).value_counts().sort_index()
        ))
    print(f"\n── Batch manual excluido del semáforo: {len(df_batch)} registros ──")

    # ── Registros por fecha de campo ──────────────────────────────────────────
    print("\n── Registros por fecha de campo ─────────────────")
    print(df[df["terminada"]]["fecha"].value_counts().sort_index())

    # ── Origen de encuestador_id ───────────────────────────────────────────────
    # Diagnóstico para verificar que el login individual de Bubble está funcionando.
    # Desde el 25 abril los IDs deberían venir de Created By (largo ~40 chars),
    # no del hash del nombre (numérico). Si post-25 abril hay muchos hashes,
    # revisar que Created By esté llegando en los registros nuevos.
    print(f"\n── Origen de encuestador_id (corte: {INICIO_LOGIN_BUBBLE}) ──────────")
    if total:
        df_nuevo    = df[df["fecha"] >= INICIO_LOGIN_BUBBLE]
        df_historico = df[df["fecha"] < INICIO_LOGIN_BUBBLE]

        # Created By llega como string largo tipo '1776902705528x187...'
        # El hash es numérico puro. Distinguimos por si contiene 'x'.
        def _es_created_by(enc_id: str) -> bool:
            return "x" in str(enc_id)

        n_nuevo      = len(df_nuevo)
        n_historico  = len(df_historico)
        n_login      = df_nuevo["encuestador_id"].apply(_es_created_by).sum() if n_nuevo else 0
        n_hash_nuevo = n_nuevo - n_login

        print(f"  Registros históricos (<25 abr) : {n_historico:>6}  → hash nombre (esperado)")
        print(f"  Registros nuevos    (≥25 abr)  : {n_nuevo:>6}")
        if n_nuevo:
            print(f"    ✅ Created By (login Bubble) : {n_login:>6}  ({n_login/n_nuevo*100:.1f}%)")
            print(f"    ⚠️  Hash nombre (sin login)   : {n_hash_nuevo:>6}  ({n_hash_nuevo/n_nuevo*100:.1f}%)")
            if n_hash_nuevo > 0:
                print("    → Revisar: estos encuestadores no tienen Created By en sus registros.")
                sin_login = df_nuevo[~df_nuevo["encuestador_id"].apply(_es_created_by)]
                print("      Nombres afectados:")
                for nombre in sin_login["encuestador_nombre"].unique():
                    print(f"        · {nombre}")
    else:
        print("  Sin registros para analizar.")

    bc.st = _orig
    print("\n✅ Prueba completada.")