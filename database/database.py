from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "smart_shop.db"


class DatabaseManager:
    """Single SQLite access layer used by every Smart Shop page."""

    def __init__(self, db_path: Path | str = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.cursor = self.connection.cursor()
        self._create_schema()

    def _create_schema(self) -> None:
        self.cursor.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                interests TEXT DEFAULT '',
                role TEXT NOT NULL DEFAULT 'customer',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                brand TEXT DEFAULT '',
                price REAL NOT NULL DEFAULT 0,
                stock INTEGER NOT NULL DEFAULT 0,
                rating REAL NOT NULL DEFAULT 0,
                sales INTEGER NOT NULL DEFAULT 0,
                supplier TEXT DEFAULT '',
                links TEXT DEFAULT '',
                content TEXT DEFAULT '',
                description TEXT DEFAULT '',
                image TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_products_category
                ON products(category);

            CREATE INDEX IF NOT EXISTS idx_products_name
                ON products(name);

            CREATE INDEX IF NOT EXISTS idx_products_sales
                ON products(sales);

            CREATE TABLE IF NOT EXISTS chat_history (
                chat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_chat_history_user_id
                ON chat_history(user_id);

            CREATE INDEX IF NOT EXISTS idx_chat_history_created_at
                ON chat_history(created_at);
            """
        )
        # Safe schema upgrade for databases created by earlier SmartShop versions.
        # SQLite has no IF NOT EXISTS form for ADD COLUMN, so inspect first.
        user_columns = {row[1] for row in self.cursor.execute("PRAGMA table_info(users)").fetchall()}
        if "role" not in user_columns:
            self.cursor.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'customer'")
        self.cursor.execute("UPDATE users SET role='customer' WHERE role IS NULL OR TRIM(role)=''")
        self.connection.commit()

    def close(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass

    # ---------- users ----------
    def register_user(self, username: str, password: str, interests: str = "") -> bool:
        """Create a customer account with a securely hashed password."""
        try:
            password_hash = generate_password_hash(password)
            self.cursor.execute(
                "INSERT INTO users(username,password,interests,role) VALUES(?,?,?,?)",
                (username, password_hash, interests, "customer"),
            )
            self.connection.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def login_user(self, username: str, password: str):
        """Authenticate both new hashed accounts and legacy plaintext accounts.

        Legacy accounts are transparently upgraded to a password hash after the
        first successful login, so existing users keep working without a reset.
        """
        user = self.cursor.execute(
            "SELECT * FROM users WHERE username=?",
            (username,),
        ).fetchone()
        if not user:
            return None

        stored = str(user["password"] or "")
        valid = False
        is_hash = stored.startswith(("scrypt:", "pbkdf2:", "argon2:"))

        if is_hash:
            try:
                valid = check_password_hash(stored, password)
            except (ValueError, TypeError):
                valid = False
        else:
            # Backward compatibility for the original working database.
            valid = stored == password
            if valid:
                new_hash = generate_password_hash(password)
                self.cursor.execute(
                    "UPDATE users SET password=? WHERE user_id=?",
                    (new_hash, user["user_id"]),
                )
                self.connection.commit()
                user = self.cursor.execute(
                    "SELECT * FROM users WHERE user_id=?",
                    (user["user_id"],),
                ).fetchone()

        return user if valid else None

    def admin_exists(self) -> bool:
        return bool(self.cursor.execute("SELECT 1 FROM users WHERE role='admin' LIMIT 1").fetchone())

    def create_admin(self, username: str, password: str) -> bool:
        try:
            self.cursor.execute(
                "INSERT INTO users(username,password,interests,role) VALUES(?,?,?,?)",
                (username, generate_password_hash(password), "", "admin"),
            )
            self.connection.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_all_users(self):
        return self.cursor.execute(
            "SELECT user_id, username, interests, role, created_at FROM users ORDER BY user_id DESC"
        ).fetchall()

    def get_recent_users(self, limit: int = 8):
        return self.cursor.execute(
            "SELECT user_id, username, role, created_at FROM users ORDER BY user_id DESC LIMIT ?",
            (max(1, int(limit)),),
        ).fetchall()

    def update_user_role(self, user_id: int, role: str) -> bool:
        cur = self.cursor.execute("UPDATE users SET role=? WHERE user_id=?", (role, user_id))
        self.connection.commit()
        return cur.rowcount > 0

    def total_users(self) -> int:
        return int(self.cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    # ---------- chat history ----------
    def save_chat_message(self, user_id: int, question: str, answer: str) -> int:
        self.cursor.execute(
            "INSERT INTO chat_history(user_id, question, answer) VALUES(?,?,?)",
            (int(user_id), str(question).strip(), str(answer).strip()),
        )
        self.connection.commit()
        return int(self.cursor.lastrowid)

    def get_chat_history(self, user_id: int, limit: int = 50):
        limit = max(1, min(int(limit), 200))
        return self.cursor.execute(
            "SELECT * FROM chat_history WHERE user_id=? ORDER BY chat_id ASC LIMIT ?",
            (int(user_id), limit),
        ).fetchall()

    def clear_chat_history(self, user_id: int) -> None:
        self.cursor.execute("DELETE FROM chat_history WHERE user_id=?", (int(user_id),))
        self.connection.commit()

    # ---------- products ----------
    def add_product(
        self,
        name,
        category,
        brand="",
        price=0,
        stock=0,
        rating=0,
        sales=0,
        supplier="",
        links="",
        content="",
        description="",
        image="",
    ):
        self.cursor.execute(
            """
            INSERT INTO products
            (name,category,brand,price,stock,rating,sales,supplier,links,content,description,image)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                name, category, brand, float(price or 0), int(stock or 0),
                float(rating or 0), int(sales or 0), supplier, links,
                content, description, image,
            ),
        )
        self.connection.commit()
        return self.cursor.lastrowid

    def update_product(
        self,
        product_id,
        name,
        category,
        brand,
        price,
        stock,
        rating,
        sales,
        supplier,
        links,
        content,
        description,
        image,
    ):
        self.cursor.execute(
            """
            UPDATE products SET
                name=?, category=?, brand=?, price=?, stock=?, rating=?,
                sales=?, supplier=?, links=?, content=?, description=?, image=?
            WHERE product_id=?
            """,
            (
                name, category, brand, float(price or 0), int(stock or 0),
                float(rating or 0), int(sales or 0), supplier, links,
                content, description, image, product_id,
            ),
        )
        self.connection.commit()

    def delete_product(self, product_id) -> None:
        self.cursor.execute("DELETE FROM products WHERE product_id=?", (product_id,))
        self.connection.commit()

    def get_product(self, product_id):
        return self.cursor.execute(
            "SELECT * FROM products WHERE product_id=?", (product_id,)
        ).fetchone()

    def get_all_products(self):
        return self.cursor.execute(
            "SELECT * FROM products ORDER BY sales DESC, product_id DESC"
        ).fetchall()

    def latest_products(self, limit: int = 8):
        return self.cursor.execute(
            "SELECT * FROM products ORDER BY product_id DESC LIMIT ?", (limit,)
        ).fetchall()

    def best_selling_products(self, limit: int = 8):
        return self.cursor.execute(
            "SELECT * FROM products ORDER BY sales DESC, rating DESC LIMIT ?", (limit,)
        ).fetchall()

    def search_and_filter(self, keyword: str = "", category: str = "All", sort: str = "featured"):
        clauses = []
        params = []

        if keyword:
            like = f"%{keyword}%"
            clauses.append(
                "(name LIKE ? OR brand LIKE ? OR supplier LIKE ? OR category LIKE ? OR description LIKE ?)"
            )
            params.extend([like, like, like, like, like])

        if category and category != "All":
            clauses.append("category = ?")
            params.append(category)

        where = " WHERE " + " AND ".join(clauses) if clauses else ""

        order_map = {
            "featured": "sales DESC, rating DESC, product_id DESC",
            "price_low": "price ASC, product_id DESC",
            "price_high": "price DESC, product_id DESC",
            "rating": "rating DESC, sales DESC",
            "newest": "product_id DESC",
            "stock": "stock DESC, sales DESC",
        }
        order = order_map.get(sort, order_map["featured"])

        return self.cursor.execute(
            f"SELECT * FROM products{where} ORDER BY {order}",
            params,
        ).fetchall()

    def get_categories(self):
        rows = self.cursor.execute(
            """
            SELECT category, COUNT(*) AS product_count, COALESCE(SUM(sales),0) AS sales,
                   COALESCE(SUM(stock),0) AS stock
            FROM products
            GROUP BY category
            ORDER BY category COLLATE NOCASE
            """
        ).fetchall()
        return [row["category"] for row in rows]

    def category_stats(self):
        return self.cursor.execute(
            """
            SELECT category,
                   COUNT(*) AS product_count,
                   COALESCE(SUM(sales),0) AS sales,
                   COALESCE(SUM(stock),0) AS stock,
                   ROUND(AVG(rating),1) AS rating,
                   ROUND(SUM(price * stock),2) AS inventory_value
            FROM products
            GROUP BY category
            ORDER BY sales DESC, category COLLATE NOCASE
            """
        ).fetchall()

    def total_products(self) -> int:
        return int(self.cursor.execute("SELECT COUNT(*) FROM products").fetchone()[0])

    def total_categories(self) -> int:
        return int(self.cursor.execute("SELECT COUNT(DISTINCT category) FROM products").fetchone()[0])

    def total_stock(self) -> int:
        return int(self.cursor.execute("SELECT COALESCE(SUM(stock),0) FROM products").fetchone()[0])

    def total_sales(self) -> int:
        return int(self.cursor.execute("SELECT COALESCE(SUM(sales),0) FROM products").fetchone()[0])

    def inventory_value(self) -> float:
        return float(self.cursor.execute(
            "SELECT COALESCE(SUM(price * stock),0) FROM products"
        ).fetchone()[0])

    def estimated_revenue(self) -> float:
        return float(self.cursor.execute(
            "SELECT COALESCE(SUM(price * sales),0) FROM products"
        ).fetchone()[0])

    def average_rating(self) -> float:
        return float(self.cursor.execute(
            "SELECT COALESCE(AVG(rating),0) FROM products"
        ).fetchone()[0])

    def low_stock_products(self, threshold: int = 12, limit: int = 8):
        return self.cursor.execute(
            """
            SELECT * FROM products
            WHERE stock <= ?
            ORDER BY stock ASC, sales DESC
            LIMIT ?
            """,
            (threshold, limit),
        ).fetchall()

    def top_rated_products(self, limit: int = 8):
        return self.cursor.execute(
            "SELECT * FROM products ORDER BY rating DESC, sales DESC LIMIT ?", (limit,)
        ).fetchall()

    def analytics_summary(self):
        return {
            "total_products": self.total_products(),
            "total_users": self.total_users(),
            "total_categories": self.total_categories(),
            "total_stock": self.total_stock(),
            "total_sales": self.total_sales(),
            "inventory_value": self.inventory_value(),
            "estimated_revenue": self.estimated_revenue(),
            "average_rating": self.average_rating(),
        }


    # ---------- orders ----------
    def create_fulfillment_schema(self) -> None:
        self.create_orders_schema()
        self.cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS shipment_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                note TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(order_id) REFERENCES orders(order_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_shipment_events_order ON shipment_events(order_id, created_at);
            CREATE TABLE IF NOT EXISTS return_requests (
                return_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Requested',
                admin_note TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_returns_order ON return_requests(order_id);
            CREATE INDEX IF NOT EXISTS idx_returns_user ON return_requests(user_id);
            """
        )
        # Backfill a first tracking event for existing orders without events.
        self.cursor.execute("""
            INSERT INTO shipment_events(order_id,status,note)
            SELECT o.order_id, o.status, 'Order timeline initialized by Smart Shop AI'
            FROM orders o
            WHERE NOT EXISTS (SELECT 1 FROM shipment_events s WHERE s.order_id=o.order_id)
        """)
        self.connection.commit()

    def get_shipment_events(self, order_id: int):
        self.create_fulfillment_schema()
        return self.cursor.execute(
            "SELECT * FROM shipment_events WHERE order_id=? ORDER BY event_id", (order_id,)
        ).fetchall()

    def add_shipment_event(self, order_id: int, status: str, note: str = '') -> bool:
        self.create_fulfillment_schema()
        cur = self.cursor.execute(
            "INSERT INTO shipment_events(order_id,status,note) VALUES(?,?,?)",
            (order_id, status, note.strip()[:300])
        )
        self.connection.commit()
        return cur.rowcount > 0

    def get_return_for_order(self, order_id: int, user_id: int):
        self.create_fulfillment_schema()
        return self.cursor.execute(
            "SELECT * FROM return_requests WHERE order_id=? AND user_id=? ORDER BY return_id DESC LIMIT 1",
            (order_id, user_id)
        ).fetchone()

    def create_return_request(self, order_id: int, user_id: int, reason: str):
        self.create_fulfillment_schema()
        order = self.get_order_for_user(order_id, user_id)
        if not order:
            return False, 'Order not found.'
        if order['status'] not in {'Delivered'}:
            return False, 'Returns can be requested after an order is delivered.'
        existing = self.get_return_for_order(order_id, user_id)
        if existing and existing['status'] not in {'Rejected','Closed'}:
            return False, 'A return request already exists for this order.'
        if not reason.strip():
            return False, 'Please provide a return reason.'
        self.cursor.execute(
            "INSERT INTO return_requests(order_id,user_id,reason) VALUES(?,?,?)",
            (order_id, user_id, reason.strip()[:500])
        )
        self.connection.commit()
        return True, 'Return request submitted successfully.'

    def get_user_returns(self, user_id: int):
        self.create_fulfillment_schema()
        return self.cursor.execute(
            "SELECT r.*, o.total_amount, o.status AS order_status FROM return_requests r JOIN orders o ON o.order_id=r.order_id WHERE r.user_id=? ORDER BY r.return_id DESC",
            (user_id,)
        ).fetchall()

    def get_all_returns(self, status='All'):
        self.create_fulfillment_schema()
        if status and status != 'All':
            return self.cursor.execute(
                "SELECT r.*, o.total_amount, o.status AS order_status, u.username FROM return_requests r JOIN orders o ON o.order_id=r.order_id LEFT JOIN users u ON u.user_id=r.user_id WHERE r.status=? ORDER BY r.return_id DESC",
                (status,)
            ).fetchall()
        return self.cursor.execute(
            "SELECT r.*, o.total_amount, o.status AS order_status, u.username FROM return_requests r JOIN orders o ON o.order_id=r.order_id LEFT JOIN users u ON u.user_id=r.user_id ORDER BY r.return_id DESC"
        ).fetchall()

    def update_return_status(self, return_id: int, status: str, admin_note: str='') -> bool:
        self.create_fulfillment_schema()
        cur=self.cursor.execute(
            "UPDATE return_requests SET status=?, admin_note=?, updated_at=CURRENT_TIMESTAMP WHERE return_id=?",
            (status, admin_note.strip()[:500], return_id)
        )
        self.connection.commit()
        return cur.rowcount > 0

    def create_orders_schema(self) -> None:
        self.cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'Placed',
                total_amount REAL NOT NULL DEFAULT 0,
                shipping_name TEXT NOT NULL DEFAULT '',
                shipping_phone TEXT NOT NULL DEFAULT '',
                shipping_address TEXT NOT NULL DEFAULT '',
                payment_method TEXT NOT NULL DEFAULT 'Cash on Delivery',
                payment_status TEXT NOT NULL DEFAULT 'Pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS order_items (
                order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER,
                product_name TEXT NOT NULL,
                price REAL NOT NULL DEFAULT 0,
                quantity INTEGER NOT NULL DEFAULT 1,
                line_total REAL NOT NULL DEFAULT 0,
                FOREIGN KEY(order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
                FOREIGN KEY(product_id) REFERENCES products(product_id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
            CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
            CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
            """
        )
        self.connection.commit()

    def create_order(self, user_id: int, items: list, shipping_name: str,
                     shipping_phone: str, shipping_address: str,
                     payment_method: str = "Cash on Delivery"):
        self.create_orders_schema()
        try:
            self.cursor.execute("BEGIN")
            total = 0.0
            prepared = []
            for item in items:
                product_id = int(item["product_id"]); quantity = int(item["quantity"])
                product = self.cursor.execute(
                    "SELECT * FROM products WHERE product_id=?", (product_id,)
                ).fetchone()
                if not product:
                    raise ValueError("A product in the cart no longer exists.")
                stock = int(product["stock"] or 0)
                if quantity < 1 or quantity > stock:
                    raise ValueError(f"Not enough stock for {product['name']}.")
                price = float(product["price"] or 0)
                line_total = round(price * quantity, 2); total += line_total
                prepared.append((product_id, product["name"], price, quantity, line_total))
            self.cursor.execute(
                """INSERT INTO orders
                   (user_id,status,total_amount,shipping_name,shipping_phone,shipping_address,
                    payment_method,payment_status) VALUES(?,?,?,?,?,?,?,?)""",
                (user_id, "Placed", round(total, 2), shipping_name, shipping_phone,
                 shipping_address, payment_method,
                 "Pending" if payment_method == "Cash on Delivery" else "Demo Paid"),
            )
            order_id = self.cursor.lastrowid
            for product_id, product_name, price, quantity, line_total in prepared:
                self.cursor.execute(
                    """INSERT INTO order_items
                       (order_id,product_id,product_name,price,quantity,line_total)
                       VALUES(?,?,?,?,?,?)""",
                    (order_id, product_id, product_name, price, quantity, line_total),
                )
                self.cursor.execute(
                    "UPDATE products SET stock=stock-?, sales=sales+? WHERE product_id=?",
                    (quantity, quantity, product_id),
                )
            self.connection.commit()
            return order_id, round(total, 2)
        except Exception:
            self.connection.rollback(); raise

    def get_orders_for_user(self, user_id: int):
        self.create_orders_schema()
        return self.cursor.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY order_id DESC", (user_id,)
        ).fetchall()

    def get_order_for_user(self, order_id: int, user_id: int):
        self.create_orders_schema()
        return self.cursor.execute(
            "SELECT * FROM orders WHERE order_id=? AND user_id=?", (order_id, user_id)
        ).fetchone()

    def get_order_items(self, order_id: int):
        self.create_orders_schema()
        return self.cursor.execute(
            "SELECT * FROM order_items WHERE order_id=? ORDER BY order_item_id", (order_id,)
        ).fetchall()

    def total_orders(self) -> int:
        self.create_orders_schema()
        return int(self.cursor.execute("SELECT COUNT(*) FROM orders").fetchone()[0])

    def total_order_revenue(self) -> float:
        self.create_orders_schema()
        return float(self.cursor.execute(
            "SELECT COALESCE(SUM(total_amount),0) FROM orders"
        ).fetchone()[0])

    @staticmethod
    def order_statuses():
        return ["Placed", "Processing", "Shipped", "Delivered", "Cancelled"]

    def get_all_orders(self, limit=None, status="All"):
        self.create_orders_schema()
        clauses = []
        params = []
        if status and status != "All":
            clauses.append("o.status=?")
            params.append(status)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = """SELECT o.*, u.username FROM orders o
                 LEFT JOIN users u ON u.user_id=o.user_id""" + where + " ORDER BY o.order_id DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(max(1, int(limit)))
        return self.cursor.execute(sql, params).fetchall()

    def get_order(self, order_id: int):
        self.create_orders_schema()
        return self.cursor.execute(
            "SELECT o.*, u.username FROM orders o LEFT JOIN users u ON u.user_id=o.user_id WHERE o.order_id=?",
            (order_id,),
        ).fetchone()

    def update_order_status(self, order_id: int, status: str) -> bool:
        self.create_orders_schema()
        cur = self.cursor.execute("UPDATE orders SET status=? WHERE order_id=?", (status, order_id))
        self.connection.commit()
        return cur.rowcount > 0

    def clear_products(self):
        self.cursor.execute("DELETE FROM products")
        try:
            self.cursor.execute("DELETE FROM sqlite_sequence WHERE name='products'")
        except sqlite3.OperationalError:
            pass
        self.connection.commit()
