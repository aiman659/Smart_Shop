from __future__ import annotations

from pathlib import Path
import sys
import re
from math import ceil

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from database.database import DatabaseManager

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))
app.secret_key = "smart-shop-ai-development-key-2026"


def ensure_catalogue():
    db = DatabaseManager()
    try:
        empty = db.total_products() == 0
    finally:
        db.close()
    if empty:
        from seed_shop import seed_catalogue
        seed_catalogue()


def cart_map():
    raw = session.get("cart", {})
    if isinstance(raw, dict):
        clean = {}
        for key, value in raw.items():
            try:
                pid, qty = int(key), max(1, int(value))
                clean[pid] = qty
            except (TypeError, ValueError):
                continue
        return clean
    if isinstance(raw, list):
        result = {}
        for pid in raw:
            try:
                pid = int(pid)
                result[pid] = result.get(pid, 0) + 1
            except (TypeError, ValueError):
                pass
        return result
    return {}


def wishlist_ids():
    raw = session.get("wishlist", [])
    if not isinstance(raw, list):
        return []
    result = []
    for value in raw:
        try:
            pid = int(value)
            if pid not in result:
                result.append(pid)
        except (TypeError, ValueError):
            pass
    return result


def ai_score(product):
    sales = int(product["sales"] or 0)
    rating = float(product["rating"] or 0)
    stock = int(product["stock"] or 0)
    sales_component = min(sales / 420, 1) * 45
    rating_component = min(rating / 5, 1) * 30
    availability_component = min(stock / 85, 1) * 25
    return round(sales_component + rating_component + availability_component)


app.jinja_env.globals["ai_score"] = ai_score
app.jinja_env.globals["wishlist_ids"] = wishlist_ids


def paginate(items, page, per_page=12):
    total = len(items)
    pages = max(1, ceil(total / per_page))
    page = min(max(1, page), pages)
    start = (page - 1) * per_page
    return items[start:start + per_page], page, pages, total


@app.context_processor
def global_shop_data():
    cart = cart_map()
    wish = wishlist_ids()
    return {
        "cart_count": sum(cart.values()),
        "cart_map": cart,
        "wishlist_count": len(wish),
        "wishlist_ids": wish,
        "current_endpoint": request.endpoint or "",
        "ai_score": ai_score,
        "is_admin": is_admin(),
    }


@app.before_request
def startup():
    if not getattr(app, "_catalogue_ready", False):
        ensure_catalogue()
        app._catalogue_ready = True


@app.route("/")
def home():
    db = DatabaseManager()
    try:
        best_products = db.best_selling_products(8)
        latest_products = db.latest_products(8)
        categories_raw = db.category_stats()
        all_products = db.get_all_products()
        summary = db.analytics_summary()
    finally:
        db.close()
    first_image = {}
    for p in all_products:
        first_image.setdefault(p["category"], p["image"] or "product_1.svg")
    categories = [dict(c) | {"image": first_image.get(c["category"], "product_1.svg")} for c in categories_raw]
    return render_template("index.html", best_products=best_products, latest_products=latest_products,
                           categories=categories, summary=summary)


@app.route("/products")
def products():
    keyword = request.args.get("search", "").strip()
    category = request.args.get("category", "All").strip() or "All"
    sort = request.args.get("sort", "featured").strip()
    try: page = int(request.args.get("page", 1))
    except ValueError: page = 1
    db = DatabaseManager()
    try:
        all_items = list(db.search_and_filter(keyword, category, sort))
        categories = db.get_categories()
    finally:
        db.close()
    items, page, pages, total = paginate(all_items, page, 12)
    return render_template("products.html", products=items, categories=categories, keyword=keyword,
                           selected_category=category, selected_sort=sort, page=page, pages=pages, total=total)


@app.route("/search")
def search():
    keyword = request.args.get("q", "").strip()
    category = request.args.get("category", "All").strip() or "All"
    sort = request.args.get("sort", "featured").strip()
    try: page = int(request.args.get("page", 1))
    except ValueError: page = 1
    db = DatabaseManager()
    try:
        all_items = list(db.search_and_filter(keyword, category, sort))
        categories = db.get_categories()
    finally:
        db.close()
    items, page, pages, total = paginate(all_items, page, 12)
    return render_template("search.html", products=items, categories=categories, keyword=keyword,
                           selected_category=category, selected_sort=sort, page=page, pages=pages, total=total)


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    db = DatabaseManager()
    try:
        product = db.get_product(product_id)
        related = []
        if product:
            related = [p for p in db.search_and_filter("", product["category"], "featured") if p["product_id"] != product_id][:4]
    finally:
        db.close()
    if not product:
        return render_template("404.html"), 404
    return render_template("product_detail.html", product=product, related=related)


