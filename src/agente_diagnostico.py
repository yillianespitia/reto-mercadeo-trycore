import json
import re
import requests
from bs4 import BeautifulSoup
from pathlib import Path

def extraer_contenido(url_archivo: str, ruta_respaldo: str) -> dict:
    """
    Intenta descargar el contenido desde la URL. 
    Si falla, activa el respaldo local y genera una alerta.
    """
    alertas = []
    fuente_usada = "URL en vivo"
    html_crudo = ""

    with open(url_archivo, "r", encoding="utf-8") as f:
        url = f.read().strip()

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        respuesta = requests.get(url, headers=headers, timeout=10)
        respuesta.raise_for_status()
        html_crudo = respuesta.text
    except Exception as e:
        fuente_usada = "Respaldo HTML local"
        alertas.append(f"ALERTA DE INGESTA: No se pudo descargar la URL ({url}). Motivo: {e}. Se cargó el archivo de respaldo.")
        with open(ruta_respaldo, "r", encoding="utf-8") as f:
            html_crudo = f.read()

    soup = BeautifulSoup(html_crudo, "html.parser")
    
    # Eliminar etiquetas que no aportan contenido editorial
    for etiqueta in soup(["script", "style", "nav", "footer", "header"]):
        etiqueta.decompose()

    titulo = soup.find("h1").get_text(strip=True) if soup.find("h1") else "Sin título principal"
    subtitulos = [h.get_text(strip=True) for h in soup.find_all(["h2", "h3"]) if h.get_text(strip=True)]
    parrafos = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 20]
    items_lista = [li.get_text(strip=True) for li in soup.find_all("li") if len(li.get_text(strip=True)) > 10]

    texto_completo = f"{titulo}\n" + "\n".join(subtitulos + parrafos + items_lista)

    return {
        "url_origen": url,
        "fuente_usada": fuente_usada,
        "titulo": titulo,
        "subtitulos": subtitulos,
        "parrafos": parrafos,
        "items_lista": items_lista,
        "texto_completo": texto_completo,
        "alertas_ingesta": alertas
    }

def diagnosticar_pieza(contenido: dict, config: dict) -> dict:
    """
    Evalúa la pieza madre contra config.json, calcula 4+ indicadores medibles
    y determina qué formatos son viables.
    """
    texto = contenido["texto_completo"]
    palabras = texto.split()
    total_palabras = len(palabras)
    
    # Indicador 2: Cifras y porcentajes encontrados
    cifras_encontradas = re.findall(r'\b\d+(?:[.,]\d+)?%?\b', texto)
    # Filtramos años comunes (2020-2030) para contar métricas reales
    metricas = [c for c in cifras_encontradas if not (c.isdigit() and 2000 <= int(c) <= 2030)]

    # Indicador 3: Productos vigentes mencionados
    productos_vigentes = config.get("productos_vigentes", [])
    productos_detectados = [p for p in productos_vigentes if re.search(rf'\b{re.escape(p)}\b', texto, re.IGNORECASE)]

    # Indicador 4: Términos prohibidos o confidenciales en la pieza madre
    alertas_reglas = list(contenido["alertas_ingesta"])
    for item in config.get("terminos_prohibidos", []):
        termino = item["termino"]
        if re.search(rf'\b{re.escape(termino)}\b', texto, re.IGNORECASE):
            alertas_reglas.append(f"Término prohibido detectado en fuente: '{termino}' ({item['motivo']})")

    for cliente in config.get("nombres_confidenciales", []):
        if re.search(rf'\b{re.escape(cliente)}\b', texto, re.IGNORECASE):
            alertas_reglas.append(f"Nombre confidencial detectado en fuente: '{cliente}'")

    if not productos_detectados:
        alertas_reglas.append("REVISIÓN: La pieza madre no menciona ningún producto vigente de Trycore.")
    
    if metricas:
        alertas_reglas.append(f"REVISIÓN DE FUENTES: Se detectaron {len(metricas)} cifras ({', '.join(metricas[:5])}...). Verificar fuente antes de publicar.")

    # Evaluar viabilidad de formatos según matriz_formatos
    formatos_viables = []
    formatos_descartados = []

    for fmt in config.get("matriz_formatos", []):
        fid = fmt["id"]
        if fid == "post_linkedin" and total_palabras >= 100:
            formatos_viables.append(fid)
        elif fid == "carrusel_linkedin" and (len(contenido["items_lista"]) >= 5 or len(contenido["subtitulos"]) >= 5):
            formatos_viables.append(fid)
        elif fid == "newsletter" and len(contenido["subtitulos"]) >= 3 and total_palabras >= 250:
            formatos_viables.append(fid)
        elif fid == "guion_video_corto" and len(contenido["subtitulos"]) >= 3:
            formatos_viables.append(fid)
        elif fid == "infografia" and (len(contenido["items_lista"]) >= 5 or len(metricas) >= 5):
            formatos_viables.append(fid)
        else:
            formatos_descartados.append({
                "formato": fid,
                "motivo": f"No cumple requisitos mínimos de estructura en pieza madre: {fmt['requiere_de_pieza_madre']}"
            })

    return {
        "titulo_pieza": contenido["titulo"],
        "fuente_usada": contenido["fuente_usada"],
        "indicadores_medibles": {
            "1_total_palabras": total_palabras,
            "2_cantidad_subtitulos": len(contenido["subtitulos"]),
            "3_elementos_lista": len(contenido["items_lista"]),
            "4_cifras_detectadas": len(metricas),
            "5_productos_vigentes_mencionados": productos_detectados
        },
        "formatos_viables": formatos_viables,
        "formatos_descartados": formatos_descartados,
        "alertas": alertas_reglas
    }