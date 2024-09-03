#!/usr/bin/python3
from logging.config import dictConfig

import psycopg
from flask import flash
from flask import Flask
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from psycopg.rows import namedtuple_row
from psycopg_pool import ConnectionPool

import re

# postgres://{user}:{password}@{hostname}:{port}/{database-name}
DATABASE_URL = "postgres://jimei:jimei@postgres/jimei"

pool = ConnectionPool(conninfo=DATABASE_URL)
# the pool starts connecting immediately.

dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s:%(lineno)s - %(funcName)20s(): %(message)s",
            }
        },
        "handlers": {
            "wsgi": {
                "class": "logging.StreamHandler",
                "stream": "ext://flask.logging.wsgi_errors_stream",
                "formatter": "default",
            }
        },
        "root": {"level": "INFO", "handlers": ["wsgi"]},
    }
)

app = Flask(__name__)
log = app.logger
last_cust_no = 0

global max_order_no


@app.route("/", methods=("GET",))
@app.route("/main", methods=("GET",))
def main_page():
    """Show all the menus."""

    max_order_no = 0

    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            orders = cur.execute(
                """
                SELECT orders.cust_no, orders.order_no, orders.date, customer.name
                FROM orders INNER JOIN customer ON orders.cust_no = customer.cust_no
                ORDER BY cust_no ASC;
                """,
                {},
            ).fetchall()
            for order in orders:
                if order[1] > max_order_no:
                    max_order_no = order[1]
            log.debug(f"Found {cur.rowcount} rows.")

    if (
        request.accept_mimetypes["application/json"]
        and not request.accept_mimetypes["text/html"]
    ):
        return jsonify(orders)

    return render_template("main.html", max_order_no=max_order_no + 1)


@app.route("/main/products", methods=("GET",))
def product_index():
    """Show all the products alphabetically."""

    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            products = cur.execute(
                """
                SELECT SKU, name, price, description
                FROM product
                ORDER BY name ASC;
                """,
                {},
            ).fetchall()
            log.debug(f"Found {cur.rowcount} rows.")

    # API-like response is returned to clients that request JSON explicitly (e.g., fetch)
    if (
        request.accept_mimetypes["application/json"]
        and not request.accept_mimetypes["text/html"]
    ):
        return jsonify(products)

    return render_template("product/index.html", products=products)


@app.route("/main/products/<SKU>/update", methods=("GET", "POST"))
def product_update(SKU):
    """Update the product balance and description."""

    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            product = cur.execute(
                """
                SELECT SKU, name, price, description
                FROM product
                WHERE SKU = %(SKU)s;
                """,
                {"SKU": SKU},
            ).fetchone()
            log.debug(f"Found {cur.rowcount} rows.")

    if request.method == "POST":
        price = request.form["price"]
        description = request.form["description"]
        error = None

        if not price:
            error = "Price is required."
            if not price.isnumeric():
                error = "Price is required to be numeric."
        if error is not None:
            flash(error)
        else:
            with pool.connection() as conn:
                with conn.cursor(row_factory=namedtuple_row) as cur:
                    cur.execute(
                        """
                        UPDATE product
                        SET price = %(price)s, description = %(description)s
                        WHERE SKU = %(SKU)s;
                        """,
                        {"SKU": SKU, "price": price, "description": description},
                    )
                conn.commit()
            return redirect(url_for("product_index"))

    return render_template("product/update.html", product=product)


