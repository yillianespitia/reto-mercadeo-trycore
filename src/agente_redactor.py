import re
import unicodedata

def limpiar_slug(texto: str) -> str:
    """Convierte un texto a minúsculas, sin tildes ni espacios, separado por guiones."""
    texto_norm = unicodedata.normalize('NFD', texto.lower())
    texto_sin_tildes = ''.join(c for c in texto_norm if unicodedata.category(c) != 'Mn')
    slug = re.sub(r'[^a-z0-9]+', '-', texto_sin_tildes).strip('-')
    return slug[:30] if slug else "pieza-madre"

def construir_utm(url_base: str, config_utm: dict, canal: str, formato: str, numero: int, titulo_pieza: str, fecha_aaaamm: str = "202612") -> str:
    """Genera el enlace con parámetros UTM según la convención de config.json."""
    source = config_utm["utm_source"].get(canal, canal)
    medium = config_utm["utm_medium"].get(canal, "organico")
    slug_pieza = limpiar_slug(titulo_pieza)
    campaign = f"{slug_pieza}-{fecha_aaaamm}"
    content = f"{limpiar_slug(formato)}-{numero}"
    
    separador = "&" if "?" in url_base else "?"
    return f"{url_base}{separador}utm_source={source}&utm_medium={medium}&utm_campaign={campaign}&utm_content={content}"

def auditar_pieza(texto_completo: str, config: dict) -> list:
    """
    Valida que el texto generado no rompa ninguna regla de negocio de config.json.
    Retorna una lista de alertas si encuentra fallos.
    """
    alertas = []

    # 1. Validar términos prohibidos
    for item in config.get("terminos_prohibidos", []):
        termino = item["termino"]
        if re.search(rf'\b{re.escape(termino)}\b', texto_completo, re.IGNORECASE):
            alertas.append(f"BLOQUEO: Contiene término prohibido '{termino}' ({item['motivo']}).")

    # 2. Validar nombres confidenciales
    for nombre in config.get("nombres_confidenciales", []):
        if re.search(rf'\b{re.escape(nombre)}\b', texto_completo, re.IGNORECASE):
            alertas.append(f"BLOQUEO: Contiene cliente confidencial '{nombre}'.")

    # 3. Validar mención de productos vigentes
    productos = config.get("productos_vigentes", [])
    mencionados = [p for p in productos if re.search(rf'\b{re.escape(p)}\b', texto_completo, re.IGNORECASE)]
    if not mencionados:
        alertas.append("ADVERTENCIA: No se menciona explícitamente un producto vigente.")

    # 4. Validar cifras (si hay cifras, se marca para verificación de fuente)
    cifras = re.findall(r'\b\d+(?:[.,]\d+)?%\b', texto_completo)
    if cifras:
        alertas.append(f"REVISIÓN: Contiene cifras ({', '.join(cifras)}). Verificar respaldo en pieza madre.")

    return alertas

