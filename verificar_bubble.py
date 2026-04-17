cat > verificar_bubble.py << 'PYEOF'
import requests, json

BUBBLE_API_TOKEN = "3e40b6cbea8e733fe3e6ac89f1f796b5"
BUBBLE_BASE_URL  = "https://encuestaopguerrero.bubbleapps.io/version-test"

headers = {"Authorization": f"Bearer {BUBBLE_API_TOKEN}"}
url     = f"{BUBBLE_BASE_URL}/api/1.1/obj/encuesta?limit=1"

r    = requests.get(url, headers=headers)
data = r.json()
results = data.get("response", {}).get("results", [])

if not results:
    print("Sin resultados")
else:
    rec = results[0]
    print(f"Total campos: {len(rec)}\n")

    esperados = [
        "p11_1","p11_2","p11_3","p11_4","p11_5","p11_6","p11_7","p11_7_otra",
        "nombre_encuestado","celular_encuestado","email_encuestado",
        "nombre_encuestador","municipio","seccion_electoral",
        "p1","p2","p3","p4","p5","p6","p7","p8","p9","p10",
        "edad","sexo","nivel_educativo","recibe_programas_bienestar",
        "Created Date","Modified Date"
    ]

    print("=== VERIFICACION DICCIONARIO v1 ===")
    for campo in esperados:
        estado = "OK" if campo in rec else "FALTA"
        valor  = repr(rec.get(campo, ""))[:60]
        print(f"  {estado:<8} {campo:<30} {valor}")

    print("\n=== CAMPOS EXTRA EN API ===")
    extras = set(rec.keys()) - set(esperados)
    for c in sorted(extras):
        print(f"  EXTRA    {c:<30} {repr(rec.get(c, ''))[:60]}")

