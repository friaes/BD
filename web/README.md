# Web Application — Online Commerce Manager

A **Flask + PostgreSQL** web application that provides a user interface over the online-commerce database (Parts 1–3 of this project). It lets an operator manage the shop's data and lets customers browse, create, and pay for their own orders.

## Stack

- **Flask 2.3** (Jinja2 templates, per-entity template folders)
- **psycopg 3** with **`psycopg_pool.ConnectionPool`** for database access
- **PostgreSQL** as the backing store
- **gunicorn** for production serving; **Docker** and a Heroku **Procfile** for deployment

## What it does

The app is organised around the domain entities, each with its own routes and templates:

- **Products** — list, create, update (price & description), and delete. Deleting a product also cleans up any order lines that reference it and removes orders that become empty as a result.
- **Suppliers** — list (joined with the products they supply), create, and delete (also removing the supplier's deliveries).
- **Customers** — list, create (with server-side validation of email and a Portuguese-format address), and delete (cascading through the customer's orders, payments, and processing records).
- **Orders** — list all orders (employee view) or a single customer's orders (customer view), create an order with multiple products and quantities, view an order's full breakdown with per-line and total values, and delete an order.
- **Payments** — a simple customer "login" by customer number, then pay for outstanding orders; order-info pages show which orders are already paid.

## Design highlights

- **Parameterized queries everywhere.** All SQL uses `psycopg`'s parameter binding (`%(name)s` / `%s`) rather than string interpolation, so user input can't be injected into the query.
- **Connection pooling.** A single `ConnectionPool` is created at start-up and every request borrows a connection via `with pool.connection()`, so connections are reused rather than reopened per request.
- **Transactions for multi-step writes.** Creating an order inserts the order row and all its `contains` line items inside one transaction, so a half-created order can't be left behind.
- **Application-level referential integrity.** Deletes walk the dependency graph (payments → line items → processing → orders → the entity itself) in the correct order to respect foreign keys.
- **Content negotiation.** Every listing endpoint checks the `Accept` header and returns `jsonify(...)` for JSON clients and rendered HTML for browsers — so the same URLs serve both a web UI and a lightweight JSON API. There's also a `/ping` health-check endpoint.

## Routes

| Route | Purpose |
|-------|---------|
| `/`, `/main` | Home; lists orders, seeds the next order number |
| `/main/products` … | Product list / create / update / delete |
| `/main/suppliers` … | Supplier list / create / delete |
| `/main/customers` … | Customer list / create / delete |
| `/main/orders` … | Order list (employee), create, delete |
| `/main/login` … | Customer login, per-customer orders, order info, pay |
| `/ping` | JSON health check |

## Running locally

```bash
cd web
pip install -r requirements.txt
```

Set the database connection. The app reads its connection string near the top of `app.py` (`DATABASE_URL`); point it at your PostgreSQL instance, for example:

```
postgres://<user>:<password>@<host>:<port>/<database>
```

Then run the dev server:

```bash
flask run
```

### With Docker

The provided `Dockerfile` installs the dependencies and starts the app on port 5001:

```bash
docker build -t commerce-web .
docker run -p 5001:5001 commerce-web
```

## Deploying to Heroku (optional)

The original course deploy guide:

1. [Sign up for Heroku](https://signup.heroku.com/) and install the [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli#install-the-heroku-cli).
2. Create the app: `heroku create appname`.
3. Push the app to its own Git repository (Heroku expects `Procfile`, `runtime.txt`, etc. at the repo root).
4. Add the Heroku remote: `heroku git:remote -a appname`.
5. Set the environment variables:
   ```bash
   heroku config:set FLASK_APP=app
   heroku config:set FLASK_DEBUG=0
   heroku config:set FLASK_ENV=production
   heroku config:set WEB_CONCURRENCY=3
   ```
6. Point at the database (replace with your credentials):
   ```bash
   heroku config:set DATABASE_URL=postgres://istID:pgpass@db.tecnico.ulisboa.pt/istID
   ```
7. Deploy: `git push heroku main`.
8. Open `https://appname.herokuapp.com/`.

## Files

- `app.py` — all routes and SQL.
- `wsgi.py`, `app.cgi` — WSGI/CGI entry points.
- `templates/` — Jinja2 templates, one folder per entity (`customer/`, `product/`, `supplier/`, `order/`, `pay/`) plus `base.html` and `main.html`.
- `static/style.css` — styling.
- `Dockerfile`, `Procfile`, `runtime.txt`, `requirements.txt` — packaging and deployment.