def transformar_piezas(contenido: dict, diagnostico: dict, config: dict) -> list:
    """
    Transforma la pieza madre en piezas estructuradas para los formatos viables,
    respetando longitudes, estructura y reglas UTM.
    """
    piezas_generadas = []
    viables = diagnostico.get("formatos_viables", [])
    matriz = {f["id"]: f for f in config.get("matriz_formatos", [])}
    
    titulo = contenido["titulo"]
    subtitulos = contenido["subtitulos"]
    parrafos = contenido["parrafos"]
    items = contenido["items_lista"]
    url_base = contenido["url_origen"]
    
    # Determinar tema principal basado en productos o título
    productos_detectados = diagnostico["indicadores_medibles"]["5_productos_vigentes_mencionados"]
    tema = limpiar_slug(productos_detectados[0]) if productos_detectados else (
        "rpa" if "rpa" in titulo.lower() else limpiar_slug(titulo.split()[0])
    )

    contador_formato = {}

    # 1. Generar POST LINKEDIN (si es viable)
    if "post_linkedin" in viables and "post_linkedin" in matriz:
        regla = matriz["post_linkedin"]
        contador_formato["post_linkedin"] = contador_formato.get("post_linkedin", 0) + 1
        enlace = construir_utm(url_base, config["utm"], regla["canal"], "post_linkedin", contador_formato["post_linkedin"], titulo)

        gancho = f"¿Sabías cómo optimizar tus procesos con {titulo}? 🚀"[:regla["gancho_max_caracteres"]]
        cuerpo = "\n\n".join(parrafos[:2]) if parrafos else titulo
        cta = f"Conoce más detalles en nuestra guía completa aquí 👉 {enlace}"
        
        texto_post = f"{gancho}\n\n{cuerpo}\n\n{cta}"
        # Ajustar longitud máxima si se pasa
        max_c = regla["longitud"]["max_caracteres"]
        if len(texto_post) > max_c:
            espacio_cuerpo = max_c - len(gancho) - len(cta) - 10
            cuerpo = cuerpo[:espacio_cuerpo].rsplit(" ", 1)[0] + "..."
            texto_post = f"{gancho}\n\n{cuerpo}\n\n{cta}"

        alertas = auditar_pieza(texto_post, config)
        if len(texto_post) < regla["longitud"]["min_caracteres"]:
            alertas.append(f"Longitud menor al mínimo ({len(texto_post)}/{regla['longitud']['min_caracteres']} caracteres).")

        piezas_generadas.append({
            "id_pieza": "PZ-01",
            "formato": "post_linkedin",
            "canal": regla["canal"],
            "tema": tema,
            "titulo": gancho,
            "estructura": {
                "gancho": gancho,
                "desarrollo": cuerpo,
                "llamado_accion": cta,
                "enlace_utm": enlace
            },
            "texto_completo": texto_post,
            "palabras": len(texto_post.split()),
            "tiene_cifra": bool(re.search(r'\d+%', texto_post)),
            "alertas": alertas,
            "estado": "Pendiente de aprobación"
        })

    # 2. Generar CARRUSEL LINKEDIN (si es viable)
    if "carrusel_linkedin" in viables and "carrusel_linkedin" in matriz:
        regla = matriz["carrusel_linkedin"]
        contador_formato["carrusel_linkedin"] = contador_formato.get("carrusel_linkedin", 0) + 1
        enlace = construir_utm(url_base, config["utm"], regla["canal"], "carrusel_linkedin", contador_formato["carrusel_linkedin"], titulo)

        elementos_fuente = items if len(items) >= 5 else subtitulos
        max_laminas_internas = min(len(elementos_fuente), regla["laminas"]["max"] - 2)
        
        portada = f"Guía clave: {titulo}"
        laminas_internas = []
        for idx, elem in enumerate(elementos_fuente[:max_laminas_internas], start=1):
            # Limitar a max_palabras_por_lamina (30 palabras)
            palabras_lamina = elem.split()[:regla["max_palabras_por_lamina"]]
            laminas_internas.append(f"Lámina {idx}: {' '.join(palabras_lamina)}")
            
        cierre = f"¿Listo para dar el siguiente paso? Lee la guía completa: {enlace}"
        texto_carrusel = f"{portada}\n" + "\n".join(laminas_internas) + f"\n{cierre}"
        alertas = auditar_pieza(texto_carrusel, config)

        piezas_generadas.append({
            "id_pieza": "PZ-02",
            "formato": "carrusel_linkedin",
            "canal": regla["canal"],
            "tema": tema,
            "titulo": portada,
            "estructura": {
                "portada": portada,
                "laminas_internas": laminas_internas,
                "cierre": cierre,
                "enlace_utm": enlace
            },
            "texto_completo": texto_carrusel,
            "palabras": len(texto_carrusel.split()),
            "tiene_cifra": bool(re.search(r'\d+%', texto_carrusel)),
            "alertas": alertas,
            "estado": "Pendiente de aprobación"
        })

    # 3. Generar NEWSLETTER (si es viable)
    if "newsletter" in viables and "newsletter" in matriz:
        regla = matriz["newsletter"]
        contador_formato["newsletter"] = contador_formato.get("newsletter", 0) + 1
        enlace = construir_utm(url_base, config["utm"], regla["canal"], "newsletter", contador_formato["newsletter"], titulo)

        asunto = f"Claves prácticas: {titulo}"[:regla["asunto_max_caracteres"]]
        introduccion = parrafos[0] if parrafos else titulo
        secciones = []
        for i in range(min(3, len(subtitulos))):
            sub = subtitulos[i]
            desc = parrafos[i + 1] if (i + 1) < len(parrafos) else sub
            secciones.append({"subtitulo": sub, "contenido": desc})

        cta = f"Explora todos los recursos aquí: {enlace}"
        cuerpo_secciones = "\n\n".join([f"### {s['subtitulo']}\n{s['contenido']}" for s in secciones])
        texto_news = f"Asunto: {asunto}\n\n{introduccion}\n\n{cuerpo_secciones}\n\n{cta}"
        alertas = auditar_pieza(texto_news, config)

        piezas_generadas.append({
            "id_pieza": "PZ-03",
            "formato": "newsletter",
            "canal": regla["canal"],
            "tema": tema,
            "titulo": asunto,
            "estructura": {
                "asunto": asunto,
                "introduccion": introduccion,
                "secciones": secciones,
                "llamado_accion": cta,
                "enlace_utm": enlace
            },
            "texto_completo": texto_news,
            "palabras": len(texto_news.split()),
            "tiene_cifra": bool(re.search(r'\d+%', texto_news)),
            "alertas": alertas,
            "estado": "Pendiente de aprobación"
        })

    return piezas_generadas