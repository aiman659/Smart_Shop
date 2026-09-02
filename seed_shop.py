from __future__ import annotations

import html
import random
from pathlib import Path

from database.database import DatabaseManager

BASE_DIR = Path(__file__).resolve().parent
IMAGE_DIR = BASE_DIR / "static" / "images"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

CATEGORIES = {"Men's Shirts": ['Classic Oxford Shirt', 'Premium Casual Shirt', 'Slim Fit Formal Shirt', 'Cotton Check Shirt'], "Women's Shirts": ["Elegant Women's Shirt", 'Soft Cotton Blouse', 'Classic Button Shirt', 'Relaxed Fit Shirt'], 'T-Shirts': ['Essential Cotton T-Shirt', 'Premium Graphic T-Shirt', 'Classic Crew Neck T-Shirt', 'Oversized Casual T-Shirt'], 'Jeans': ['Classic Blue Jeans', 'Slim Fit Denim Jeans', 'Straight Leg Jeans', 'Dark Wash Jeans'], 'Trousers': ['Modern Formal Trousers', 'Slim Fit Trousers', 'Classic Cotton Trousers', 'Comfort Stretch Trousers'], 'Shorts': ['Casual Cotton Shorts', 'Denim Shorts', 'Summer Comfort Shorts', 'Sport Style Shorts'], 'Dresses': ['Elegant Summer Dress', 'Classic Midi Dress', 'Floral Casual Dress', 'Evening Style Dress'], 'Skirts': ['Classic A-Line Skirt', 'Pleated Fashion Skirt', 'Denim Mini Skirt', 'Elegant Midi Skirt'], 'Jackets': ['Classic Denim Jacket', 'Modern Casual Jacket', 'Lightweight Utility Jacket', 'Premium Winter Jacket'], 'Hoodies': ['Classic Cotton Hoodie', 'Premium Fleece Hoodie', 'Oversized Street Hoodie', 'Everyday Comfort Hoodie'], 'Sweaters': ['Classic Knit Sweater', 'Soft Winter Sweater', 'Premium Crew Sweater', 'Casual Ribbed Sweater'], 'Shoes': ['Classic Casual Shoes', 'Everyday Walking Shoes', 'Modern Lifestyle Shoes', 'Smart Formal Shoes'], 'Sneakers': ['Classic White Sneakers', 'Performance Running Sneakers', 'Streetwear Sneakers', 'Lightweight Training Sneakers'], 'Sandals': ['Everyday Comfort Sandals', 'Minimal Slide Sandals', 'Summer Strap Sandals', 'Soft Walking Sandals'], 'Scarves': ['Soft Winter Scarf', 'Classic Cotton Scarf', 'Elegant Fashion Scarf', 'Lightweight Casual Scarf'], 'Hats & Caps': ['Classic Baseball Cap', 'Premium Cotton Cap', 'Everyday Bucket Hat', 'Classic Winter Beanie'], 'Bags': ['Everyday Shoulder Bag', 'Classic Travel Backpack', 'Premium Tote Bag', 'Compact Crossbody Bag'], 'Belts & Accessories': ['Classic Leather Belt', 'Minimal Canvas Belt', 'Everyday Sunglasses', 'Premium Fashion Wallet']}
BRANDS = ['UrbanEdge', 'StyleCraft', 'NovaWear', 'TrendLine', 'ModeVista', 'EverStyle', 'UrbanPeak', 'PrimeWear', 'StreetAura', 'ClassicCo', 'LuxeLane', 'VibeWear']
SUPPLIERS = ['FashionHub Supply', 'Urban Wholesale', 'StyleSource', 'Prime Fashion Supply', 'Global Wear Distribution', 'Modern Apparel Supply', 'Metro Style Traders']
PALETTE = {"Men's Shirts": '#2563eb', "Women's Shirts": '#db2777', 'T-Shirts': '#7c3aed', 'Jeans': '#1d4ed8', 'Trousers': '#0f766e', 'Shorts': '#ea580c', 'Dresses': '#be185d', 'Skirts': '#9333ea', 'Jackets': '#475569', 'Hoodies': '#4f46e5', 'Sweaters': '#0891b2', 'Shoes': '#16a34a', 'Sneakers': '#0ea5e9', 'Sandals': '#f59e0b', 'Scarves': '#c026d3', 'Hats & Caps': '#e11d48', 'Bags': '#7c2d12', 'Belts & Accessories': '#334155'}

