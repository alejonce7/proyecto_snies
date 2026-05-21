#!/usr/bin/env python
"""
Ejecutor del diagnóstico de calidad SNIES
Uso: python scripts/run_diagnostico.py [ruta_de_archivos]
Ejemplo: python scripts/run_diagnostico.py ./data/raw
"""

import sys
from pathlib import Path

# Agregar la ruta src para poder importar
sys.path.append(str(Path(__file__).parent.parent))

from src.quality.diagnostico import DiagnosticoCalidadSNIES

if __name__ == "__main__":
    # Configurar ruta de datos
    if len(sys.argv) > 1:
        carpeta_datos = Path(sys.argv[1])
    else:
        carpeta_datos = Path("./data/raw")  # Ruta por defecto
    
    if not carpeta_datos.exists():
        print(f" La carpeta {carpeta_datos} no existe.")
        print(f"Uso: python scripts/run_diagnostico.py [ruta_de_archivos]")
        sys.exit(1)
    
    print(f"Ejecutando diagnóstico en: {carpeta_datos}")
    print("="*70)
    
    # Ejecutar diagnóstico
    diagnostico = DiagnosticoCalidadSNIES(carpeta_datos)
    reporte = diagnostico.ejecutar()
    
    print("\nDiagnóstico completado")
    print(f"📁Reportes guardados en: ./src/quality/")