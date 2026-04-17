"""
kobo_sync.py
Sincronización de respuestas KoboToolbox → Bubble
Proyecto: CEOP - CAPI Offline Guerrero
"""

import requests
from datetime import datetime

# ─────────────────────────────────────────────
# 1. CREDENCIALES
# ─────────────────────────────────────────────

KOBO_API_KEY   = "215a1f2451dbd773a4761a6cdb06a02c32e81250"
KOBO_FORM_ID   = "agrbE6tTjpnRkMiiEwsXzJ"

BUBBLE_API_KEY  = "3e40b6cbea8e733fe3e6ac89f1f796b5"
BUBBLE_ENDPOINT = "https://encuestaopguerrero.bubbleapps.io/version-test/api/1.1/obj/Encuesta"

# ─────────────────────────────────────────────
# 2. OBTENER RESPUESTAS DE KOBO
# ─────────────────────────────────────────────

def obtener_respuestas_kobo():
    url = f"https://kf.kobotoolbox.org/api/v2/assets/{KOBO_FORM_ID}/data/?format=json"
    headers = {"Authorization": f"Token {KOBO_API_KEY}"}

    print("📡 Conectando a KoboToolbox...")
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"❌ Error al conectar con Kobo: {response.status_code}")
        print(response.text)
        return []

    datos = response.json()
    respuestas = datos.get("results", [])
    print(f"✅ Se encontraron {len(respuestas)} respuestas en Kobo.")
    return respuestas

# ─────────────────────────────────────────────
# 3. MAPEAR CAMPOS KOBO → BUBBLE
# ─────────────────────────────────────────────

def mapear_respuesta(r):
    return {
        "nombre_encuestador":         r.get("nombre_encuestador", ""),
        "municipio":                  r.get("municipio", ""),
        "seccion_electoral":          r.get("seccion_electoral", ""),
        "p1":                         r.get("p1", ""),
        "p2":                         r.get("p2", ""),
        "p3":                         r.get("p3", ""),
        "p4":                         r.get("p4", ""),
        "p5":                         r.get("p5", ""),
        "p6":                         r.get("p6", ""),
        "p7":                         r.get("p7", ""),
        "p8":                         r.get("p8", ""),
        "p9":                         r.get("p9", ""),
        "p10":                        r.get("p10", ""),
        "p11_1":                      r.get("p11_1", ""),
        "p11_2":                      r.get("p11_2", ""),
        "p11_3":                      r.get("p11_3", ""),
        "p11_4":                      r.get("p11_4", ""),
        "p11_5":                      r.get("p11_5", ""),
        "p11_6":                      r.get("p11_6", ""),
        "p11_7":                      r.get("p11_7", ""),
        "p11_7_otra":                 r.get("p11_7_otra", ""),
        "edad":                       r.get("edad", ""),
        "sexo":                       r.get("sexo", ""),
        "nivel_educativo":            r.get("nivel_educativo", ""),
        "recibe_programas_bienestar": r.get("recibe_programas_bienestar", ""),
        "nombre_encuestado":          r.get("nombre_encuestado", ""),
        "celular_encuestado":         r.get("celular_encuestado", ""),
        "email_encuestado":           r.get("email_encuestado", ""),
    }

# ─────────────────────────────────────────────
# 4. SUBIR UNA RESPUESTA A BUBBLE
# ─────────────────────────────────────────────

def subir_a_bubble(registro):
    headers = {
        "Authorization": f"Bearer {BUBBLE_API_KEY}",
        "Content-Type": "application/json"
    }

    # Eliminar campos vacíos para evitar errores en Bubble
    registro_limpio = {k: v for k, v in registro.items() if v != ""}

    response = requests.post(BUBBLE_ENDPOINT, headers=headers, json=registro_limpio)

    if response.status_code in (200, 201):
        return True
    else:
        print(f"  ⚠️  Error al subir registro: {response.status_code} — {response.text}")
        return False

# ─────────────────────────────────────────────
# 5. FLUJO PRINCIPAL
# ─────────────────────────────────────────────

def sincronizar():
    print("\n" + "="*50)
    print("  CEOP — Sincronización Kobo → Bubble")
    print("="*50 + "\n")

    respuestas = obtener_respuestas_kobo()

    if not respuestas:
        print("⚠️  No hay respuestas para sincronizar.")
        return

    exitosos = 0
    fallidos  = 0

    for i, r in enumerate(respuestas, 1):
        registro = mapear_respuesta(r)
        print(f"  → Subiendo registro {i}/{len(respuestas)}...")
        if subir_a_bubble(registro):
            exitosos += 1
        else:
            fallidos += 1

    print(f"\n✅ Sincronización completa: {exitosos} exitosos, {fallidos} fallidos.")
    print(f"   Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

if __name__ == "__main__":
    sincronizar()