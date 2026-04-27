"""
CEOP · config.py
Parámetros centralizados para el visualizador estatal de Guerrero.
Editar aquí — no tocar app.py para cambiar umbrales o mapeos.
"""

# ── API Bubble ─────────────────────────────────────────────────────────────────
BUBBLE_BASE_URL = "https://encuestaopguerrero.bubbleapps.io/api/1.1"
BUBBLE_ENDPOINT = f"{BUBBLE_BASE_URL}/obj/Encuesta"
BUBBLE_PAGE_SIZE = 100
CACHE_TTL_SEC    = 300           # 5 minutos

# ── Parámetros operativos ──────────────────────────────────────────────────────
META_DIA         = 20
UMBRAL_AMARILLO  = 15
DUR_MIN_MIN      = 5
DUR_MAX_MIN      = 20
AUTO_REFRESH_SEC = 300
META_POR_SECCION = 20            # confirmado por stakeholder

# ── Identidad visual ───────────────────────────────────────────────────────────
VERDE    = "#2E7D5E"
VERDE_L  = "#52B788"
AZUL     = "#1A3A5C"
AZUL_L   = "#2C6E9E"
NARANJA  = "#E07B39"
ROJO     = "#C0392B"
AMARILLO = "#F5A623"
GRIS_BG  = "#F2F4F7"

# ── Mapeo campos Bubble → app ──────────────────────────────────────────────────
FIELD_MAP = {
    "_id":                        "folio",
    "Created Date":               "fecha_inicio",
    "Modified Date":              "fecha_fin",
    "estatus_encuesta":           "estatus",
    "nombre_encuestador":         "encuestador_nombre",
    "municipio":                  "municipio",
    "seccion_electoral":          "seccion",
    "coordinador":                "coordinador",      # pendiente activar en Bubble
    "p1":                         "p1_amlo",
    "p2":                         "p2_sheinbaum",
    "p3":                         "p3_bienestar",
    "p4a":                        "p4a_delegado_amlo",
    "p4b":                        "p4b_delegado_csp",
    "p5":                         "p5_conoce",
    "p6":                         "p6_opinion",
    "p7":                         "p7_cercania",
    "p8":                         "p8_valores_4t",
    "p9":                         "p9_voto",
    "p10":                        "p10_frase",
    "p11_1":                      "p11_programas_sociales",
    "p11_2":                      "p11_empleo",
    "p11_3":                      "p11_seguridad",
    "p11_4":                      "p11_educacion",
    "p11_5":                      "p11_salud",
    "p11_6":                      "p11_infraestructura",
    "p11_7":                      "p11_otra",
    "p11_7_otra":                 "p11_otra_texto",
    "edad":                       "edad",
    "sexo":                       "sexo",
    "nivel_educativo":            "nivel_educativo",
    "recibe_programas_bienestar": "recibe_bienestar",
}

CAMPOS_EXCLUIR = {
    "nombre_encuestado", "celular_encuestado", "email_encuestado",
    "Created By", "prioridades",
}

# ── Opciones de respuesta por pregunta (para ordenar gráficas) ─────────────────
OPCIONES = {
    "p1_amlo":       ["Muy satisfecho", "Satisfecho", "Regular", "Insatisfecho"],
    "p2_sheinbaum":  ["Muy satisfecho", "Satisfecho", "Regular", "Insatisfecho"],
    "p3_bienestar":  ["Mucho", "Algo", "Poco", "Nada"],
    "p4a_delegado_amlo": [
        "Sí, lo sabía",
        "No lo sabía, pero me parece bien",
        "No lo sabía y no me interesa",
        "No sabe / No contesta",
    ],
    "p4b_delegado_csp": [
        "Sí, lo sabía",
        "No lo sabía, pero me parece bien",
        "No lo sabía y no me interesa",
        "No sabe / No contesta",
    ],
    "p5_conoce":     ["Sí", "No"],
    "p6_opinion":    ["Muy buena", "Buena", "Regular", "Mala", "No sabe / No contesta"],
    "p7_cercania":   ["Muy cercano", "Algo cercano", "Poco cercano", "No sabe / No contesta"],
    "p8_valores_4t": ["Sí, totalmente", "En parte", "No", "No sabe / No contesta"],
    "p9_voto": [
        "Sí, con seguridad", "Probablemente sí",
        "Probablemente no", "No", "No sabe / No contesta",
    ],
    "p10_frase": [
        "Es una persona de trabajo y territorio",
        "Es un operador del gobierno federal",
        "No lo conozco bien",
        "No tengo una opinión clara",
        "Otro",
    ],
    "p11_labels": {
        "p11_programas_sociales": "Programas sociales",
        "p11_empleo":             "Empleo / economía",
        "p11_seguridad":          "Seguridad",
        "p11_educacion":          "Educación",
        "p11_salud":              "Salud",
        "p11_infraestructura":    "Infraestructura",
        "p11_otra":               "Otra",
    },
}

