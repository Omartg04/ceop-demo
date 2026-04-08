"""
Generador de datos sintéticos – CEOP Iguala, Guerrero
Ejecutar una sola vez: python data/generate_data.py
"""
import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

SECCIONES = [
    1480, 1481, 1482, 1483, 1484, 1485, 1486, 1487, 1488, 1489,
    1490, 1491, 1492, 1493, 1494, 1495, 1496, 1497, 1498, 1499,
    1500, 1501, 1502, 1503, 1504, 1505, 1506, 1507, 1508, 1509,
    1510, 1511, 1512, 1513, 1514, 1515, 1516, 1517, 1518, 1519,
    1520, 1521, 1522, 1523, 1524, 1525, 1526, 1527, 1528, 1529,
    1530, 1531, 1532, 1533, 1534, 1535, 1536, 1537, 1538, 1540,
    1541, 1542, 1543, 1544, 1545, 1546, 1547, 1548, 1549, 1550,
    1551, 1552, 1553, 1554, 1555, 1556, 1557, 1558, 1559, 1560,
    1561, 1562, 1563, 1564, 2830, 2831, 2832,
]

NOMBRES_H = [
    "Carlos Mendoza", "Juan Ramírez", "Pedro Sánchez", "Luis Torres",
    "Miguel Ángel Flores", "Roberto Guzmán", "Héctor Morales", "Arturo Vega",
    "Fernando Cruz", "Eduardo Reyes", "Alejandro Díaz", "Jorge Castillo",
    "Raúl Herrera", "Manuel Ortega", "Víctor Ramos", "Antonio Lara",
    "Sergio Jiménez", "Ricardo Peña", "José Salinas", "Pablo Guerrero",
    "Óscar Núñez", "Rubén Medina", "Enrique Delgado", "Alfredo Aguilar",
    "Marco Vargas", "Iván Rojas", "Gerardo Fuentes", "Daniel Peralta",
    "Ernesto Luna", "Adrián Campos",
]
NOMBRES_M = [
    "María López", "Ana García", "Laura Torres", "Claudia Ríos",
    "Sandra Moreno", "Patricia Alvarado", "Verónica Espinoza", "Rosa Núñez",
    "Isabel Zamora", "Gabriela Soto", "Alejandra Ruiz", "Mónica Cervantes",
    "Silvia Pacheco", "Lorena Ibarra", "Carmen Mendez", "Yolanda Vargas",
    "Beatriz Guerrero", "Norma Estrada", "Lucía Pedroza", "Teresa Montes",
    "Irma Sandoval", "Graciela Domínguez", "Leticia Vásquez", "Blanca Tapia",
    "Alma Figueroa", "Fabiola Olvera", "Marcela Gutiérrez", "Rocío Bautista",
    "Elena Cardenas", "Diana Maldonado",
]

ENCUESTADORES = [{"id": f"E{i:02d}", "nombre": n}
                 for i, n in enumerate(NOMBRES_H + NOMBRES_M, 1)]

FECHAS = pd.date_range("2025-06-02", periods=10, freq="B")

OPCIONES = {
    "satisfaccion_amlo":    ["Muy satisfecho", "Satisfecho", "Regular", "Insatisfecho"],
    "satisfaccion_cs":      ["Muy satisfecho", "Satisfecho", "Regular", "Insatisfecho"],
    "programas_bienestar":  ["Mucho", "Algo", "Poco", "Nada"],
    "conoce_ivan":          ["Sí", "No"],
    "opinion_ivan":         ["Muy buena", "Buena", "Regular", "Mala", "No sabe / No contesta"],
    "cercania_ivan":        ["Muy cercano", "Algo cercano", "Poco cercano", "No sabe / No contesta"],
    "representa_4t":        ["Sí, totalmente", "En parte", "No", "No sabe / No contesta"],
    "intencion_voto":       ["Sí, con seguridad", "Probablemente sí", "Probablemente no",
                             "No", "No sabe / No contesta"],
    "descripcion_ivan":     ["Es una persona de trabajo y territorio",
                             "Es un operador del gobierno federal",
                             "No lo conozco bien", "No tengo una opinión clara"],
    "prioridad_gobernador": ["Seguridad", "Empleo / economía", "Programas sociales",
                             "Educación", "Salud", "Infraestructura"],
    "sexo":                 ["Hombre", "Mujer", "Otro"],
    "nivel_educativo":      ["Primaria", "Secundaria", "Preparatoria", "Universidad", "Posgrado"],
    "recibe_bienestar":     ["Sí", "No"],
    "sabia_designacion":    ["Sí, lo sabía", "No lo sabía, pero me parece bien",
                             "No lo sabía y no me interesa", "No sabe / No contesta"],
}

