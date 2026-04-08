# CEOP · Visualizador de Levantamiento — Iguala, Guerrero

Demo operativo del sistema de monitoreo de brigadas para el municipio de Iguala.

## Estructura del proyecto

```
ceop_demo/
├── app.py                  # Aplicación principal Streamlit
├── requirements.txt        # Dependencias
├── README.md
└── data/
    ├── generate_data.py    # Generador de datos sintéticos (ejecutar una vez)
    └── encuestas.csv       # Datos generados (se crea al ejecutar generate_data.py)
```

## Instalación

```bash
# 1. Instalar dependencias (si aún no están en tu ambiente)
pip install -r requirements.txt

# 2. Generar datos sintéticos (solo la primera vez)
cd ceop_demo
python data/generate_data.py

# 3. Lanzar la aplicación
streamlit run app.py
```

La app abre en http://localhost:8501

## Funcionalidades del demo

### 📈 Desempeño de Brigadas
- Total de encuestas por encuestador (con color por productividad diaria)
- Box plot de duración de entrevistas por encuestador
- Línea de avance diario por encuestador
- Tabla resumen de KPIs: total, días activos, promedio diario, duración (promedio, mínima, máxima)

### 🗺️ Mapa de Puntos
- Mapa interactivo Folium centrado en Iguala con puntos georeferenciados por colonia
- Color por encuestador; popup con folio, fecha, duración
- Gráfica de barras de concentración por colonia/zona

### 👤 Perfil de Entrevistados
- Distribución por sexo (pie chart)
- Nivel educativo
- Beneficiarios de programas Bienestar
- Pirámide de edades (Hombres vs Mujeres)

### 📊 Resultados del Instrumento
- Sección A: Satisfacción con AMLO, Sheinbaum, Programas Bienestar
- Sección B: Conocimiento y opinión de Iván Hernández (cercanía, representatividad 4T)
- Sección C: Intención de voto, descripción como candidato, prioridades para el gobernador
- Botón de descarga CSV con datos filtrados

### ⚙️ Filtros en sidebar
- Rango de fechas
- Encuestador específico
- Colonia / zona

## Datos sintéticos

El generador crea ~540 registros con distribuciones de respuesta realistas para el
contexto político de Guerrero (perfil pro-4T con variación). Las coordenadas están
jittered dentro de 10 colonias representativas de Iguala.

## Próximos pasos (producción)
- Conectar a base de datos real (PostgreSQL / Google Sheets vía gspread)
- Agregar autenticación con `streamlit-authenticator`
- Incorporar capa shapefile de AGEBs de INEGI para heatmap por AGEB
- Panel de alertas por encuestador (encuestas demasiado cortas, outliers GPS)
- Integración con formulario digital (KoboToolbox / ODK) vía API