@app.route("/main/products/<SKU>/delete", methods=("POST",))
def product_delete(SKU):
    """Delete the product, and in case the product is the last contained in 
    an order, the same order is deleted."""

    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute(
                """
                SELECT order_no
                FROM contains
                WHERE sku = %(SKU)s
                """,
                {"SKU": SKU},
            )
            order_nos = [row[0] for row in cur.fetchall()]

            for order_no in order_nos:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM contains
                    WHERE order_no = %(order_no)s
                    """,
                    {"order_no": order_no},
                )
                product_count = cur.fetchone()[0]

                if product_count == 1:
                    cur.execute(
                        """
                        DELETE FROM pay
                        WHERE order_no = %(order_no)s
                        """,
                        {"order_no": order_no},
                    )
                    cur.execute(
                        """
                        DELETE FROM process
                        WHERE order_no = %(order_no)s
                        """,
                        {"order_no": order_no},
                    )

                cur.execute(
                    """
                    DELETE FROM contains
                    WHERE sku = %(SKU)s
                    AND order_no = %(order_no)s
                    """,
                    {"SKU": SKU, "order_no": order_no},
                )
                
            for order_no in order_nos:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM contains
                    WHERE order_no = %(order_no)s
                    """,
                    {"order_no": order_no},
                 )
                product_count = cur.fetchone()[0]

                if product_count == 0: 
                    cur.execute(
                        """
                        DELETE FROM orders
                        WHERE order_no = %(order_no)s
                        """,
                        {"order_no": order_no},
                )
                    
            cur.execute(
                """
                DELETE FROM delivery
                USING supplier
                INNER JOIN product USING (SKU)
                WHERE delivery.TIN = supplier.TIN
                AND supplier.SKU = %(SKU)s;
                """,
                {"SKU": SKU},
            )
            cur.execute(
                """
                DELETE FROM supplier WHERE SKU = %(SKU)s;
                """,
                {"SKU": SKU},
            )
            cur.execute(
                """
                DELETE FROM product WHERE SKU = %(SKU)s;
                """,
                {"SKU": SKU},
            )

        conn.commit()
    return redirect(url_for("product_index"))

@app.route("/main/products/create", methods=("GET", "POST",))
def product_create():
    """Create a new product."""

    if request.method == "POST":
        sku = request.form["sku"]
        name = request.form["name"]
        description = request.form["description"]
        price = request.form["price"]
        ean = request.form["ean"]

        error = None

        if ean == "":
            ean = None

        if not name:
            error = "Name is required."

        if not price:
            error = "Price is required."

        if error is not None:
            flash(error)
        else:
            with pool.connection() as conn:
                with conn.cursor(row_factory=namedtuple_row) as cur:
                    cur.execute(
                        """
                        INSERT INTO product (sku, name, description, price, ean)
                        VALUES (%s, %s, %s, %s, %s);
                        """,
                         (sku, name, description, price, ean),
                    )
                conn.commit()
            return redirect(url_for("product_index"))
    return render_template("product/create.html")

# ----------------------------------------------------------------------------------- #


@app.route("/main/suppliers", methods=("GET",))
def supplier_index():
    """Show all the suppliers, ordered by ascending TIN."""

    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            suppliers = cur.execute(
                """
                SELECT supplier.TIN, supplier.name as sn, supplier.SKU, product.name as pn
                FROM supplier
                INNER JOIN product ON supplier.SKU = product.SKU
                ORDER BY supplier.TIN ASC;
                """,
                {},
            ).fetchall()
            log.debug(f"Found {cur.rowcount} rows.")

    if (
        request.accept_mimetypes["application/json"]
        and not request.accept_mimetypes["text/html"]
    ):
        return jsonify(suppliers)

    return render_template("supplier/index.html", suppliers=suppliers)


@app.route("/main/suppliers/<TIN>/delete", methods=("POST",))
def supplier_delete(TIN):
    """Delete the supplier."""

    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute(
                """
                DELETE FROM delivery WHERE TIN = %(TIN)s;
                """,
                {"TIN": TIN},
            )
            cur.execute(
                """
                DELETE FROM supplier WHERE TIN = %(TIN)s;
                """,
                {"TIN": TIN},
            )
        conn.commit()
    return redirect(url_for("supplier_index"))


