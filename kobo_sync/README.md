# kobo_sync — Sincronización KoboToolbox → Bubble

## ¿Qué hace este script?
Descarga las respuestas de tu formulario en KoboToolbox y las sube
automáticamente a tu base de datos en Bubble vía API REST.

---

## Pasos para usarlo

### 1. Instala la dependencia
```bash
pip install requests
```

### 2. Rellena las credenciales en `kobo_sync.py`

Abre el archivo y busca la sección `# 1. CREDENCIALES`:

| Variable | Dónde encontrarla |
|---|---|
| `KOBO_API_KEY` | KoboToolbox → Cuenta → Seguridad → API Key |
| `KOBO_FORM_ID` | URL del formulario en Kobo, el código alfanumérico |
| `BUBBLE_API_KEY` | Bubble → Settings → API → Private key |
| `BUBBLE_ENDPOINT` | Bubble → Settings → API → Data API → tu tipo de dato |

**Ejemplo de endpoint Bubble:**
```
https://ceop.bubbleapps.io/api/1.1/obj/respuesta
```

### 3. Ejecuta el script
```bash
cd ceop_demo/kobo_sync
python kobo_sync.py
```

---

## ¿Cómo encontrar el FORM_ID de Kobo?
En KoboToolbox, abre tu formulario. La URL se verá así:
```
https://kf.kobotoolbox.org/#/forms/aXmK3pQ7rZ/summary
```
El `FORM_ID` es la parte alfanumérica: `aXmK3pQ7rZ`

---

## Salida esperada
```
==================================================
  CEOP — Sincronización Kobo → Bubble
==================================================

📡 Conectando a KoboToolbox...
✅ Se encontraron 2 respuestas en Kobo.
  → Subiendo registro 1/2 (kobo_id: 123456)...
  → Subiendo registro 2/2 (kobo_id: 123457)...

✅ Sincronización completa: 2 exitosos, 0 fallidos.
   Hora: 2025-04-16 10:32:01
```