# ── Jerarquía territorial ──────────────────────────────────────────────────────
MUNICIPIOS = {
    "TELOLOAPAN": {
        "clave_ini": 59,
        "geojson":   "secciones_teloloapan.geojson",
        "secciones": 76,
        "distritos": [],
        "centro":    [18.354, -99.876],
        "zoom":      12,
    },
    "COYUCA DE BENITEZ": {
        "clave_ini": 21,
        "geojson":   "secciones_coyuca.geojson",
        "secciones": 59,
        "distritos": [],
        "centro":    [17.017, -100.082],
        "zoom":      12,
    },
    "ACAPULCO DE JUAREZ": {
        "clave_ini": 1,
        "geojson":   "secciones_acapulco.geojson",
        "secciones": 398,
        "distritos": [3, 4, 5, 6, 7, 8, 9],
        "centro":    [16.863, -99.882],
        "zoom":      11,
    },
    "CHILPANCINGO DE LOS BRAVO": {
        "clave_ini": 29,
        "geojson":   "secciones_chilpancingo.geojson",
        "secciones": 123,
        "distritos": [1, 2],
        "centro":    [17.551, -99.500],
        "zoom":      12,
    },
    "IGUALA DE LA INDEPENDENCIA": {
        "clave_ini": 36,
        "geojson":   "secciones_iguala.geojson",
        "secciones": 87,
        "distritos": [22, 23],
        "centro":    [18.344, -99.539],
        "zoom":      12,
    },
    "ZIHUATANEJO DE AZUETA": {
        "clave_ini": 39,
        "geojson":   "secciones_zihuatanejo.geojson",
        "secciones": 120,
        "distritos": [11, 12],
        "centro":    [17.638, -101.554],
        "zoom":      12,
    },
    "PETATLAN": {
        "clave_ini": 49,
        "geojson":   "secciones_petatlan.geojson",
        "secciones": 81,
        "distritos": [11],
        "centro":    [17.538, -101.270],
        "zoom":      12,
    },
    "OMETEPEC": {
        "clave_ini": 47,
        "geojson":   "secciones_ometepec.geojson",
        "secciones": 41,
        "distritos": [16],
        "centro":    [16.690, -98.413],
        "zoom":      12,
    },
    "SAN MARCOS": {
        "clave_ini": 53,
        "geojson":   "secciones_san_marcos.geojson",
        "secciones": 25,
        "distritos": [28],
        "centro":    [16.797, -99.385],
        "zoom":      13,
    },
    # Municipios adicionales — GeoJSONs y claves INE pendientes
    "CHILAPA DE ALVAREZ": {
        "clave_ini": 28,
        "geojson":   "secciones_chilapa.geojson",
        "secciones": 85,
        "distritos": [],
        "centro":    [17.501, -99.075],
        "zoom":      12,
    },
    "TLAPA DE COMONFORT": {
        "clave_ini": 67,
        "geojson":   "secciones_tlapa.geojson",
        "secciones": 36,
        "distritos": [],
        "centro":    [17.529, -98.618],
        "zoom":      12,
    },
    "AYUTLA DE LOS LIBRES": {
        "clave_ini": 57,
        "geojson":   "secciones_ayutla.geojson",
        "secciones": 39,
        "distritos": [],
        "centro":    [16.973, -99.303],
        "zoom":      12,
    },
    "TEPECOACUILCO DE TRUJANO": {
        "clave_ini": 60,
        "geojson":   "secciones_tepecoacuilco.geojson",
        "secciones": 31,
        "distritos": [],
        "centro":    [18.133, -99.482],
        "zoom":      12,
    },
    "TAXCO DE ALARCON": {
        "clave_ini": 56,
        "geojson":   "secciones_taxco.geojson",
        "secciones": 89,
        "distritos": [],
        "centro":    [18.504, -99.598],
        "zoom":      12,
    },
    "HUITZUCO DE LOS FIGUEROA": {
        "clave_ini": 35,
        "geojson":   "secciones_huitzuco.geojson",
        "secciones": 36,
        "distritos": [],
        "centro":    [18.180, -99.268],
        "zoom":      12,
    },
}

ESTADO_CENTRO = [17.5, -99.8]
ESTADO_ZOOM   = 8

# ── Semanas de operativo ───────────────────────────────────────────────────────
# Semana 1 = 18–19 abril (arranque de fin de semana).
# A partir del lunes 21 abril: semanas ISO lunes–domingo.
# Levantamientos eventuales entre semana caen en la semana calendario que les
# corresponde sin necesidad de configuración adicional.