@app.route("/main/suppliers/create", methods=("GET", "POST",))
def supplier_create():
    """Create a new supplier."""

    if request.method == "POST":
        tin = request.form["tin"]
        name = request.form["name"]
        address = request.form["address"]
        sku = request.form["sku"]
        date = request.form["date"]

        error = None

        if not name:
            error = "Name is required."

        if error is not None:
            flash(error)
        else:
            with pool.connection() as conn:
                with conn.cursor(row_factory=namedtuple_row) as cur:
                    cur.execute(
                        """
                        INSERT INTO supplier (tin, name, address, sku, date)
                        VALUES (%s, %s, %s, %s, %s);
                        """,
                         (tin, name, address, sku, date),
                    )
                conn.commit()
            return redirect(url_for("supplier_index"))

    return render_template("supplier/create.html")

#--------------------------------------------------------------------------------------------#

@app.route("/main/customers", methods=("GET",))
def customer_index():
    """Show all the customers alphabetically."""

    max_cust_no = 0

    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            customers = cur.execute(
                """
                SELECT name, cust_no, phone, address
                FROM customer
                ORDER BY cust_no ASC;
                """,
                {},
            ).fetchall()
            log.debug(f"Found {cur.rowcount} rows.")
            log.debug(customers)
            for customer in customers:
                if customer[1] > max_cust_no:
                    max_cust_no = customer[1]


    if (
        request.accept_mimetypes["application/json"]
        and not request.accept_mimetypes["text/html"]
    ):
        return jsonify(customers)

    return render_template("customer/index.html", customers=customers, max_cust_no=max_cust_no + 1)


@app.route("/main/customers/create/<max_cust_no>", methods=("GET", "POST",))
def customer_create(max_cust_no):
    """Create a new customer."""

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        address = request.form["address"]

        error = None
        address_match = re.search(".*, [1-9][0-9][0-9][0-9]-[0-9][0-9][0-9] .*", address)

        if not name:
            error = "Name is required."

        if not email:
            error = "Email is required."

        if not address_match:
            error = "Address doesn't match with portuguese standards."

        if error is not None:
            flash(error)
        else:
            with pool.connection() as conn:
                with conn.cursor(row_factory=namedtuple_row) as cur:
                    cur.execute(
                        """
                        INSERT INTO customer (cust_no, name, email, phone, address)
                        VALUES (%s, %s, %s, %s, %s);
                        """,
                        (max_cust_no, name, email, phone, address),
                    )
                conn.commit()
            return redirect(url_for("customer_index"))
    return render_template("customer/create.html")


@app.route("/main/customers/<cust_no>/delete", methods=("POST",))
def customer_delete(cust_no):
    """Delete the costumer."""

    if request.method == "POST":
        with pool.connection() as conn:
            with conn.cursor(row_factory=namedtuple_row) as cur:
                cur.execute(
                    """
                    DELETE FROM pay
                    USING orders
                    INNER JOIN customer USING (cust_no)
                    WHERE orders.order_no = pay.order_no
                    AND customer.cust_no = %(cust_no)s;
                    """,
                    {"cust_no": cust_no},
                )
                cur.execute(
                    """
                    DELETE FROM contains
                    USING orders
                    INNER JOIN customer USING (cust_no)
                    WHERE orders.order_no = contains.order_no
                    AND customer.cust_no = %(cust_no)s;
                    """,
                    {"cust_no": cust_no},
                )
                cur.execute(
                    """
                    DELETE FROM process
                    USING orders
                    INNER JOIN customer USING (cust_no)
                    WHERE orders.order_no = process.order_no
                    AND customer.cust_no = %(cust_no)s;
                    """,
                    {"cust_no": cust_no},
                )
                cur.execute(
                    """
                    DELETE FROM orders
                    WHERE cust_no = %(cust_no)s
                    """,
                    {"cust_no": cust_no},
                )
                cur.execute(
                    """
                    DELETE FROM customer
                    WHERE cust_no = %(cust_no)s
                    """,
                    {"cust_no": cust_no},
                )
            conn.commit()
        return redirect(url_for("customer_index"))

