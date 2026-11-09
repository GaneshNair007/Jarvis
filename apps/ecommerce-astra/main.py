import os
import json
import sqlite3
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

BASE = Path(__file__).parent
DB_PATH = Path(os.environ.get("ASTRA_DB", BASE / "astra.db"))
TEMPLATES = BASE / "templates"
STATIC = BASE / "static"

app = FastAPI(title="Astra Store", version="1.0.0")
templates = Jinja2Templates(directory=str(TEMPLATES))
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            price REAL NOT NULL,
            category TEXT DEFAULT 'General',
            stock INTEGER DEFAULT 10,
            image TEXT DEFAULT ''
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            email TEXT NOT NULL,
            address TEXT DEFAULT '',
            items TEXT NOT NULL DEFAULT '[]',
            total REAL NOT NULL DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at REAL NOT NULL
        )
    """)
    con.commit()
    cur = con.execute("SELECT COUNT(*) c FROM products")
    if cur.fetchone()["c"] == 0:
        seed = [
            ("Astra Wireless Headphones", "Noise-cancelling over-ear headphones", 89.99, "Electronics", 25, ""),
            ("Astra Chrono Watch", "Minimalist analog watch with steel strap", 159.00, "Accessories", 12, ""),
            ("Astra Canvas Backpack", "25L water-resistant everyday backpack", 74.50, "Accessories", 30, ""),
            ("Astra Ceramic Mug Set", "Set of 4 hand-glazed ceramic mugs", 34.99, "Home", 40, ""),
            ("Astra Mechanical Keyboard", "Hot-swappable 75% keyboard, gasket mount", 129.00, "Electronics", 18, ""),
            ("Astra Desk Lamp", "Dimmable LED desk lamp with USB-C charging", 49.99, "Home", 22, ""),
            ("Astra Running Shoes", "Lightweight knit running shoes", 99.99, "Apparel", 15, ""),
            ("Astra Water Bottle", "Insulated 1L steel bottle, 24h cold", 29.99, "Accessories", 50, ""),
        ]
        con.executemany(
            "INSERT INTO products (name, description, price, category, stock, image) VALUES (?,?,?,?,?,?)",
            seed,
        )
        con.commit()
    con.close()


class OrderCreate(BaseModel):
    customer_name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    address: str = ""
    items: list  # [{product_id:int, qty:int}]
    total: Optional[float] = None


def row_to_product(r):
    return dict(r)


def row_to_order(r):
    d = dict(r)
    try:
        d["items_parsed"] = json.loads(d["items"])
    except Exception:
        d["items_parsed"] = []
    return d


init_db()


@app.get("/health")
def health():
    return {"status": "ok", "service": "astra-store"}


@app.get("/api/products")
def api_products(q: Optional[str] = None, category: Optional[str] = None):
    con = db()
    query = "SELECT * FROM products WHERE 1=1"
    params = []
    if q:
        query += " AND (name LIKE ? OR description LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY id"
    rows = con.execute(query, params).fetchall()
    con.close()
    return {"count": len(rows), "products": [row_to_product(r) for r in rows]}


@app.get("/api/products/{pid}")
def api_product(pid: int):
    con = db()
    r = con.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    con.close()
    if not r:
        raise HTTPException(404, "product not found")
    return row_to_product(r)


@app.post("/api/orders", status_code=201)
def api_create_order(payload: OrderCreate):
    if not payload.items:
        raise HTTPException(400, "items required")
    con = db()
    total = 0.0
    enriched = []
    for it in payload.items:
        r = con.execute("SELECT * FROM products WHERE id=?", (it.get("product_id"),)).fetchone()
        if not r:
            con.close()
            raise HTTPException(404, f"product {it.get('product_id')} not found")
        qty = int(it.get("qty", 1))
        line_total = r["price"] * qty
        total += line_total
        enriched.append(
            {
                "product_id": r["id"],
                "name": r["name"],
                "price": r["price"],
                "qty": qty,
                "line_total": round(line_total, 2),
            }
        )
    if payload.total is not None:
        total = payload.total
    ts = time.time()
    cur = con.execute(
        "INSERT INTO orders (customer_name, email, address, items, total, status, created_at) VALUES (?,?,?,?,?,?,?)",
        (payload.customer_name, payload.email, payload.address, json.dumps(enriched), round(total, 2), "pending", ts),
    )
    oid = cur.lastrowid
    con.commit()
    con.close()
    return {"id": oid, "total": round(total, 2), "status": "pending", "items": enriched}


@app.get("/api/orders")
def api_orders():
    con = db()
    rows = con.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    con.close()
    return {"count": len(rows), "orders": [row_to_order(r) for r in rows]}


@app.get("/api/orders/{oid}")
def api_order(oid: int):
    con = db()
    r = con.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    con.close()
    if not r:
        raise HTTPException(404, "order not found")
    return row_to_order(r)


@app.get("/", response_class=HTMLResponse)
def home(request: Request, q: Optional[str] = None, category: Optional[str] = None):
    con = db()
    query = "SELECT * FROM products WHERE 1=1"
    params = []
    if q:
        query += " AND (name LIKE ? OR description LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if category:
        query += " AND category = ?"
        params.append(category)
    rows = con.execute(query + " ORDER BY id", params).fetchall()
    cats = [r[0] for r in con.execute("SELECT DISTINCT category FROM products").fetchall()]
    con.close()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "products": [row_to_product(r) for r in rows],
            "categories": cats,
            "q": q or "",
            "category": category or "",
        },
    )


@app.get("/product/{pid}", response_class=HTMLResponse)
def product_page(request: Request, pid: int):
    con = db()
    r = con.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    con.close()
    if not r:
        raise HTTPException(404, "product not found")
    return templates.TemplateResponse(request, "product.html", {"request": request, "product": row_to_product(r)})


@app.get("/checkout", response_class=HTMLResponse)
def checkout_page(request: Request):
    return templates.TemplateResponse(request, "checkout.html", {"request": request})


@app.get("/orders", response_class=HTMLResponse)
def orders_page(request: Request):
    con = db()
    rows = con.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    con.close()
    return templates.TemplateResponse(
        request, "orders.html", {"request": request, "orders": [row_to_order(r) for r in rows]}
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