PRICE_RANGES = {
    "Dresses": (29.99, 79.99), "Jackets": (39.99, 99.99),
    "Shoes": (34.99, 89.99), "Sneakers": (39.99, 94.99),
    "Bags": (24.99, 74.99), "Belts & Accessories": (12.99, 49.99)
}
DEFAULT_RANGE = (14.99, 59.99)

ICONS = {
    "Men's Shirts":"👔","Women's Shirts":"👚","T-Shirts":"👕","Jeans":"👖","Trousers":"👖",
    "Shorts":"🩳","Dresses":"👗","Skirts":"👗","Jackets":"🧥","Hoodies":"🧥","Sweaters":"🧶",
    "Shoes":"👞","Sneakers":"👟","Sandals":"🩴","Scarves":"🧣","Hats & Caps":"🧢","Bags":"👜",
    "Belts & Accessories":"🕶️"
}

def make_svg(path: Path, title: str, category: str, color: str, icon: str):
    title_safe = html.escape(title)
    category_safe = html.escape(category)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="900" height="700" viewBox="0 0 900 700">
<defs>
 <linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{color}"/><stop offset="100%" stop-color="#111827"/></linearGradient>
 <filter id="shadow"><feDropShadow dx="0" dy="18" stdDeviation="22" flood-opacity=".22"/></filter>
</defs>
<rect width="900" height="700" fill="#f8fafc"/>
<circle cx="120" cy="110" r="120" fill="{color}" opacity=".10"/><circle cx="790" cy="610" r="190" fill="{color}" opacity=".10"/>
<rect x="90" y="85" width="720" height="530" rx="55" fill="url(#g)" filter="url(#shadow)"/>
<circle cx="450" cy="320" r="165" fill="white" opacity=".13"/>
<text x="450" y="365" text-anchor="middle" font-family="Segoe UI,Arial" font-size="150">{icon}</text>
<rect x="165" y="505" width="570" height="1" fill="white" opacity=".35"/>
<text x="450" y="555" text-anchor="middle" font-family="Segoe UI,Arial" font-size="28" font-weight="700" fill="white">{title_safe}</text>
<text x="450" y="592" text-anchor="middle" font-family="Segoe UI,Arial" font-size="19" fill="#dbeafe">{category_safe}</text>
</svg>"""
    path.write_text(svg, encoding="utf-8")

def seed_catalogue():
    rng = random.Random(20260831)
    db = DatabaseManager()
    try:
        db.clear_products()
        for image in IMAGE_DIR.glob("product_*.svg"):
            image.unlink(missing_ok=True)
        product_number = 0
        for category, product_names in CATEGORIES.items():
            low, high = PRICE_RANGES.get(category, DEFAULT_RANGE)
            for name in product_names:
                product_number += 1
                brand = rng.choice(BRANDS)
                supplier = rng.choice(SUPPLIERS)
                price = round(rng.uniform(low, high), 2)
                stock = rng.randint(10, 85)
                rating = round(rng.uniform(4.0, 5.0), 1)
                sales = rng.randint(35, 420)
                description = (
                    f"{name} by {brand} combines a polished look with practical everyday comfort. "
                    f"Designed for modern shoppers, this {category.lower()} item is easy to style, "
                    f"versatile across occasions and presented with reliable quality and value."
                )
                image_name = f"product_{product_number}.svg"
                make_svg(IMAGE_DIR / image_name, name, category, PALETTE[category], ICONS[category])
                db.add_product(name=name, category=category, brand=brand, price=price,
                               stock=stock, rating=rating, sales=sales, supplier=supplier,
                               links="", content=description, description=description, image=image_name)
        print(f"Created {len(CATEGORIES)} categories and {product_number} products.")
        print(f"Images created: {product_number}")
        print(f"Database: {db.db_path}")
    finally:
        db.close()

def main():
    seed_catalogue()


if __name__ == "__main__":
    main()
