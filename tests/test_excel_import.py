"""Tests for Excel import of access codes."""
import io
from unittest.mock import patch

import openpyxl
import pytest
from tests.conftest import CSRF_TOKEN

CT = {"_csrf_token": CSRF_TOKEN}


def _make_excel(codes):
    """Create an in-memory .xlsx file with codes in column A."""
    wb = openpyxl.Workbook()
    ws = wb.active
    for code in codes:
        ws.append([code])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _admin_login(client):
    client.post("/admin/login", data={**CT, "password": "testpass"})


class TestImportCodesEndpoint:
    def test_importar_codigos_desde_excel(self, client, mock_db):
        _admin_login(client)
        excel = _make_excel(["CODE1", "CODE2", "CODE3"])
        response = client.post("/admin/import-codes", data={
            "file": (excel, "codes.xlsx"),
        }, content_type="multipart/form-data")
        assert response.status_code == 200
        data = response.get_json()
        assert data["codes"] == ["CODE1", "CODE2", "CODE3"]

    def test_codigos_se_normalizan_mayusculas(self, client, mock_db):
        _admin_login(client)
        excel = _make_excel(["abc", "Def", "GHI"])
        response = client.post("/admin/import-codes", data={
            "file": (excel, "codes.xlsx"),
        }, content_type="multipart/form-data")
        assert response.status_code == 200
        data = response.get_json()
        assert data["codes"] == ["ABC", "DEF", "GHI"]

    def test_elimina_duplicados(self, client, mock_db):
        _admin_login(client)
        excel = _make_excel(["CODE1", "CODE2", "CODE1", "CODE3", "CODE2"])
        response = client.post("/admin/import-codes", data={
            "file": (excel, "codes.xlsx"),
        }, content_type="multipart/form-data")
        assert response.status_code == 200
        data = response.get_json()
        assert data["codes"] == ["CODE1", "CODE2", "CODE3"]

    def test_ignora_celdas_vacias(self, client, mock_db):
        _admin_login(client)
        excel = _make_excel(["CODE1", "", None, "CODE2"])
        response = client.post("/admin/import-codes", data={
            "file": (excel, "codes.xlsx"),
        }, content_type="multipart/form-data")
        assert response.status_code == 200
        data = response.get_json()
        assert data["codes"] == ["CODE1", "CODE2"]

    def test_codigos_numericos_se_convierten_a_string(self, client, mock_db):
        _admin_login(client)
        excel = _make_excel([12345, 67890])
        response = client.post("/admin/import-codes", data={
            "file": (excel, "codes.xlsx"),
        }, content_type="multipart/form-data")
        assert response.status_code == 200
        data = response.get_json()
        assert data["codes"] == ["12345", "67890"]

    def test_archivo_no_enviado_devuelve_400(self, client, mock_db):
        _admin_login(client)
        response = client.post("/admin/import-codes")
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_formato_no_soportado_devuelve_400(self, client, mock_db):
        _admin_login(client)
        response = client.post("/admin/import-codes", data={
            "file": (io.BytesIO(b"not excel"), "codes.csv"),
        }, content_type="multipart/form-data")
        assert response.status_code == 400
        data = response.get_json()
        assert "Formato" in data["error"]

    def test_archivo_corrupto_devuelve_400(self, client, mock_db):
        _admin_login(client)
        response = client.post("/admin/import-codes", data={
            "file": (io.BytesIO(b"not a real xlsx"), "codes.xlsx"),
        }, content_type="multipart/form-data")
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_requiere_autenticacion(self, client, mock_db):
        excel = _make_excel(["CODE1"])
        response = client.post("/admin/import-codes", data={
            "file": (excel, "codes.xlsx"),
        }, content_type="multipart/form-data")
        # Should redirect to login
        assert response.status_code == 302

    def test_excel_con_3000_codigos(self, client, mock_db):
        """Verify the endpoint handles large Excel files (3000 codes)."""
        _admin_login(client)
        codes = [f"CODE{i:04d}" for i in range(3000)]
        excel = _make_excel(codes)
        response = client.post("/admin/import-codes", data={
            "file": (excel, "codes.xlsx"),
        }, content_type="multipart/form-data")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["codes"]) == 3000
        assert data["codes"][0] == "CODE0000"
        assert data["codes"][2999] == "CODE2999"
