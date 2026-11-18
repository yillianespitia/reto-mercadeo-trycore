import argparse
import json
from pathlib import Path
from src.agente_diagnostico import extraer_contenido, diagnosticar_pieza
from src.agente_redactor import transformar_piezas
from src.agente_planificador import cargar_historial, programar_calendario, generar_html

def main():
    parser = argparse.ArgumentParser(description="Sistema Agéntico de Contenidos - Trycore")
    parser.add_argument("--url", type=str, help="URL opcional para probar otra pieza madre en vivo")
    args = parser.parse_args()

    # Rutas de insumos
    ruta_config = "02_insumos/configuracion/config.json"
    ruta_url = "02_insumos/pieza_madre/url.txt"
    ruta_respaldo = "02_insumos/pieza_madre/guia_rpa_respaldo.html"
    ruta_ventana = "02_insumos/calendario/ventana.json"
    ruta_ocupado = "02_insumos/calendario/calendario_ocupado.csv"
    ruta_historial = "02_insumos/historial/historial_publicaciones.csv" # Verifica que el nombre coincida con tu CSV

    if args.url:
        Path("output").mkdir(exist_ok=True)
        ruta_url = "output/url_temp.txt"
        with open(ruta_url, "w", encoding="utf-8") as f:
            f.write(args.url)

    with open(ruta_config, "r", encoding="utf-8") as f:
        config = json.load(f)

    print("1. Ejecutando Agente de Diagnóstico...")
    contenido = extraer_contenido(ruta_url, ruta_respaldo)
    diagnostico = diagnosticar_pieza(contenido, config)

    print("2. Ejecutando Agente Redactor y Auditor...")
    piezas = transformar_piezas(contenido, diagnostico, config)

    print("3. Ejecutando Agente Planificador y Predictor...")
    historial = cargar_historial(ruta_historial)
    agenda = programar_calendario(piezas, ruta_ventana, ruta_ocupado, config, historial)

    # Guardar resultados en output/
    Path("output").mkdir(exist_ok=True)
    with open("output/diagnostico.json", "w", encoding="utf-8") as f:
        json.dump(diagnostico, f, indent=2, ensure_ascii=False)

    # Limpia el objeto datetime antes de exportar a JSON
    agenda_json = [{k: v for k, v in item.items() if k != "dt"} for item in agenda]
    with open("output/piezas_y_agenda.json", "w", encoding="utf-8") as f:
        json.dump(agenda_json, f, indent=2, ensure_ascii=False)

    generar_html(agenda, diagnostico, "output/calendario.html")
    print("¡Listo! Revisa los archivos generados en la carpeta 'output/' y abre 'output/calendario.html'.")

if __name__ == "__main__":
    main()