#--------------------------------------------------------------------------------------------#


@app.route("/main/orders", methods=("GET",))
def order_index():
    """Show all the orders, ordered by date, recent-old.."""

    max_order_no = 0

    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            orders = cur.execute(
                """
                SELECT orders.cust_no, orders.order_no, orders.date, customer.name
                FROM orders INNER JOIN customer ON orders.cust_no = customer.cust_no
                ORDER BY date DESC;
                """,
                {},
            ).fetchall()
            for order in orders:
                if order[1] > max_order_no:
                    max_order_no = order[1]
            log.debug(f"Found {cur.rowcount} rows.")

    if (
        request.accept_mimetypes["application/json"]
        and not request.accept_mimetypes["text/html"]
    ):
        return jsonify(orders)

    return render_template("order/index.html", orders=orders, max_order_no=max_order_no)


@app.route("/main/login/<max_order_no>", methods=("GET", "POST",))
def orders_login(max_order_no):
    """Asks for the customer number, of which orders you want to interact."""

    if request.method == "POST":
        cust_no = request.form["cust_no"]
        error = None

        if not cust_no:
            error = "Customer ID is required."

        if error is not None:
            flash(error)
        else:
            with pool.connection() as conn:
                with conn.cursor(row_factory=namedtuple_row) as cur:
                    cur.execute(
                        """
                        SELECT customer.cust_no
                        FROM customer
                        WHERE cust_no = %(cust_no)s;
                        """,
                        {"cust_no": cust_no},
                    )
                conn.commit()
            return redirect(url_for("c_order_index", cust_no=cust_no, max_order_no=max_order_no))

    return render_template("pay/login.html")


@app.route("/main/login/<cust_no>/<max_order_no>", methods=("GET",))
def c_order_index(cust_no, max_order_no):
    """Show all the orders, from a specific customer, ordered by date, recent-old."""

    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            orders = cur.execute(
                """
                SELECT cust_no, order_no, date, name
                FROM orders INNER JOIN customer USING (cust_no)
                WHERE cust_no = %(cust_no)s
                ORDER BY date DESC;
                """,
                {"cust_no": cust_no},
            ).fetchall()
            log.debug(f"Found {cur.rowcount} rows.")

    if (
        request.accept_mimetypes["application/json"]
        and not request.accept_mimetypes["text/html"]
    ):
        return jsonify(orders=orders)
    return render_template("pay/index.html", orders=orders, max_order_no=max_order_no)


@app.route("/main/login/<cust_no>/<order_no>/info/pay/<max_order_no>", methods=("GET", "POST",))
def pay_order(cust_no, order_no, max_order_no):
    """Pays the given order."""
    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute(
                """
                INSERT INTO pay (order_no, cust_no)
                VALUES (%s, %s)
                """,
                (order_no, cust_no),
            )
        conn.commit()
    return redirect(url_for("c_order_index", cust_no=cust_no, max_order_no=max_order_no))

@app.route("/main/login/<cust_no>/<order_no>/info/<max_order_no>", methods=("GET", "POST",))
def order_info(order_no, cust_no, max_order_no):
    """Lists all the info from a specific order."""
    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:

            containings = cur.execute(
                    """
                    SELECT sku, qty, price, name, cust_no, qty*price as sub_total
                    FROM orders INNER JOIN (contains INNER JOIN product USING (sku)) USING (order_no)
                    WHERE order_no = %(order_no)s
                    ORDER BY order_no ASC;
                    """,
                    {"order_no" : order_no},
            ).fetchall()
            log.debug(f"Found {cur.rowcount} rows. ")

            total = cur.execute(
                    """
                    SELECT cust_no, order_no, sum(qty*price) as total_value
                    FROM orders INNER JOIN (contains INNER JOIN product USING (sku)) USING (order_no)
                    WHERE order_no = %(order_no)s
                    GROUP BY order_no
                    """,
                    {"order_no" : order_no},
            ).fetchall()
            log.debug(f"Found {cur.rowcount} rows.")

            paid_orders = cur.execute(
                """
                SELECT order_no
                FROM pay
                WHERE cust_no = %(cust_no)s
                ORDER BY cust_no ASC;
                """,
                {"cust_no" : cust_no},
            ).fetchall()
            log.debug(f"Found {cur.rowcount} rows.")

    if (
        request.accept_mimetypes["application/json"]
        and not request.accept_mimetypes["text/html"]
    ):
        return jsonify(containings=containings, total=total, paid_orders=paid_orders)
    return render_template("pay/order_info.html", containings=containings, total=total, paid_orders=paid_orders, max_order_no=max_order_no)


