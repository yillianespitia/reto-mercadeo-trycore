# Sistema Táctico de Contenidos - Reto Técnico Trycore

Sistema modular en Python diseñado para diagnosticar piezas madre, transformarlas en formatos estructurados con validación de reglas de negocio, calcular su probabilidad de éxito y agendarlas en un calendario web sin conflictos.

## Requisitos
- Python 3.10 o superior
- Librerías listadas en `requirements.txt`

## Instalación y Ejecución
1. Crear y activar entorno virtual:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```
2. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Ejecutar el flujo completo (un solo comando):
   ```bash
   python main.py
   ```
   *(Opcional para probar con otra URL en vivo: `python main.py --url https://ejemplo.com`)*
4. Ejecutar pruebas automatizadas:
   ```bash
   pytest
   ```

## Resultados
Al ejecutarse, el sistema genera en la carpeta `output/`:
- `diagnostico.json`: Indicadores medibles y alertas de la pieza madre.
- `piezas_y_agenda.json`: Contenido estructurado por formato, enlaces UTM y fechas asignadas.
- `calendario.html`: Vista web semanal interactiva para revisión y aprobación humana.