import pandas as _pd

def semana_operativo(fecha) -> str:
    """
    Asigna una etiqueta de semana de operativo a una fecha.
    Semana operativa: sábado → viernes.
    S1 = 18–24 abril · S2 = 25 abril–1 mayo · S3 en adelante automático.
    Retorna 'S1', 'S2', 'S3', ...
    """
    import datetime as _dt
    ANCLA = _dt.date(2026, 4, 18)  # sábado de inicio del operativo

    if hasattr(fecha, "date"):
        fecha = fecha.date()

    delta = (fecha - ANCLA).days
    semana_num = (delta // 7) + 1
    return f"S{max(semana_num, 1)}"

# ── Coordinadores por municipio ────────────────────────────────────────────────
# Confirmado por Ilich · 17 abril 2026
# ⚠️  Acapulco tiene múltiples coordinadores — usar campo `coordinador` de Bubble
#     como fuente de verdad, no este diccionario.
COORDINADORES = {
    "ACAPULCO DE JUAREZ":         ["Ilich Lozano", "Alma Jessica Perez Vargas"],
    "CHILPANCINGO DE LOS BRAVO":  ["Samir Ávila"],
    "IGUALA DE LA INDEPENDENCIA": ["Elizabeth Figueroa Helguera"],
    "ZIHUATANEJO DE AZUETA":      ["Pilar Pérez Gutiérrez"],
    "OMETEPEC":                   ["Xochitl Jiménez Pita"],
    "PETATLAN":                   ["Sin asignar"],
    "SAN MARCOS":                 ["Sin asignar"],
    "CHILAPA DE ALVAREZ":         ["Sin asignar"],
    "TLAPA DE COMONFORT":         ["Sin asignar"],
    "AYUTLA DE LOS LIBRES":       ["Sin asignar"],
    "TEPECOACUILCO DE TRUJANO":   ["Serapio Navarro Rayo"],
    "TAXCO DE ALARCON":           ["Sin asignar"],
    "HUITZUCO DE LOS FIGUEROA":   ["Sin asignar"],
    "TELOLOAPAN":                 ["Serapio Navarro Rayo"],
    "COYUCA DE BENITEZ":          ["Jose Roberto Sanchez Rios"],
}

# Lista plana de todos los coordinadores (para el dropdown del sidebar)
TODOS_COORDINADORES = sorted(set(
    c for coords in COORDINADORES.values() for c in coords
    if c != "Sin asignar"
))

# Inverso: coordinador → municipios (best-effort, usar Bubble como fuente de verdad)
MUNICIPIOS_POR_COORDINADOR: dict[str, list[str]] = {}
for _muni, _coords in COORDINADORES.items():
    for _coord in _coords:
        MUNICIPIOS_POR_COORDINADOR.setdefault(_coord, []).append(_muni)

# ── Roles (estructura lista para streamlit-authenticator) ──────────────────────
ROLES = {
    # ── Coordinador estatal — acceso total + Tab 3 y Tab 4 ────────────────────
    "ilich": {
        "rol":        "estatal",
        "municipios": list(MUNICIPIOS.keys()),
    },
    # ── Coordinadores municipales — solo Tab 1 y Tab 2, municipio(s) asignado(s)
    # Rol "municipal": NO puede ver Tab 3 (Perfil) ni Tab 4 (Resultados)
    "belgica": {
        "rol":        "municipal",
        "municipios": ["ACAPULCO DE JUAREZ"],
    },
    "samir": {
        "rol":        "municipal",
        "municipios": ["CHILPANCINGO DE LOS BRAVO"],
    },
    "elizabeth": {
        "rol":        "municipal",
        "municipios": ["IGUALA DE LA INDEPENDENCIA"],
    },
    "pilar": {
        "rol":        "municipal",
        "municipios": ["ZIHUATANEJO DE AZUETA"],
    },
    "oscar": {
        "rol":        "municipal",
        "municipios": ["ZIHUATANEJO DE AZUETA"],
    },
    "xochitl": {
        "rol":        "municipal",
        "municipios": ["OMETEPEC", "SAN MARCOS", "AYUTLA DE LOS LIBRES"],
    },
    "serapio": {
        "rol":        "municipal",
        "municipios": ["TELOLOAPAN"],
    },
    "bresne": {
        "rol":        "municipal",
        "municipios": ["IGUALA DE LA INDEPENDENCIA"],
    },
    "roberto": {
        "rol":        "municipal",
        "municipios": ["ACAPULCO DE JUAREZ", "COYUCA DE BENITEZ"],
    },
}