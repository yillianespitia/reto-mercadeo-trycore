import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

def cargar_historial(ruta_csv: str) -> list:
    """Lee el CSV histórico, elimina IDs duplicados y normaliza los números."""
    vistos = set()
    registros_limpios = []
    
    with open(ruta_csv, mode="r", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        for fila in lector:
            pid = fila["id_publicacion"].strip()
            if pid in vistos:
                continue  # Ignora duplicados (ej. P012, P031, P053)
            vistos.add(pid)
            
            # Convertir coma decimal a punto flotante
            tasa_str = fila.get("tasa_interaccion", "").replace(",", ".").strip()
            tasa = float(tasa_str) if tasa_str else 0.0
            
            cifra_raw = fila.get("tiene_cifra", "").strip().lower()
            tiene_cifra = cifra_raw in ["1", "sí", "si"]
            
            registros_limpios.append({
                "id": pid,
                "formato": fila["formato"].strip(),
                "hora": fila["hora"].strip(),
                "tiene_cifra": tiene_cifra,
                "tasa": tasa
            })
    return registros_limpios

def calcular_puntaje(pieza: dict, historial: list) -> int:
    """
    Calcula un puntaje de 0 a 100 apoyado en la tasa de interacción histórica del formato.
    """
    tasas_formato = [r["tasa"] for r in historial if r["formato"] == pieza["formato"] and r["tasa"] > 0]
    promedio_tasa = sum(tasas_formato) / len(tasas_formato) if tasas_formato else 0.035
    
    # En el historial la tasa máxima ronda 0.065 (6.5%). Escalamos sobre 0.065 para llegar a base 85.
    puntaje_base = min(85, (promedio_tasa / 0.065) * 85)
    
    # Bonos basados en comportamiento del historial
    bono_cifra = 10 if pieza.get("tiene_cifra") else 0
    bono_hora = 5 if pieza.get("hora") == "08:30" else 0
    
    return min(100, round(puntaje_base + bono_cifra + bono_hora))

def programar_calendario(piezas: list, ruta_ventana: str, ruta_ocupado: str, config: dict, historial: list) -> list:
    """Ubica las piezas en la ventana respetando festivos, capacidad y separación de 48h."""
    with open(ruta_ventana, "r", encoding="utf-8") as f:
        ventana = json.load(f)
        
    reglas_cal = config["calendario"]
    festivos = {f["fecha"] for f in reglas_cal["festivos"]}
    franjas = reglas_cal["franjas_de_publicacion"]
    max_dia = reglas_cal["capacidad_max_por_dia"]
    max_semana = reglas_cal["capacidad_max_por_semana"]
    sep_horas = reglas_cal["separacion_minima_mismo_tema_horas"]

    # Cargar lo que ya está agendado
    agenda = []
    with open(ruta_ocupado, mode="r", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            dt = datetime.strptime(f"{fila['fecha']} {fila['hora']}", "%Y-%m-%d %H:%M")
            agenda.append({
                "fecha": fila["fecha"],
                "hora": fila["hora"],
                "dt": dt,
                "canal": fila["canal"],
                "formato": fila["formato"],
                "tema": fila["tema"],
                "titulo": fila["titulo"],
                "estado": "Ya agendada (Ocupado)",
                "puntaje": "-",
                "alertas": []
            })

    fecha_actual = datetime.strptime(ventana["inicio"], "%Y-%m-%d")
    fecha_fin = datetime.strptime(ventana["fin"], "%Y-%m-%d")
    
    # Generar todos los slots  válidos (fechas disponibles) / (lunes a viernes, no festivos)
    slots_disponibles = []
    while fecha_actual <= fecha_fin:
        fecha_str = fecha_actual.strftime("%Y-%m-%d")
        # weekday(): 0=Lunes ... 4=Viernes
        if fecha_actual.weekday() < 5 and fecha_str not in festivos:
            for hora in franjas:
                slots_disponibles.append((fecha_str, hora, datetime.strptime(f"{fecha_str} {hora}", "%Y-%m-%d %H:%M")))
        fecha_actual += timedelta(days=1)

    for pieza in piezas:
        ubicada = False
        for fecha_str, hora, dt_slot in slots_disponibles:
            # 1. Verificar que la franja exacta no esté ocupada
            if any(a["fecha"] == fecha_str and a["hora"] == hora for a in agenda):
                continue
            # 2. Verificar capacidad por día (máx 2)
            if sum(1 for a in agenda if a["fecha"] == fecha_str) >= max_dia:
                continue
            # 3. Verificar capacidad por semana ISO (máx 4)
            semana_slot = dt_slot.isocalendar()[1]
            if sum(1 for a in agenda if a["dt"].isocalendar()[1] == semana_slot) >= max_semana:
                continue
            # 4. Verificar separación mínima de 48h para el mismo tema
            choque_tema = any(
                a["tema"] == pieza["tema"] and abs((dt_slot - a["dt"]).total_seconds()) / 3600 < sep_horas
                for a in agenda
            )
            if choque_tema:
                continue
            
            # ¡Slot válido encontrado!
            pieza["fecha"] = fecha_str
            pieza["hora"] = hora
            pieza["dt"] = dt_slot
            pieza["puntaje"] = calcular_puntaje(pieza, historial)
            agenda.append(pieza)
            ubicada = True
            break
            
        if not ubicada:
            pieza["fecha"] = "Sin cupo"
            pieza["hora"] = "-"
            pieza["dt"] = datetime.max
            pieza["puntaje"] = calcular_puntaje(pieza, historial)
            pieza["estado"] = "CONFLICTO: No cupo en ventana"
            agenda.append(pieza)

    return sorted(agenda, key=lambda x: (x["fecha"], x["hora"]))

def generar_html(agenda: list, diagnostico: dict, ruta_salida: str):
    """Genera la vista web semanal propia con colores por formato y alertas."""
    colores = {
        "post_linkedin": "#dbeafe",      # Azul claro
        "carrusel_linkedin": "#fef3c7",  # Amarillo claro
        "newsletter": "#dcfce7",         # Verde claro
        "infografia": "#f3e8ff"          # Morado claro
    }
    
    filas_html = ""
    for item in agenda:
        bg = colores.get(item["formato"], "#f3f4f6")
        if "CONFLICTO" in item["estado"]:
            bg = "#fee2e2"  # Rojo claro para conflictos
        alertas_txt = "<br>".join(item.get("alertas", [])) or "Sin alertas"
        
        filas_html += f"""
        <tr style="background-color: {bg};">
            <td><strong>{item['fecha']}</strong><br>{item['hora']}</td>
            <td><span class="badge">{item['formato']}</span></td>
            <td>{item['tema']}</td>
            <td>{item['titulo']}</td>
            <td style="text-align:center;"><strong>{item['puntaje']} / 100</strong></td>
            <td>{item['estado']}</td>
            <td style="font-size: 0.85em; color: #991b1b;">{alertas_txt}</td>
        </tr>
        """

    alertas_diag = "".join(f"<li>{a}</li>" for a in diagnostico["alertas"]) or "<li>Todo en orden</li>"

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Calendario de Contenidos - Trycore</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f9fafb; color: #111827; }}
        .card {{ background: white; padding: 15px 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; background: white; }}
        th, td {{ border: 1px solid #d1d5db; padding: 10px; text-align: left; }}
        th {{ background: #1f2937; color: white; }}
        .badge {{ padding: 4px 8px; border-radius: 4px; background: rgba(0,0,0,0.08); font-weight: bold; }}
    </style>
</head>
<body>
    <h1>📅 Tablero Táctico de Contenidos (Ventana: 30 Nov - 11 Dic 2026)</h1>
    <div class="card">
        <h3>🔍 Diagnóstico de Pieza Madre: {diagnostico['titulo_pieza']}</h3>
        <p><strong>Fuente:</strong> {diagnostico['fuente_usada']} | <strong>Indicadores:</strong> {diagnostico['indicadores_medibles']}</p>
        <ul>{alertas_diag}</ul>
    </div>
    <table>
        <thead>
            <tr>
                <th>Fecha y Hora</th>
                <th>Formato</th>
                <th>Tema</th>
                <th>Título / Gancho</th>
                <th>Puntaje Éxito</th>
                <th>Estado</th>
                <th>Alertas de Auditoría</th>
            </tr>
        </thead>
        <tbody>
            {filas_html}
        </tbody>
    </table>
</body>
</html>"""
    
    Path(ruta_salida).parent.mkdir(parents=True, exist_ok=True)
    with open(ruta_salida, "w", encoding="utf-8") as f:
        f.write(html)