#!/bin/bash
# Day 9 — Script para ejecutar todos los tests de integración.
# Requiere: backend corriendo en localhost:8080, MongoDB con datos seed.
#
# Uso:
#   cd sp1-backend-py
#   chmod +x tests/run_tests.sh
#   ./tests/run_tests.sh

set -e

echo "=========================================="
echo "  SP1 — Tests de Integración E2E"
echo "=========================================="
echo ""

# Verificar que el backend está corriendo
echo "→ Verificando que el backend está accesible..."
if ! curl -s http://localhost:8080/api/policies/public > /dev/null 2>&1; then
    echo "  ❌ Backend no responde en localhost:8080"
    echo "  Asegúrate de que el backend esté corriendo: uvicorn main:app --port 8080"
    exit 1
fi
echo "  ✓ Backend accesible"
echo ""

# Instalar dependencias de test si no están
pip install pytest httpx --quiet 2>/dev/null

# Ejecutar tests
echo "→ Ejecutando tests E2E..."
echo ""
python -m pytest tests/test_e2e_integration.py -v --tb=short -x

echo ""
echo "=========================================="
echo "  ✅ Todos los tests pasaron"
echo "=========================================="
