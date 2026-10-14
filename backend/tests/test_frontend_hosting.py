"""Standalone hosting must serve the same /web/ asset paths as Docker."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import path_conf, register_frontend


def test_production_web_asset_prefix(tmp_path, monkeypatch):
    (tmp_path / "js").mkdir()
    (tmp_path / "index.html").write_text('<html><script src="/web/js/main.js"></script></html>', encoding="utf-8")
    (tmp_path / "js/main.js").write_text('console.log("ResNexus")', encoding="utf-8")
    monkeypatch.setattr(path_conf, "FRONTEND_DIST_DIR", tmp_path)
    app = FastAPI()
    register_frontend(app)
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/web/").status_code == 200
        asset = client.get("/web/js/main.js")
        assert asset.status_code == 200
        assert "javascript" in asset.headers["content-type"]
        assert asset.text == 'console.log("ResNexus")'