@app.route("/products/add", methods=["GET", "POST"])
def add_product():

    access = admin_required()
    if access:
        return access
    db = DatabaseManager()
    try:
        categories = db.get_categories()
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            category = request.form.get("category", "").strip()
            brand = request.form.get("brand", "").strip() or "NovaWear"
            supplier = request.form.get("supplier", "").strip() or "FashionHub Supply"
            description = request.form.get("description", "").strip()
            image = request.form.get("image", "").strip() or "product_1.svg"
            links = request.form.get("links", "").strip()
            if not name or not category:
                flash("Product name and category are required.")
                return render_template("add_product.html", categories=categories, product=None, edit_mode=False)
            def number(name, kind=float, default=0):
                try: return max(0, kind(request.form.get(name, default)))
                except (TypeError, ValueError): return default
            price = number("price", float); stock = number("stock", int); sales = number("sales", int)
            rating = min(5, number("rating", float))
            db.add_product(name, category, brand, price, stock, rating, sales, supplier,
                           links, description, description, image)
            flash("Product added successfully.")
            return redirect(url_for("products"))
    finally:
        db.close()
    return render_template("add_product.html", categories=categories, product=None, edit_mode=False)


@app.route("/products/edit/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):

    access = admin_required()
    if access:
        return access
    db = DatabaseManager()
    try:
        product = db.get_product(product_id)
        categories = db.get_categories()
        if not product:
            return render_template("404.html"), 404
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            category = request.form.get("category", "").strip()
            brand = request.form.get("brand", "").strip()
            supplier = request.form.get("supplier", "").strip()
            description = request.form.get("description", "").strip()
            image = request.form.get("image", "").strip() or product["image"]
            links = request.form.get("links", "").strip()
            def number(name, kind=float, default=0):
                try: return max(0, kind(request.form.get(name, default)))
                except (TypeError, ValueError): return default
            price = number("price", float); stock = number("stock", int); sales = number("sales", int)
            rating = min(5, number("rating", float))
            db.update_product(product_id, name, category, brand, price, stock, rating, sales,
                              supplier, links, description, description, image)
            flash("Product updated successfully.")
            return redirect(url_for("product_detail", product_id=product_id))
    finally:
        db.close()
    return render_template("add_product.html", categories=categories, product=product, edit_mode=True)


@app.route("/products/delete/<int:product_id>", methods=["POST"])
def delete_product(product_id):

    access = admin_required()
    if access:
        return access
    db = DatabaseManager()
    try: db.delete_product(product_id)
    finally: db.close()
    cart = cart_map(); cart.pop(product_id, None); session["cart"] = cart
    wish = wishlist_ids(); session["wishlist"] = [x for x in wish if x != product_id]
    flash("Product deleted.")
    return redirect(url_for("products"))


@app.route("/dashboard")
def dashboard():

    access = admin_required()
    if access:
        return access
    db = DatabaseManager()
    try:
        summary = db.analytics_summary()
        best_products = db.best_selling_products(6)
        latest_products = db.latest_products(6)
        top_categories = db.category_stats()[:8]
        low_stock = db.low_stock_products(12, 6)
    finally: db.close()
    return render_template("dashboard.html", summary=summary, best_products=best_products,
                           latest_products=latest_products, top_categories=top_categories, low_stock=low_stock)


@app.route("/analytics")
def analytics():

    access = admin_required()
    if access:
        return access
    db = DatabaseManager()
    try:
        summary = db.analytics_summary()
        category_stats = db.category_stats()
        best_products = db.best_selling_products(10)
        low_stock = db.low_stock_products(12, 8)
        top_rated = db.top_rated_products(6)
    finally: db.close()
    max_sales = max([int(x["sales"]) for x in category_stats] or [1])
    return render_template("analytics.html", summary=summary, category_stats=category_stats,
                           best_products=best_products, low_stock=low_stock, top_rated=top_rated,
                           max_sales=max_sales)


def _recommendation_profile(db):
    """Build transparent preference signals from real Smart Shop activity."""
    profile = {"categories": {}, "brands": {}, "terms": set(), "source": []}
    user_id = session.get("user_id")
    if not user_id:
        return profile

    user = db.cursor.execute("SELECT interests FROM users WHERE user_id=?", (int(user_id),)).fetchone()
    if user and user["interests"]:
        terms = _tokens(user["interests"])
        profile["terms"].update(terms)
        profile["source"].append("your saved interests")

    # Wishlist/cart are session-level signals and never leave the local app.
    for pid in wishlist_ids():
        product = db.get_product(pid)
        if product:
            profile["categories"][product["category"]] = profile["categories"].get(product["category"], 0) + 4
            if product["brand"]:
                profile["brands"][product["brand"]] = profile["brands"].get(product["brand"], 0) + 2
    if wishlist_ids():
        profile["source"].append("your wishlist")

    for pid, qty in cart_map().items():
        product = db.get_product(pid)
        if product:
            weight = min(int(qty), 4) * 3
            profile["categories"][product["category"]] = profile["categories"].get(product["category"], 0) + weight
            if product["brand"]:
                profile["brands"][product["brand"]] = profile["brands"].get(product["brand"], 0) + min(int(qty), 2)
    if cart_map():
        profile["source"].append("your current cart")

    # Order history is a strong long-term signal.
    try:
        db.create_orders_schema()
        order_rows = db.cursor.execute(
            """SELECT oi.product_id, oi.product_name, oi.quantity, p.category, p.brand
               FROM order_items oi LEFT JOIN orders o ON o.order_id=oi.order_id
               LEFT JOIN products p ON p.product_id=oi.product_id
               WHERE o.user_id=? ORDER BY o.order_id DESC""", (int(user_id),)
        ).fetchall()
        for row in order_rows:
            if row["category"]:
                profile["categories"][row["category"]] = profile["categories"].get(row["category"], 0) + min(int(row["quantity"] or 1), 5) * 5
            if row["brand"]:
                profile["brands"][row["brand"]] = profile["brands"].get(row["brand"], 0) + 3
        if order_rows:
            profile["source"].append("your order history")
    except Exception:
        pass

    # Chat history is used only as a lightweight intent signal; product facts still come from products.
    try:
        chats = db.get_chat_history(int(user_id), 30)
        for row in chats:
            profile["terms"].update(_tokens(row["question"]))
        if chats:
            profile["source"].append("your recent AI shopping questions")
    except Exception:
        pass
    return profile


def _personalized_recommendations(db, products):
    profile = _recommendation_profile(db)
    rows = []
    for product in products:
        if int(product["stock"] or 0) <= 0:
            continue
        category = str(product["category"] or "")
        brand = str(product["brand"] or "")
        text = " ".join(str(product.get(k) or "") for k in ("name", "category", "brand", "description"))
        tokens = _tokens(text)
        category_signal = profile["categories"].get(category, 0)
        brand_signal = profile["brands"].get(brand, 0)
        term_signal = len(tokens & profile["terms"])
        quality = (float(product["rating"] or 0) / 5) * 18
        popularity = min(int(product["sales"] or 0) / 400, 1) * 12
        freshness = min(int(product["stock"] or 0) / 30, 1) * 5
        personal = min(category_signal * 5 + brand_signal * 3 + term_signal * 7, 48)
        score = round(min(100, personal + quality + popularity + freshness))
        if personal >= 28 and category_signal:
            reason = f"It matches your interest in {category}."
        elif brand_signal >= 4:
            reason = f"It matches a brand you have interacted with before: {brand}."
        elif term_signal:
            reason = "Its catalogue details match themes from your recent shopping activity."
        else:
            reason = "It is a strong catalogue pick based on rating, demand and availability."
        rows.append({"product": product, "score": score, "reason": reason, "personal": personal})
    rows.sort(key=lambda x: (x["score"], x["personal"], float(x["product"]["rating"] or 0), int(x["product"]["sales"] or 0)), reverse=True)
    return rows[:8], profile


@app.route("/recommendations")
def recommendations():
    db = DatabaseManager()
    try:
        products = db.get_all_products()
        personalized, profile = _personalized_recommendations(db, products)
        trending = []
        for product in products:
            if int(product["stock"] or 0) <= 0:
                continue
            score = ai_score(product)
            trending.append({"product": product, "score": score})
        trending.sort(key=lambda x: x["score"], reverse=True)
    finally:
        db.close()
    if profile["source"]:
        intro = "AI combines " + ", ".join(profile["source"][:3]) + " with live catalogue quality signals."
    else:
        intro = "Start shopping and Smart Shop AI will turn your real catalogue activity into personalized picks."
    return render_template("recommendations.html", personalized=personalized, trending=trending[:6], intro=intro)


@app.route("/cart")
def cart():
    cart = cart_map(); rows = []
    db = DatabaseManager()
    try:
        for product_id, quantity in cart.items():
            product = db.get_product(product_id)
            if product: rows.append({"product": product, "quantity": quantity})
    finally: db.close()
    subtotal = sum(float(item["product"]["price"]) * item["quantity"] for item in rows)
    return render_template("cart.html", items=rows, subtotal=subtotal)



def admin_required():
    """Allow only authenticated Smart Shop AI administrators."""
    if not session.get("user_id"):
        flash("Please log in as an administrator.")
        return redirect(url_for("login", next=request.path))
    if session.get("role") != "admin":
        flash("Administrator access is required for this area.")
        return redirect(url_for("home"))
    return None


def is_admin():
    return session.get("role") == "admin"


def login_required():
    return bool(session.get("user_id"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if not login_required():
        flash("Please log in before checkout.")
        return redirect(url_for("login"))
    cart = cart_map()
    if not cart:
        flash("Your cart is empty.")
        return redirect(url_for("cart"))
    db = DatabaseManager()
    try:
        rows = []
        for product_id, quantity in cart.items():
            product = db.get_product(product_id)
            if not product:
                flash("A product in your cart is no longer available.")
                return redirect(url_for("cart"))
            if quantity > int(product["stock"]):
                flash(f"Not enough stock for {product['name']}. Please update your cart.")
                return redirect(url_for("cart"))
            rows.append({"product": product, "quantity": quantity})
        subtotal = sum(float(x["product"]["price"]) * x["quantity"] for x in rows)

        if request.method == "POST":
            name = request.form.get("shipping_name", "").strip()
            phone = request.form.get("shipping_phone", "").strip()
            address = request.form.get("shipping_address", "").strip()
            payment = request.form.get("payment_method", "Cash on Delivery").strip()
            allowed = {"Cash on Delivery", "Demo Card Payment"}
            if payment not in allowed:
                payment = "Cash on Delivery"
            if not name or not phone or not address:
                flash("Name, phone and delivery address are required.")
                return render_template("checkout.html", items=rows, subtotal=subtotal)
            try:
                order_id, total = db.create_order(
                    int(session["user_id"]),
                    [{"product_id": p["product_id"], "quantity": q} for p, q in
                     [(x["product"], x["quantity"]) for x in rows]],
                    name, phone, address, payment
                )
            except ValueError as exc:
                flash(str(exc))
                return redirect(url_for("cart"))
            session["cart"] = {}
            flash(f"Order #{order_id} placed successfully.")
            return redirect(url_for("order_detail", order_id=order_id))
    finally:
        db.close()
    return render_template("checkout.html", items=rows, subtotal=subtotal)


@app.route("/orders")
def orders():
    if not login_required():
        flash("Please log in to view your orders.")
        return redirect(url_for("login"))
    db = DatabaseManager()
    try:
        order_rows = db.get_orders_for_user(int(session["user_id"]))
    finally:
        db.close()
    return render_template("orders.html", orders=order_rows)


@app.route("/orders/<int:order_id>")
def order_detail(order_id):
    if not login_required():
        flash("Please log in to view your order.")
        return redirect(url_for("login"))
    db = DatabaseManager()
    try:
        order = db.get_order_for_user(order_id, int(session["user_id"]))
        if not order:
            return render_template("404.html"), 404
        items = db.get_order_items(order_id)
        db.create_fulfillment_schema()
        tracking = db.get_shipment_events(order_id)
        return_request = db.get_return_for_order(order_id, int(session["user_id"]))
    finally:
        db.close()
    return render_template("order_detail.html", order=order, items=items, tracking=tracking, return_request=return_request)

@app.route("/cart/add/<int:product_id>", methods=["POST", "GET"])
def add_to_cart(product_id):
    db = DatabaseManager()
    try: product = db.get_product(product_id)
    finally: db.close()
    if not product:
        flash("Product not found."); return redirect(url_for("products"))
    if int(product["stock"]) <= 0:
        flash("That product is currently out of stock."); return redirect(request.referrer or url_for("products"))
    cart = cart_map(); current = cart.get(product_id, 0)
    if current < int(product["stock"]):
        cart[product_id] = current + 1; session["cart"] = cart
        flash(f"{product['name']} added to cart.")
    else: flash("Maximum available stock is already in your cart.")
    return redirect(request.referrer or url_for("products"))


@app.route("/cart/update/<int:product_id>", methods=["POST"])
def update_cart(product_id):
    db = DatabaseManager()
    try: product = db.get_product(product_id)
    finally: db.close()
    cart = cart_map()
    try: quantity = int(request.form.get("quantity", 1))
    except ValueError: quantity = 1
    if not product or quantity <= 0: cart.pop(product_id, None)
    else: cart[product_id] = min(quantity, int(product["stock"]))
    session["cart"] = cart
    flash("Cart updated.")
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:product_id>", methods=["POST"])
def remove_from_cart(product_id):
    cart = cart_map(); cart.pop(product_id, None); session["cart"] = cart
    flash("Item removed from cart.")
    return redirect(url_for("cart"))


@app.route("/cart/clear", methods=["POST"])
def clear_cart():
    session["cart"] = {}; flash("Cart cleared."); return redirect(url_for("cart"))


@app.route("/wishlist")
def wishlist():
    ids = wishlist_ids(); products = []
    db = DatabaseManager()
    try:
        for pid in ids:
            p = db.get_product(pid)
            if p: products.append(p)
    finally: db.close()
    return render_template("wishlist.html", products=products)


@app.route("/wishlist/toggle/<int:product_id>", methods=["POST", "GET"])
def toggle_wishlist(product_id):
    db = DatabaseManager()
    try: product = db.get_product(product_id)
    finally: db.close()
    if not product:
        flash("Product not found."); return redirect(url_for("products"))
    ids = wishlist_ids()
    if product_id in ids:
        ids.remove(product_id); flash("Removed from wishlist.")
    else:
        ids.append(product_id); flash("Added to wishlist.")
    session["wishlist"] = ids
    return redirect(request.referrer or url_for("wishlist"))



# ---------- Module 4: AI Shopping Advisor ----------
def _money_value(text):
    """Extract a likely budget/price from natural-language shopping text."""
    if not text:
        return None
    cleaned = text.lower().replace(",", "")
    patterns = [
        r'(?:rs\.?|pkr|rupees?)\s*(\d+(?:\.\d+)?)\s*(k|thousand|lac|lakh|m)?',
        r'(\d+(?:\.\d+)?)\s*(k|thousand|lac|lakh|m)?\s*(?:rs\.?|pkr|rupees?)',
        r'\$\s*(\d+(?:\.\d+)?)\s*(k|thousand|m)?',
    ]
    for pat in patterns:
        m = re.search(pat, cleaned)
        if not m:
            continue
        value = float(m.group(1))
        suffix = (m.group(2) or "").lower()
        if suffix in {"k", "thousand"}:
            value *= 1000
        elif suffix in {"lac", "lakh"}:
            value *= 100000
        elif suffix == "m":
            value *= 1000000
        # If the user says a bare number in a shopping context, don't treat
        # small quantities such as "2" as a budget.
        if value >= 500:
            return value
    return None


def _normalize_text(value):
    value = str(value or "").lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _tokens(value):
    return {t for t in _normalize_text(value).split() if len(t) >= 2}


def _catalogue_snapshot(db):
    """Return only facts that currently exist in the local catalogue."""
    rows = [dict(r) for r in db.get_all_products()]
    in_stock = [p for p in rows if int(p.get("stock") or 0) > 0]
    categories = sorted({str(p.get("category") or "").strip() for p in rows if p.get("category")}, key=str.casefold)
    return rows, in_stock, categories


def _find_catalogue_intent(question, products, categories):
    """Find a catalogue-backed category/product mention; never invent one."""
    qn = _normalize_text(question)
    qt = _tokens(qn)
    best = None

    # Exact/near category matches are strongest.
    for category in categories:
        cn = _normalize_text(category)
        ct = _tokens(cn)
        overlap = len(qt & ct)
        phrase = cn in qn
        score = 100 if phrase else overlap * 25
        # Singular/plural-friendly category matching.
        if not phrase:
            singular = {t.rstrip("s") for t in ct}
            qsing = {t.rstrip("s") for t in qt}
            score = max(score, len(singular & qsing) * 28)
        if score and (best is None or score > best[0]):
            best = (score, "category", category)

    # Product-name/brand/description matches are also catalogue facts.
    for product in products:
        text = " ".join(str(product.get(k) or "") for k in ("name", "brand", "category", "description"))
        pn = _normalize_text(text)
        pt = _tokens(pn)
        overlap = len(qt & pt)
        name_tokens = _tokens(product.get("name"))
        name_overlap = len(qt & name_tokens)
        phrase = _normalize_text(product.get("name")) in qn if product.get("name") else False
        score = (120 if phrase else 0) + name_overlap * 35 + overlap * 8
        if score and (best is None or score > best[0]):
            best = (score, "product", product)

    return best


def _is_general_catalogue_question(question):
    q = _normalize_text(question)
    general_terms = {
        "what do you have", "what products", "products do you have", "show products",
        "show me products", "available products", "available categories", "what is available",
        "what can i buy", "what can i purchase", "catalogue", "catalog", "inventory",
    }
    return any(term in q for term in general_terms)


def _ai_shopping_advisor(question, db):
    """Catalogue-grounded shopping intelligence. It must refuse unsupported items."""
    q = question.strip()
    budget = _money_value(q)
    all_products, in_stock, categories = _catalogue_snapshot(db)

    if not all_products:
        return {
            "answer": "I checked the SmartShop catalogue, but there are currently no products stored in it. I won't invent a recommendation.",
            "products": [], "advisor": True, "budget": budget, "available_categories": []
        }

    # First-class 'show me what you actually have' response.
    if _is_general_catalogue_question(q):
        available = []
        for category in categories:
            count = sum(1 for p in in_stock if p.get("category") == category)
            if count:
                available.append(f"{category} ({count} in stock)")
        shown = ", ".join(available)
        answer = (
            "🧠 I only recommend products that exist in SmartShop's live catalogue. "
            f"Right now I can work with: {shown}. "
            "If a product is not in this list, I'll tell you it isn't available rather than making one up."
        )
        return {"answer": answer, "products": [], "advisor": True, "budget": budget,
                "available_categories": categories}

    intent = _find_catalogue_intent(q, in_stock, categories)

    # No catalogue evidence = explicit refusal. This is the anti-hallucination gate.
    if intent is None or intent[0] < 20:
        available = ", ".join(categories)
        return {
            "answer": (
                "🚫 I can't find that product in the SmartShop catalogue. "
                "I won't make up a product that we don't sell. "
                f"What I can actually help you shop for is: {available}."
            ),
            "products": [], "advisor": True, "budget": budget,
            "available_categories": categories, "catalogue_refusal": True
        }

    _, intent_type, intent_value = intent
    if intent_type == "category":
        category = intent_value
        candidates = [p for p in in_stock if p.get("category") == category]
        if not candidates:
            return {
                "answer": f"🚫 {category} is in the catalogue, but there are no units currently in stock. I won't recommend an out-of-stock item.",
                "products": [], "advisor": True, "budget": budget,
                "available_categories": categories, "catalogue_refusal": True
            }
    else:
        product = intent_value
        # Product intent must remain inside the exact catalogue record.
        candidates = [p for p in in_stock if p.get("product_id") == product.get("product_id")]
        if not candidates:
            return {
                "answer": f"🚫 {product.get('name')} exists in the catalogue, but it is currently out of stock. I won't recommend it as available.",
                "products": [], "advisor": True, "budget": budget,
                "available_categories": categories, "catalogue_refusal": True
            }

    # If a budget was supplied, never recommend an item above it when a match exists.
    budget_note = ""
    if budget is not None:
        within = [p for p in candidates if float(p.get("price") or 0) <= budget]
        if within:
            candidates = within
        else:
            return {
                "answer": (
                    f"💡 I found real {intent_value if intent_type == 'category' else 'catalogue'} matches, "
                    f"but none are within your stated budget of {budget:,.0f}. "
                    "I won't quietly recommend something more expensive. Try a higher budget or another category."
                ),
                "products": [], "advisor": True, "budget": budget,
                "available_categories": categories, "budget_miss": True
            }

    # Score only the already-proven catalogue candidates.
    scored = []
    for p in candidates:
        price = float(p.get("price") or 0)
        rating = float(p.get("rating") or 0)
        sales = int(p.get("sales") or 0)
        stock = int(p.get("stock") or 0)
        affordability = 1.0 if budget is None else max(0.0, 1.0 - (price / max(budget, 1)) * 0.55)
        score = (affordability * 35 + min(rating / 5, 1) * 30 + min(sales / 400, 1) * 20 + min(stock / 25, 1) * 15)
        scored.append((score, p))
    scored.sort(key=lambda x: (x[0], float(x[1].get("rating") or 0), int(x[1].get("sales") or 0)), reverse=True)

    top = scored[:3]
    best_score, best = top[0]
    category = best.get("category") or "this category"
    price = float(best.get("price") or 0)
    reasons = [f"it is a real {category} from the catalogue"]
    if budget is not None:
        reasons.append("it is within your stated budget")
    if float(best.get("rating") or 0) >= 4.5:
        reasons.append("it has a strong catalogue rating")
    if int(best.get("sales") or 0) >= 200:
        reasons.append("it has strong recorded sales")

    answer = f"✨ I found a real match: {best['name']}. I chose it because " + ", ".join(reasons) + "."
    if len(top) > 1:
        answer += " I also found " + ", ".join(p[1]["name"] for p in top[1:]) + " in the same catalogue category."

    return {
        "answer": answer,
        "products": [
            {"product_id": p["product_id"], "name": p["name"], "category": p.get("category"),
             "price": p["price"], "stock": p["stock"], "rating": p["rating"],
             "sales": p["sales"], "score": round(score)}
            for score, p in top
        ],
        "advisor": True, "budget": budget, "available_categories": categories
    }


@app.route("/support")
def support():
    history = []
    db = DatabaseManager()
    try:
        categories = db.get_categories()
        if session.get("user_id"):
            history = [dict(row) for row in db.get_chat_history(session["user_id"], 100)]
    finally:
        db.close()
    return render_template("support.html", history=history, categories=categories or [])

@app.route("/chat-history/clear", methods=["POST"])
def clear_chat_history():
    if not session.get("user_id"):
        flash("Please log in to manage chat history.")
        return redirect(url_for("login"))
    db = DatabaseManager()
    try:
        db.clear_chat_history(session["user_id"])
    finally:
        db.close()
    flash("Chat history cleared.")
    return redirect(url_for("support"))

@app.route("/api/support", methods=["POST"])
def support_api():
    """Catalogue-grounded AI shopping assistant with persistent chat history."""
    payload = request.get_json(silent=True) or {}
    question = str(payload.get("question", "")).strip()
    if not question:
        return jsonify({"answer": "Please type a question.", "products": []})

    db = DatabaseManager()
    try:
        result = _ai_shopping_advisor(question, db)
    finally:
        db.close()

    if session.get("user_id"):
        history_db = DatabaseManager()
        try:
            history_db.save_chat_message(session["user_id"], question, result["answer"])
        finally:
            history_db.close()

    return jsonify(result)


@app.route("/api/ai-advisor", methods=["POST"])
def ai_advisor_api():
    """Dedicated endpoint for the Smart Shopping Advisor experience."""
    payload = request.get_json(silent=True) or {}
    question = str(payload.get("question", "")).strip()
    if not question:
        return jsonify({"answer": "Tell me what you want to buy.", "products": [], "advisor": True})

    db = DatabaseManager()
    try:
        result = _ai_shopping_advisor(question, db)
    finally:
        db.close()

    if session.get("user_id"):
        history_db = DatabaseManager()
        try:
            history_db.save_chat_message(session["user_id"], question, result["answer"])
        finally:
            history_db.close()

    return jsonify(result)



@app.route("/orders/<int:order_id>/return", methods=["POST"])
def request_return(order_id):
    if not login_required():
        flash("Please log in to request a return.")
        return redirect(url_for("login"))
    reason = request.form.get("reason", "").strip()
    db = DatabaseManager()
    try:
        ok, message = db.create_return_request(order_id, int(session["user_id"]), reason)
    finally:
        db.close()
    flash(message)
    return redirect(url_for("order_detail", order_id=order_id))

@app.route("/returns")
def returns():
    if not login_required():
        flash("Please log in to view your returns.")
        return redirect(url_for("login"))
    db=DatabaseManager()
    try:
        rows=db.get_user_returns(int(session["user_id"]))
    finally:
        db.close()
    return render_template("returns.html", returns=rows)

# =========================
# ADMIN SYSTEM — SMART SHOP AI
# =========================
@app.route("/admin")
def admin_dashboard():
    access = admin_required()
    if access:
        return access
    db = DatabaseManager()
    try:
        summary = db.analytics_summary()
        summary["total_orders"] = db.total_orders()
        summary["order_revenue"] = db.total_order_revenue()
        low_stock = db.low_stock_products(12, 8)
        recent_orders = db.get_all_orders(8)
        recent_users = db.get_recent_users(8)
        top_products = db.best_selling_products(6)
    finally:
        db.close()
    return render_template("admin/dashboard.html", summary=summary, low_stock=low_stock,
                           recent_orders=recent_orders, recent_users=recent_users, top_products=top_products)


@app.route("/admin/setup", methods=["GET", "POST"])
def admin_setup():
    db = DatabaseManager()
    try:
        if db.admin_exists():
            flash("An administrator account already exists. Please sign in.")
            return redirect(url_for("login"))
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")
            if len(username) < 3 or len(password) < 6:
                flash("Use a username of at least 3 characters and a password of at least 6 characters.")
            elif password != confirm:
                flash("Passwords do not match.")
            else:
                if db.create_admin(username, password):
                    flash("Administrator account created. Please sign in.")
                    return redirect(url_for("login"))
                flash("Could not create the administrator account.")
    finally:
        db.close()
    return render_template("admin/setup.html")


@app.route("/admin/products")
def admin_products():
    access = admin_required()
    if access:
        return access
    db = DatabaseManager()
    try:
        keyword = request.args.get("search", "").strip()
        category = request.args.get("category", "All").strip() or "All"
        products = db.search_and_filter(keyword, category, "featured")
        categories = db.get_categories()
    finally:
        db.close()
    return render_template("admin/products.html", products=products, categories=categories,
                           keyword=keyword, selected_category=category)


@app.route("/admin/orders")
def admin_orders():
    access = admin_required()
    if access:
        return access
    db = DatabaseManager()
    try:
        status = request.args.get("status", "All").strip() or "All"
        orders = db.get_all_orders(status=status)
    finally:
        db.close()
    return render_template("admin/orders.html", orders=orders, selected_status=status,
                           statuses=db.order_statuses())


@app.route("/admin/orders/<int:order_id>")
def admin_order_detail(order_id):
    access = admin_required()
    if access:
        return access
    db = DatabaseManager()
    try:
        order = db.get_order(order_id)
        if not order:
            return render_template("404.html"), 404
        items = db.get_order_items(order_id)
        statuses = db.order_statuses()
    finally:
        db.close()
    return render_template("admin/order_detail.html", order=order, items=items, statuses=statuses)


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
def admin_update_order_status(order_id):
    access = admin_required()
    if access:
        return access
    status = request.form.get("status", "").strip()
    db = DatabaseManager()
    try:
        if status not in db.order_statuses():
            flash("Invalid order status.")
        elif db.update_order_status(order_id, status):
            db.add_shipment_event(order_id, status, f"Order status updated to {status} by admin")
            flash(f"Order #{order_id} updated to {status}.")
        else:
            flash("Order not found.")
    finally:
        db.close()
    return redirect(url_for("admin_order_detail", order_id=order_id))


@app.route("/admin/returns")
def admin_returns():
    access = admin_required()
    if access:
        return access
    status = request.args.get("status", "All").strip() or "All"
    db=DatabaseManager()
    try:
        rows=db.get_all_returns(status)
    finally:
        db.close()
    return render_template("admin/returns.html", returns=rows, selected_status=status, statuses=["All","Requested","Approved","Rejected","Closed"])

@app.route("/admin/returns/<int:return_id>/status", methods=["POST"])
def admin_update_return(return_id):
    access = admin_required()
    if access:
        return access
    status=request.form.get("status", "Requested").strip()
    note=request.form.get("admin_note", "").strip()
    allowed={"Requested","Approved","Rejected","Closed"}
    db=DatabaseManager()
    try:
        if status not in allowed or not db.update_return_status(return_id,status,note):
            flash("Could not update the return request.")
        else:
            flash(f"Return #{return_id} updated to {status}.")
    finally:
        db.close()
    return redirect(url_for("admin_returns"))

@app.route("/admin/users")
def admin_users():
    access = admin_required()
    if access:
        return access
    db = DatabaseManager()
    try:
        users = db.get_all_users()
    finally:
        db.close()
    return render_template("admin/users.html", users=users)


@app.route("/admin/users/<int:user_id>/role", methods=["POST"])
def admin_update_user_role(user_id):
    access = admin_required()
    if access:
        return access
    role = request.form.get("role", "customer").strip()
    if role not in {"customer", "admin"}:
        flash("Invalid role.")
        return redirect(url_for("admin_users"))
    if user_id == session.get("user_id") and role != "admin":
        flash("You cannot remove administrator access from your own account.")
        return redirect(url_for("admin_users"))
    db = DatabaseManager()
    try:
        if db.update_user_role(user_id, role):
            flash("User role updated successfully.")
        else:
            flash("User not found.")
    finally:
        db.close()
    return redirect(url_for("admin_users"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Username and password are required.")
            return redirect(url_for("login"))
        db = DatabaseManager()
        try:
            user = db.login_user(username, password)
        finally:
            db.close()
        if user:
            # Preserve shopping-session data while refreshing authentication state.
            session.pop("user_id", None)
            session.pop("username", None)
            session["user_id"] = user["user_id"]
            session["username"] = user["username"]
            session["role"] = user["role"] if "role" in user.keys() else "customer"
            flash("Welcome back!")
            if session.get("role") == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("home"))
        flash("Invalid username or password.")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        interests = request.form.get("interests", "").strip()
        if not username or not password:
            flash("Username and password are required.")
            return redirect(url_for("register"))
        if len(username) < 3:
            flash("Username must be at least 3 characters long.")
            return redirect(url_for("register"))
        if len(password) < 6:
            flash("Password must be at least 6 characters long.")
            return redirect(url_for("register"))
        db = DatabaseManager()
        try:
            success = db.register_user(username, password, interests)
        finally:
            db.close()
        if success:
            flash("Account created securely. You can now sign in.")
            return redirect(url_for("login"))
        flash("That username already exists.")
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    session.pop("role", None)
    flash("You have been logged out.")
    return redirect(url_for("home"))


@app.route("/about")
def about(): return render_template("about.html")

@app.route("/contact")
def contact(): return render_template("contact.html")

@app.errorhandler(404)
def not_found(error): return render_template("404.html"), 404

@app.errorhandler(500)
def server_error(error): return render_template("500.html"), 500


if __name__ == "__main__":
    print("\n==============================================")
    print("          SMART SHOP AI")
    print("==============================================")
    print("Open: http://127.0.0.1:5000\n")
    app.run(host="127.0.0.1", port=5000, debug=True)
