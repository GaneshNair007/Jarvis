import os
import sys
from pathlib import Path

os.environ["ASTRA_DB"] = str(Path(__file__).parent / "test.db")
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_products_list():
    r = client.get("/api/products")
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_product_search_filter():
    r = client.get("/api/products", params={"q": "headphones"})
    assert r.status_code == 200
    test = client.get("/api/products", params={"category": "Electronics"})
    assert test.status_code == 200
    assert all(p["category"] == "Electronics" for p in test.json()["products"])


def test_product_detail():
    r = client.get("/api/products/1")
    assert r.status_code == 200
    assert "name" in r.json()


def test_create_order_and_history():
    p = client.get("/api/products/1").json()
    payload = {"customer_name": "Test User", "email": "t@example.com",
               "address": "1 Way", "items": [{"product_id": p["id"], "qty": 2}]}
    r = client.post("/api/orders", json=payload)
    assert r.status_code == 201, r.text
    oid = r.json()["id"]
    o = client.get(f"/api/orders/{oid}")
    assert o.status_code == 200
    lst = client.get("/api/orders")
    assert any(x["id"] == oid for x in lst.json()["orders"])


def test_home_page():
    r = client.get("/")
    assert r.status_code == 200
    assert "Astra Store" in r.text
