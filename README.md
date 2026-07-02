# Databases — Online Commerce Database & Web Application

A full-lifecycle database project for the **Bases de Dados** (Databases) course at **Instituto Superior Técnico (IST)**, University of Lisbon, 2022/23. The project models the data of an **online commerce company** — customers, orders, products, suppliers, deliveries, employees, and workplaces — and takes it all the way from a conceptual diagram to a working, deployed web application.

It is delivered in three parts that follow the standard database-design pipeline: **conceptual model → relational model → physical database + queries + application**.

## Part 1 — Conceptual model (`db-01.pdf`)

An **Entity–Association (ER) model** of the online-commerce domain: the entities (customer, order, product, supplier, employee, workplace and its office/warehouse specializations), their attributes, and the relationships and cardinalities between them. This is the conceptual foundation the rest of the project is built on.

## Part 2 — Relational model & integrity constraints (`db-02.ipynb`)

The systematic **conversion of the ER model into a relational schema**, following the mapping rules taught in the course:

- Each entity and relationship becomes a relation, with primary keys, foreign keys, and candidate (`UNIQUE`) keys identified.
- The `Workplace` hierarchy with its `Office` / `Warehouse` specialization is mapped explicitly.
- A set of **integrity constraints** is added to capture the business rules the plain relational model can't express on its own (e.g. an order must contain at least one product; a workplace is either an office or a warehouse but not both).

## Part 3 — Physical database, queries, triggers, views & OLAP (`db-03.ipynb`)

The schema realised in **PostgreSQL**, together with the SQL that makes it useful. This notebook is the technical heart of the project:

- **DDL** — the full `CREATE TABLE` schema with `PRIMARY KEY`, `FOREIGN KEY`, `UNIQUE`, `NOT NULL`, and typed columns.
- **Advanced integrity constraints via triggers** — business rules that can't be declared statically are enforced with PL/pgSQL functions and `CONSTRAINT TRIGGER`s: disjoint/total specialization of workplaces into offices and warehouses, and the rule that every order must contain at least one product.
- **SQL queries** — non-trivial `SELECT`s using CTEs, aggregation, `GROUP BY`/`HAVING`, correlated subqueries, `COALESCE`, and date functions (e.g. finding the customer with the most orders, or counting unpaid orders per month).
- **Views** — reusable derived relations built on top of the base tables.
- **OLAP / analytical queries** — multidimensional analysis with `GROUPING SETS`, generating date dimensions (month, day-of-month, day-of-week) and aggregating sales across several dimensions at once, in the style of a data-warehouse cube.

## Part 4 — Web application (`web/`)

A working **Flask + PostgreSQL web application** that puts a user interface on top of the schema. See [`web/README.md`](./web/README.md) for full details; in brief:

- CRUD over the main entities — customers, products, suppliers, orders, and payments — served through Jinja2 templates organised per entity.
- All database access goes through **`psycopg` (v3)** with a **connection pool** and **parameterized queries** (guarding against SQL injection).
- **Multi-statement transactions** for operations that must be atomic (e.g. creating an order and its line items together).
- Referential-integrity-aware **cascading deletes** (deleting a product cleans up the order lines, payments, and now-empty orders that depend on it).
- **Content negotiation**: every listing endpoint returns JSON instead of HTML when the client asks for `application/json`, so the same routes double as a simple API.
- Ships with a **Dockerfile**, a Heroku **Procfile**, and a `requirements.txt`, so it can run locally in a container or be deployed to a PaaS.

## The schema at a glance

The core relations (from Part 3):

- **customer** (`cust_no`, name, email *unique*, phone, address)
- **product** (`sku`, name, description, price) + EAN codes
- **supplier** (`tin`, name, address) with supply contracts for products
- **orders** (`order_no`, `cust_no` → customer, date)
- **contains** (`order_no`, `sku`, qty) — the order line items
- **pay** (`order_no`, `cust_no`) — payment records
- **employee**, **department**, **workplace** (→ **office** / **warehouse**), **works**, **process**, **delivery** — the internal/operations side

## Requirements

- PostgreSQL
- Python 3.10 with Jupyter (to run the notebooks) and the packages in `web/requirements.txt`
- Optionally Docker, to run the web app in a container

## Running the pieces

**Notebooks (Parts 2 & 3):** open `db-02.ipynb` / `db-03.ipynb` in Jupyter. Part 3 connects to PostgreSQL with the `ipython-sql` extension (`%sql postgresql://user:pass@host/db`) and runs the DDL, constraints, queries, views, and OLAP cells against a live database.

**Web app (Part 4):** see [`web/README.md`](./web/README.md). The short version:

```bash
cd web
pip install -r requirements.txt
# point DATABASE_URL at your PostgreSQL instance (see web/app.py), then:
flask run
```

or build the provided Docker image.

## Repository layout

```
.
├── db-01.pdf        # Part 1 — Entity–Association (ER) conceptual model
├── db-02.ipynb      # Part 2 — relational model + integrity constraints
├── db-03.ipynb      # Part 3 — DDL, triggers, SQL queries, views, OLAP
└── web/             # Part 4 — Flask + PostgreSQL web application
    ├── app.py       #   routes + all SQL
    ├── templates/   #   Jinja2 templates, organised per entity
    ├── static/      #   CSS
    ├── Dockerfile   #   containerised run
    ├── Procfile     #   Heroku deploy
    └── requirements.txt
```

## Notes

The notebooks and assignment are in Portuguese (a Portuguese-taught course); The `web/` scaffolding (Dockerfile, Procfile, deploy guide) was provided by the course; the graded work is the data model, the SQL, and the application logic in `app.py` and the templates.

## Authors

Group 55 — João Fidalgo (103471), José Lopes (103938), and Rodrigo Friães (104139). Course taught by Prof. Flávio Martins.
