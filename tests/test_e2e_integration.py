"""
Day 9 — Tests de Integración E2E.
Ejecuta los escenarios end-to-end contra el backend real (localhost:8080).

Uso:
    cd sp1-backend-py
    python -m pytest tests/test_e2e_integration.py -v --tb=short

Requisitos:
    - Backend corriendo en localhost:8080
    - MongoDB con datos seed cargados
    - pip install pytest httpx
"""
import os
import pytest
import httpx

BASE_URL = os.getenv("API_URL", "http://localhost:8080/api")
TIMEOUT = 15.0


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def client():
    """HTTP client compartido para toda la sesión de tests."""
    return httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)


@pytest.fixture(scope="session")
def auth_headers(client):
    """Login como admin y obtiene headers con JWT."""
    res = client.post("/auth/login", json={
        "email": "admin@sp1.com",
        "password": "Admin123!"
    })
    if res.status_code != 200:
        pytest.skip("No se pudo autenticar — ¿el backend está corriendo?")
    token = res.json().get("access_token") or res.json().get("token")
    return {"Authorization": f"Bearer {token}"}


# ──────────────────────────────────────────────────────────────────────────────
# 1. MIRA Dashboard
# ──────────────────────────────────────────────────────────────────────────────

class TestMIRA:
    """Verifica que MIRA responde con datos coherentes."""

    def test_dashboard(self, client, auth_headers):
        res = client.get("/mira/dashboard", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "resumenRiesgos" in data
        assert "scoreRiesgoGlobal" in data
        assert data["scoreRiesgoGlobal"] >= 0

    def test_risk_analysis(self, client, auth_headers):
        res = client.get("/mira/risk-analysis", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "tramites" in data
        assert isinstance(data["tramites"], list)

    def test_anomalies(self, client, auth_headers):
        res = client.get("/mira/anomalies", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "anomalias" in data

    def test_resource_priority(self, client, auth_headers):
        res = client.get("/mira/resource-priority", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "tareas" in data
        # Verificar que están ordenadas por prioridad
        if len(data["tareas"]) > 1:
            priorities = [t["prioridadMIRA"] for t in data["tareas"]]
            assert priorities == sorted(priorities)

    def test_predict_route(self, client, auth_headers):
        """Busca un trámite activo y predice su ruta."""
        # Primero obtener un trámite activo
        tramites_res = client.get("/tramites?status=ACTIVE&limit=1", headers=auth_headers)
        if tramites_res.status_code != 200 or not tramites_res.json():
            pytest.skip("No hay trámites activos para predict-route")

        tramites = tramites_res.json()
        tramite_id = tramites[0]["id"] if isinstance(tramites, list) else tramites.get("items", [{}])[0].get("id")
        if not tramite_id:
            pytest.skip("No se pudo obtener ID de trámite")

        res = client.get(f"/mira/predict-route/{tramite_id}", headers=auth_headers)
        assert res.status_code in [200, 404]  # 404 si no tiene nodos suficientes


# ──────────────────────────────────────────────────────────────────────────────
# 2. Agente Conversacional
# ──────────────────────────────────────────────────────────────────────────────

class TestAgente:
    """Verifica el flujo conversacional del agente."""

    def test_chat_saludo(self, client, auth_headers):
        """El agente responde a un saludo inicial."""
        res = client.post("/agent/chat", headers=auth_headers, json={
            "mensaje": "Hola, necesito hacer un trámite"
        })
        assert res.status_code == 200
        data = res.json()
        assert "mensaje" in data
        assert "sessionId" in data
        assert len(data["mensaje"]) > 10  # Respuesta no trivial

    def test_chat_identifica_politica(self, client, auth_headers):
        """El agente identifica una política cuando se describe el trámite."""
        # Primera interacción
        res1 = client.post("/agent/chat", headers=auth_headers, json={
            "mensaje": "Quiero solicitar un crédito personal"
        })
        assert res1.status_code == 200
        data = res1.json()
        session_id = data["sessionId"]

        # El agente debería identificar la política o pedir más info
        assert data["mensaje"]  # Hay respuesta

        # Segunda interacción con contexto
        res2 = client.post("/agent/chat", headers=auth_headers, json={
            "mensaje": "Sí, un crédito de 50000 bolivianos",
            "sessionId": session_id,
        })
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["sessionId"] == session_id

    def test_clear_session(self, client, auth_headers):
        """Limpiar sesión del agente."""
        # Crear sesión
        res = client.post("/agent/chat", headers=auth_headers, json={
            "mensaje": "test"
        })
        session_id = res.json().get("sessionId")

        # Limpiar
        res_clear = client.post("/agent/clear-session", headers=auth_headers, json={
            "sessionId": session_id
        })
        assert res_clear.status_code == 200


# ──────────────────────────────────────────────────────────────────────────────
# 3. Reportes
# ──────────────────────────────────────────────────────────────────────────────

class TestReportes:
    """Verifica generación de reportes por prompt."""

    def test_parse_prompt_excel(self, client, auth_headers):
        """LLM parsea un prompt para reporte Excel."""
        res = client.post("/reportes/parse-prompt", headers=auth_headers, json={
            "prompt": "Dame un reporte en Excel de todos los trámites completados de este mes"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["valido"] is True
        assert data["criterios"]["formato"] == "EXCEL"

    def test_parse_prompt_word(self, client, auth_headers):
        """LLM parsea un prompt para reporte Word."""
        res = client.post("/reportes/parse-prompt", headers=auth_headers, json={
            "prompt": "Genera un documento Word con los trámites rechazados"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["valido"] is True
        assert data["criterios"]["formato"] == "WORD"

    def test_generar_excel(self, client, auth_headers):
        """Genera y descarga un Excel."""
        res = client.post("/reportes/generar", headers=auth_headers, json={
            "criterios": {
                "titulo": "Test Report",
                "formato": "EXCEL",
                "estado": "COMPLETED",
                "columnas": [],
                "ordenarPor": "startedAt"
            }
        })
        assert res.status_code == 200
        assert "spreadsheetml" in res.headers.get("content-type", "")
        assert len(res.content) > 100  # Archivo no vacío

    def test_generar_word(self, client, auth_headers):
        """Genera y descarga un Word."""
        res = client.post("/reportes/generar", headers=auth_headers, json={
            "criterios": {
                "titulo": "Test Report Word",
                "formato": "WORD",
                "estado": None,
                "columnas": [],
                "ordenarPor": "startedAt"
            }
        })
        assert res.status_code == 200
        assert "wordprocessingml" in res.headers.get("content-type", "")


# ──────────────────────────────────────────────────────────────────────────────
# 4. Documentos
# ──────────────────────────────────────────────────────────────────────────────

class TestDocumentos:
    """Verifica CRUD de documentos."""

    def test_listar_documentos(self, client, auth_headers):
        """Listar documentos (puede estar vacío)."""
        res = client.get("/documentos", headers=auth_headers)
        assert res.status_code == 200

    def test_upload_documento(self, client, auth_headers):
        """Subir un archivo de prueba."""
        import tempfile
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Contenido de prueba para test E2E")
            f.flush()
            file_path = f.name

        with open(file_path, "rb") as f:
            res = client.post(
                "/documentos/upload",
                headers=auth_headers,
                files={"file": ("test_e2e.txt", f, "text/plain")},
                data={"nombre": "Test E2E Document"},
            )

        # Puede fallar si no hay tramiteId, pero al menos no debe ser 500
        assert res.status_code in [200, 201, 400, 422]


# ──────────────────────────────────────────────────────────────────────────────
# 5. Sync (Offline)
# ──────────────────────────────────────────────────────────────────────────────

class TestSync:
    """Verifica endpoints de sincronización offline."""

    def test_pull(self, client, auth_headers):
        """Pull de datos recientes."""
        res = client.post("/sync/pull", headers=auth_headers, json={
            "lastSyncTimestamp": "2026-01-01T00:00:00Z"
        })
        # Endpoint puede existir o no — verificar que no sea 500
        assert res.status_code in [200, 404, 405]

    def test_push_empty(self, client, auth_headers):
        """Push vacío (sin acciones pendientes)."""
        res = client.post("/sync/push", headers=auth_headers, json={
            "actions": []
        })
        assert res.status_code in [200, 404, 405]


# ──────────────────────────────────────────────────────────────────────────────
# 6. Políticas Públicas (sin auth — para mobile)
# ──────────────────────────────────────────────────────────────────────────────

class TestPublic:
    """Verifica endpoints públicos accesibles sin JWT."""

    def test_politicas_publicas(self, client):
        """Lista de políticas publicadas."""
        res = client.get("/policies/public")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)

    def test_tramite_por_ticket(self, client):
        """Consulta de trámite por ticket (público)."""
        res = client.get("/tramites/ticket/TKT-NONEXIST")
        # 404 es correcto si no existe, 200 si existe
        assert res.status_code in [200, 404]