@app.route("/main/orders/create/<cust_no>/<max_order_no>", methods=("GET", "POST",))
def order_create(cust_no, max_order_no):
    """Create a new order."""

    skus = []
    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            products = cur.execute(
                """
                SELECT SKU, name, price, description
                FROM product
                ORDER BY name DESC;
                """,
                {},
            ).fetchall()
            for product in products:
                skus.append([product[0], 0])
            log.debug(skus)
            log.debug(f"Found {cur.rowcount} rows.")

    if (
        request.accept_mimetypes["application/json"]
        and not request.accept_mimetypes["text/html"]
    ):
        return jsonify(products)

    if request.method == "POST":

        qtys = request.form.getlist("qty")
        log.debug(qtys)
        i = 0

        for qty in qtys:
            skus[i][1] = qty
            i += 1

        log.debug(qtys)

        if not all(int(qty) == 0 for qty in qtys):
            with pool.connection() as conn:
                with conn.cursor(row_factory=namedtuple_row) as cur:
                    cur.execute(
                        """
                        BEGIN TRANSACTION
                        """
                    )
                    cur.execute(
                        """
                        INSERT INTO orders (order_no, cust_no, date)
                        VALUES (%s, %s, CURRENT_DATE)
                        """,
                        (max_order_no, cust_no),
                    )
                    for sku, qty in skus:
                        if int(qty) > 0:
                            cur.execute(
                                """
                                INSERT INTO contains (order_no, sku, qty)
                                VALUES (%s, %s, %s)
                                """,
                                (max_order_no, sku, qty),
                            )
                    cur.execute(
                        """
                        COMMIT;
                        """
                    )
                conn.commit()
            return redirect(url_for("c_order_index", cust_no=cust_no, max_order_no=int(max_order_no) + 1))

    return render_template("pay/for_order.html", products=products)


@app.route("/main/login/<cust_no>/<order_no>/info/delete/<max_order_no>/<flag>", methods=("POST",))
def order_delete(cust_no, order_no, max_order_no, flag):
    """Delete the order."""

    if request.method == "POST":
        with pool.connection() as conn:
            with conn.cursor(row_factory=namedtuple_row) as cur:
                cur.execute(
                    """
                    DELETE FROM pay
                    WHERE order_no = %(order_no)s
                    """,
                    {"order_no": order_no},
                )
                cur.execute(
                    """
                    DELETE FROM process
                    WHERE order_no = %(order_no)s
                    """,
                    {"order_no": order_no},
                )
                cur.execute(
                    """
                   DELETE FROM contains
                   WHERE order_no= %(order_no)s
                    """,
                    {"order_no": order_no},
                )
                cur.execute(
                    """
                    DELETE FROM orders
                    WHERE order_no = %(order_no)s
                    """,
                    {"order_no": order_no},
                )
            conn.commit()
        if flag == 'customer':    
            return redirect(url_for("c_order_index", cust_no=cust_no, max_order_no=max_order_no))
        elif flag == 'employee':
            return redirect(url_for("order_index", max_order_no=max_order_no))
            

@app.route("/ping", methods=("GET",))
def ping():
    log.debug("ping!")
    return jsonify({"message": "pong!", "status": "success"})


if __name__ == "__main__":
    app.run()