PESOS = {
    "satisfaccion_amlo":    [0.35, 0.35, 0.20, 0.10],
    "satisfaccion_cs":      [0.30, 0.38, 0.22, 0.10],
    "programas_bienestar":  [0.40, 0.35, 0.18, 0.07],
    "conoce_ivan":          [0.45, 0.55],
    "opinion_ivan":         [0.20, 0.35, 0.28, 0.08, 0.09],
    "cercania_ivan":        [0.22, 0.35, 0.25, 0.18],
    "representa_4t":        [0.30, 0.35, 0.15, 0.20],
    "intencion_voto":       [0.22, 0.28, 0.18, 0.17, 0.15],
    "descripcion_ivan":     [0.38, 0.22, 0.28, 0.12],
    "prioridad_gobernador": [0.32, 0.25, 0.18, 0.12, 0.09, 0.04],
    "sexo":                 [0.50, 0.48, 0.02],
    "nivel_educativo":      [0.15, 0.30, 0.30, 0.20, 0.05],
    "recibe_bienestar":     [0.62, 0.38],
    "sabia_designacion":    [0.30, 0.35, 0.20, 0.15],
}


def pick(campo):
    return random.choices(OPCIONES[campo], weights=PESOS[campo], k=1)[0]


def duracion_minutos():
    return max(5, min(35, round(np.random.normal(13, 3), 1)))


registros = []
folio = 1
enc_secciones = {enc["id"]: random.sample(SECCIONES, k=random.randint(2, 5))
                 for enc in ENCUESTADORES}

for fecha in FECHAS:
    encuestadores_dia = random.sample(ENCUESTADORES, k=random.randint(35, 50))
    for enc in encuestadores_dia:
        n = random.randint(6, 18)
        seccion_base = random.choice(enc_secciones[enc["id"]])
        for _ in range(n):
            sec = seccion_base if random.random() > 0.2 else random.choice(SECCIONES)
            conoce = pick("conoce_ivan")
            hora_inicio = (datetime.combine(fecha.date(), datetime.min.time())
                           + timedelta(hours=9) + timedelta(minutes=random.randint(0, 480)))
            duracion = duracion_minutos()
            hora_fin = hora_inicio + timedelta(minutes=duracion)
            row = {
                "folio":               f"IGU-{folio:04d}",
                "fecha":               fecha.date(),
                "hora_inicio":         hora_inicio.strftime("%H:%M"),
                "hora_fin":            hora_fin.strftime("%H:%M"),
                "duracion_min":        duracion,
                "encuestador_id":      enc["id"],
                "encuestador_nombre":  enc["nombre"],
                "seccion":             sec,
                "satisfaccion_amlo":   pick("satisfaccion_amlo"),
                "satisfaccion_cs":     pick("satisfaccion_cs"),
                "programas_bienestar": pick("programas_bienestar"),
                "sabia_designacion":   pick("sabia_designacion"),
                "conoce_ivan":         conoce,
                "opinion_ivan":        pick("opinion_ivan") if conoce == "Sí" else "No aplica",
                "cercania_ivan":       pick("cercania_ivan"),
                "representa_4t":       pick("representa_4t"),
                "intencion_voto":      pick("intencion_voto"),
                "descripcion_ivan":    pick("descripcion_ivan"),
                "prioridad_gobernador":pick("prioridad_gobernador"),
                "edad":                random.randint(18, 75),
                "sexo":                pick("sexo"),
                "nivel_educativo":     pick("nivel_educativo"),
                "recibe_bienestar":    pick("recibe_bienestar"),
            }
            registros.append(row)
            folio += 1

df = pd.DataFrame(registros)
df.to_csv("data/encuestas.csv", index=False)
print(f"✅ Generados {len(df):,} registros")
print(f"   Encuestadores: {df['encuestador_id'].nunique()}")
print(f"   Secciones cubiertas: {df['seccion'].nunique()} de {len(SECCIONES)}")
print(f"   Fechas: {df['fecha'].min()} → {df['fecha'].max()}")
