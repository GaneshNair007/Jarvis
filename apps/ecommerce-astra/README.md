# Astra Store

Single-deployable FastAPI e-commerce demo: catalog, search/filter, product detail, cart (localStorage), checkout → order record, order history, JSON API, health endpoint for Render.

## Run locally

```bash
pip install -r requirements.txt
python main.py
# open http://localhost:8000
```

Override port: `PORT=8000 python main.py` · DB path: `ASTRA_DB=astra.db`

## Tests

```bash
python -m pytest -q
```

## Render deploy

- Build Command: `pip install -r requirements.txt`
- Start Command: `python main.py`
- Env: `PORT` is read automatically by `main.py`.
- Health check: `GET /health`

## API

- `GET /health`
- `GET /api/products?q=&category=`
- `GET /api/products/{id}`
- `POST /api/orders` — `{customer_name, email, address, items:[{product_id, qty}]}`
- `GET /api/orders`, `GET /api/orders/{id}`

## Pages

`/`, `/product/{id}`, `/checkout`, `/orders`
