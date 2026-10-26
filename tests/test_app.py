import app as app_module


def test_index_renders():
    client = app_module.app.test_client()
    assert client.get("/").status_code == 200


def test_scan_without_any_api_key_is_rejected(monkeypatch):
    monkeypatch.setattr(app_module, "ENV_API_KEY", None)
    response = app_module.app.test_client().post("/scan", json={})
    assert response.status_code == 400
    assert response.get_json()["success"] is False
