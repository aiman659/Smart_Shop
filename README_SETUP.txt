SMART SHOP AI - PROFESSIONAL SYNCHRONIZED PACKAGE

This package was built from the user's uploaded project and keeps the existing Flask + SQLite architecture.

IMPORTANT
1. Back up your current web folder first.
2. Overlay this new web folder onto your existing web folder.
3. The included smart_shop.db is a copy of the uploaded database (72 products / 18 categories / 3700 stock units).
4. If your local database contains newer changes than the uploaded ZIP, preserve your local web\database\smart_shop.db before copying.
5. Run RUN_SMART_SHOP.bat, or from PowerShell inside web: python app.py
6. Open http://127.0.0.1:5000 and press Ctrl+F5 once after replacement.

ABSTRACT ALIGNMENT
The Support Center adds a lightweight customer-support assistant for product information, order tracking demo guidance, shipping, payment questions, returns and refunds. It is intentionally a simple FAQ/intention-based demo; the current database does not include real orders or payment processing.


IMPORTANT RUNTIME FIX
---------------------
This synchronized package explicitly registers the AI score and wishlist helpers as Jinja globals so imported product-card macros work correctly. No database schema change is required for this fix.

RUN
---
1. Open this web folder in PowerShell.
2. Run: python app.py
3. Open: http://127.0.0.1:5000/
Or double-click RUN_SMART_SHOP.bat.
