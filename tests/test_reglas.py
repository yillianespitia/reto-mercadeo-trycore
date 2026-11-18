import json
from src.agente_redactor import auditar_pieza, construir_utm
from src.agente_diagnostico import diagnosticar_pieza
from src.agente_planificador import calcular_puntaje

with open("02_insumos/configuracion/config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

def test_1_bloquea_termino_prohibido():
    """Falla si el auditor deja pasar palabras prohibidas como GPT o integración inmediata."""
    texto_malo = "Nuestro producto Docfly usa GPT y tiene integración inmediata."
    alertas = auditar_pieza(texto_malo, CONFIG)
    assert any("BLOQUEO" in a for a in alertas)

def test_2_bloquea_nombre_confidencial():
    """Falla si el auditor deja pasar un cliente confidencial."""
    texto_malo = "Caso de éxito implementado en Banco Andino del Sur con Docfly."
    alertas = auditar_pieza(texto_malo, CONFIG)
    assert any("Banco Andino del Sur" in a for a in alertas)

def test_3_alerta_si_no_hay_producto_vigente():
    """Verifica que advierta cuando no se menciona ningún producto vigente."""
    texto_sin_producto = "La automatización de procesos ayuda a ahorrar tiempo en oficina."
    alertas = auditar_pieza(texto_sin_producto, CONFIG)
    assert any("producto vigente" in a for a in alertas)

def test_4_construccion_utm_sin_tildes_ni_espacios():
    """Verifica que los enlaces UTM cumplan formato en minúsculas y sin tildes."""
    enlace = construir_utm("https://trycore.com", CONFIG["utm"], "linkedin", "post_linkedin", 1, "Guía Automatización")
    assert "utm_source=linkedin" in enlace
    assert "utm_medium=social-organico" in enlace
    assert "í" not in enlace and "ó" not in enlace and " " not in enlace

def test_5_puntaje_exito_rango_valido():
    """Verifica que el puntaje calculado siempre esté entre 0 y 100."""
    historial_falso = [{"formato": "post_linkedin", "tasa": 0.04}]
    pieza = {"formato": "post_linkedin", "tiene_cifra": True, "hora": "08:30"}
    puntaje = calcular_puntaje(pieza, historial_falso)
    assert 0 <= puntaje <= 100
