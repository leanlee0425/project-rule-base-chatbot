#!/usr/bin/env python
# coding: utf-8

# In[1]:


import sqlite3
import spacy
import re
from datetime import datetime
import time, random, sys
import os

DB_FILE = os.getenv("DB_FILE", r"D:\DB Browser for SQLite\chatbot_db.db")
EMAIL_REGEX = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

# --- CONFIGURATION ---
# DB_FILE = r"D:\DB Browser for SQLite\chatbot_db.db" # Updated to your file path
# Load the small English model for SpaCy.
# You need to download it first by running: python -m spacy download en_core_web_sm
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Spacy model 'en_core_web_sm' not found.")
    print("Please run: !python -m spacy download en_core_web_sm in a Jupyter cell or")
    print("python -m spacy download en_core_web_sm in your terminal.")
    exit()



def capture_user_profile():
    """
    Ask for name and email in a single prompt like:
    'Jane Doe jane@example.com'
    Extracts the email via regex; uses the remaining text as name.
    If the email exists in DB, keeps the stored name.
    """
    while True:
        raw = input("Hi! please give me your name and email: ").strip()
        m = re.search(EMAIL_REGEX, raw)
        if not m:
            print("I couldn't find a valid email. Try again (e.g., Jane Doe jane@example.com).")
            continue

        email = m.group(0)
        # Remove the email token from the input to get the name
        name = raw.replace(email, "").strip(" ,;<>\"'")

        if not name:
            name = input("Got your email. What's your name? ").strip()
            if not name:
                print("Name can't be empty.")
                continue

        # Save to DB (insert if new, keep existing if email found)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM user_profile WHERE email = ?", (email,))
        row = cursor.fetchone()

        if row is None:
            cursor.execute(
                "INSERT INTO user_profile (name, email, created_at) VALUES (?, ?, ?)",
                (name, email, datetime.utcnow().isoformat())
            )
            conn.commit()
            user_id = cursor.lastrowid
        else:
            user_id, existing_name = row
            # Keep the existing name and ignore the newly typed one
            name = existing_name

        conn.close()
        return {"user_id": user_id, "name": name, "email": email}



# --- 1. DATABASE SETUP ---

def setup_database():
    """
    Connects to the existing database to ensure it is accessible and contains the required tables.
    This function no longer creates tables or populates data.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Check if the required tables exist to provide a helpful error message.
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='faq_db'")
        if cursor.fetchone() is None:
            print(f"Error: Table 'faq_db' not found in {DB_FILE}.")
            print("Please ensure your database has the correct table schema.")
            exit()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='faq_db_pattern'")
        if cursor.fetchone() is None:
            print(f"Error: Table 'faq_db_pattern' not found in {DB_FILE}.")
            print("Please ensure your database has the correct table schema.")
            exit()

        conn.close()
        print("Database connection successful. Using existing data.")
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        exit()


# --- 2. NLP & INTENT RECOGNITION ---

def preprocess_text(text):
    """
    Processes user input by converting to lowercase, removing punctuation,
    and lemmatizing tokens.

    Args:
        text (str): The raw user input.

    Returns:
        list: A list of lemmatized tokens.
    """
    doc = nlp(text.lower())
    lemmas = [token.lemma_ for token in doc if not token.is_punct and not token.is_space]
    return lemmas

def get_intent(user_input):
    """
    Determines the user's intent by matching their preprocessed input against
    patterns from the database. It calculates a score for each potential intent
    and returns the one with the highest score.

    Args:
        user_input (str): The raw text from the user.

    Returns:
        tuple: A tuple containing the best intent (str) and any extracted entity (like an order number).
    """

    lemmas = preprocess_text(user_input)
    lemmatized_input_str = " ".join(lemmas)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT intent, type, pattern, weight FROM faq_db_pattern")
    all_patterns = cursor.fetchall()
    conn.close()

    intent_scores = {}
    extracted_entity = None

    for intent, type, pattern, weight in all_patterns:
        if intent not in intent_scores:
            intent_scores[intent] = 0.0

        if type == 'keyword':
            # For keywords, we also lemmatize the pattern for a fair comparison
            pattern_lemmas = preprocess_text(pattern)
            # Check if all words in the pattern are in the user's input
            if all(p_lemma in lemmas for p_lemma in pattern_lemmas):
                intent_scores[intent] += weight
                # print(f"[MATCH] intent={intent}, type=keyword, pattern='{pattern}', +{weight} → total={intent_scores[intent]}")

        elif type == 'regex':
            # For regex, we match against the original (lowercased) input
            match = re.search(pattern, user_input.lower())
            if match:
                intent_scores[intent] += weight
                # print(f"[MATCH] intent={intent}, type=regex, pattern='{pattern}', +{weight} → total={intent_scores[intent]}")
                # If the regex has a capturing group, we extract it as an entity
                if match.groups():
                    extracted_entity = match.group(1)
                    # print(f"   [ENTITY] extracted → {extracted_entity}")

    # Show all final scores before picking
    # print("\n--- Final intent scores ---")
    # for intent, score in intent_scores.items():
    #     print(f"{intent}: {score}")


    # Determine the best intent
    if not any(score > 0 for score in intent_scores.values()):
        best_intent = 'fallback'
    else:
        best_intent = max(intent_scores, key=intent_scores.get)

    return best_intent, extracted_entity


def get_answer_for_intent(intent):
    """
    Retrieves the corresponding answer for a given intent from the database.

    Args:
        intent (str): The intent to find an answer for.

    Returns:
        str: The answer text.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT answer FROM faq_db WHERE intent = ?", (intent,))
    result = cursor.fetchone()
    conn.close()

    # It's good practice to have a default fallback answer in your database
    # but this handles cases where an intent might not have a matching answer.
    if result is None:
        # Plain safe fallback (do NOT call fallback_menu here)
        return "\nSorry, I couldn't understand your request. Please choose an option:"
    return result[0]


def fallback_menu():
    """
    Presents a menu when fallback is triggered.
    Returns the selected intent slug, or None after 3 invalid tries.
    """
    menu = [
        ("1) Track Your Order", "track_order"),
        ("2) Create Your Account", "create_account"),
        ("3) Return & Refund", "return_policy"),
        ("4) Product Damage", "package_lost_damaged"),
        ("5) Contact Us", "contact_customer_support"),
        ("6) Need agent support", "send_glink"),
    ]

    # print("\nSorry, I couldn't understand your request. Please choose an option:")
    for i, (label, _) in enumerate(menu, 1):
        print(f"{i}. {label}")

    attempts = 0
    while attempts < 3:
        choice = input("Enter the number of your choice (1-5): ").strip()
        try:
            idx = int(choice)
            if 1 <= idx <= len(menu):
                return menu[idx - 1][1]   # return the intent slug
        except ValueError:
            pass
        attempts += 1
        print("Invalid input. Please enter a number between 1 and 5.")

    # After 3 invalid attempts
    print("It seems you're having trouble. Please fill out this form and our team will assist you: #")
    return None

def confirm_before_end(conversation_context):
    """
    Ask user if they want to continue before ending the session.
    Returns: (updated_context, should_end: bool)
    """
    while True:
        reply = input("Bot: Is there anything else I can help you with before ending the session? (yes/no) ").strip().lower()
        if reply in ("y", "yes"):
            # reset flags but keep user for name-echo
            bot_send("Sure—how else can I help you?", min_delay=0.8, max_delay=1.2)
            return {'user': conversation_context.get('user')}, False
        elif reply in ("n", "no"):
            bot_send("Goodbye!", min_delay=0.8, max_delay=1.2)
            return conversation_context, True
        else:
            print("Bot: Please answer yes or no.")

# Accept 5+ digits as a plausible order number. Change to r'\b([A-Za-z0-9-]{5,})\b' if you use alphanumeric order codes.
ORDER_NO_RE = re.compile(r'\b(\d{5,})\b')

def ensure_order_tables():
    """Fail fast with a friendly message if order tables are missing."""
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='faq_db_orders'")
        if cur.fetchone() is None:
            print("Error: Table 'faq_db_orders' not found. Please create it or update the table name in code.")
            sys.exit(1)
        cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='faq_db_order_items'")
        if cur.fetchone() is None:
            print("Error: Table 'faq_db_order_items' not found. Please create it or update the table name in code.")
            sys.exit(1)

def find_order_number(text: str) -> str | None:
    """Pull an order number from free text."""
    m = ORDER_NO_RE.search(text)
    return m.group(1) if m else None

def fetch_open_orders_for_user(user_id: int) -> list[dict]:
    """
    Return all 'open' orders (processing / in_transit / shipped) for this user,
    newest first.
    """
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT id, customer_id, order_number, placed_at, status,
                   shipping_carrier,
                   tracking_number, eta_date
            FROM faq_db_orders
            WHERE customer_id = ?
              AND lower(status) IN ('processing','in_transit')
            ORDER BY datetime(placed_at) DESC, id DESC
        """, (user_id,))
        return [dict(r) for r in cur.fetchall()]

def fetch_order_bundle_by_id(order_id: int):
    """Fetch one order row by id and its items."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        order = cur.execute("""
            SELECT id, customer_id, order_number, placed_at, status,
                   shipping_carrier,
                   tracking_number, eta_date
            FROM faq_db_orders
            WHERE id = ?
            LIMIT 1
        """, (order_id,)).fetchone()
        if not order:
            return None, None
        items = cur.execute("""
            SELECT sku, name, qty
            FROM faq_db_order_items
            WHERE order_id = ?
            ORDER BY id
        """, (order_id,)).fetchall()
        return dict(order), [dict(i) for i in items]

def format_open_orders_menu(orders: list[dict]) -> str:
    """
    Build a numbered list the user can pick from.
    Example line: "1) #184533 — shipped (DHL, track DHLMY... , ETA Sep 04)"
    """
    if not orders:
        return "I didn’t find any orders that are still processing or in transit."

    lines = ["Here are your current orders:"]
    for idx, o in enumerate(orders, start=1):
        status = (o.get("status") or "").lower()
        carrier = o.get("shipping_carrier")
        track   = o.get("tracking_number") or "N/A"
        eta     = _fmt_date(o.get("eta_date"))
        eta_str = f", ETA {eta:%b %d}" if eta and hasattr(eta, "strftime") else ""
        extra   = []
        if status in {"in_transit", "shipped"}:
            extra.append(carrier)
            extra.append(f"track {track}")
        extra_str = f" ({', '.join([e for e in extra if e])}{eta_str})" if extra or eta_str else ""
        lines.append(f"{idx}) #{o['order_number']} — {status}{extra_str}")
    lines.append("\nPlease select which order you want to track:")
    return "\n".join(lines)


def _fmt_date(s):
    """Accept ISO8601 or plain text; return friendly date or s."""
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            from datetime import datetime as _dt
            return _dt.fromisoformat(s) if "T" in s else _dt.strptime(s, fmt)
        except Exception:
            pass
    return s  # leave as-is if unknown

def summarize_order(order: dict, items: list[dict]) -> str:
    """Human-friendly status + item summary."""
    status = (order.get("status") or "").lower()
    eta = _fmt_date(order.get("eta_date"))
    carrier = order.get("shipping_carrier") or "the courier"
    tracking = order.get("tracking_number") or "N/A"

    # Status phrasing
    if  status in {"shipped", "in_transit"}:
        eta_part = f", ETA {eta:%b %d}" if eta and hasattr(eta, "strftime") else ""
        status_line = f"in transit with {carrier} (tracking: {tracking}{eta_part})"
    elif status in {"processing", "confirmed", "paid"}:
        status_line = "being prepared for shipment, you will receive a tracking number once it ships."
    elif status in {"cancelled", "canceled"}:
        status_line = "cancelled"
    elif status in {"returned", "refunded"}:
        status_line = status
    else:
        status_line = status or "processing"

    lines = []
    for it in items[:3]:
        qty = it.get("qty") or 1
        name = it.get("name") or "Item"
        sku = it.get("sku") or ""
        sku_part = f" (SKU {sku})" if sku else ""
        lines.append(f"- {qty} × {name}{sku_part}")

    more = ""
    if len(items) > 3:
        more = f"\n… and {len(items) - 3} more item(s)."

    header = f"Order #{order['order_number']} is {status_line}."
    return header + "\n\nItems:\n" + "\n".join(lines) + more

def user_has_any_orders(user_id: int) -> bool:
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM faq_db_orders WHERE customer_id = ? LIMIT 1", (user_id,))
        return cur.fetchone() is not None

def fetch_product_by_id(pid: int) -> dict | None:
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT id, sku, name, category, price, sale_price, is_trending, is_on_sale,
                   sizes, colors, material, description, stock_qty, shipping_note, return_note
            FROM faq_db_products
            WHERE id = ?
            LIMIT 1
        """, (pid,))
        row = cur.fetchone()
        return dict(row) if row else None

def format_product_answer(p: dict, facet: str | None) -> str:
    """Return a concise answer tailored to the facet. Falls back to overview."""
    name = p.get("name") or (p.get("sku") or "this item")
    def has(field): 
        return p.get(field) not in (None, "", "N/A")

    # Price helper (handles sale price)
    def price_text() -> str | None:
        price = p.get("price")
        sale  = p.get("sale_price")
        if price is None and sale is None:
            return None
        if p.get("is_on_sale") and sale is not None and price is not None:
            return f"RM{sale:.2f} (was RM{price:.2f})"
        if sale is not None and (price is None):
            return f"RM{sale:.2f}"
        if price is not None:
            return f"RM{price:.2f}"
        return None

    if facet == "sizes" and has("sizes"):
        return f"{name} sizes available: {p['sizes']}."
    if facet == "colors" and has("colors"):
        return f"{name} color options: {p['colors']}."
    if facet == "price":
        pt = price_text()
        if pt: return f"{name} price: {pt}."
    if facet == "material" and has("material"):
        return f"{name} material: {p['material']}."
    if facet == "stock":
        qty = p.get("stock_qty")
        if isinstance(qty, int):
            return f"{name} stock: {qty} unit(s) available."
    if facet == "shipping" and has("shipping_note"):
        return f"Shipping for {name}: {p['shipping_note']}."
    if facet == "returns" and has("return_note"):
        return f"Returns for {name}: {p['return_note']}."
    if facet == "desc" and has("description"):
        return f"{name}: {p['description']}"

    # Default overview
    parts = []
    if has("sizes"):       parts.append(f"Sizes: {p['sizes']}")
    if has("colors"):      parts.append(f"Colors: {p['colors']}")
    if has("material"):    parts.append(f"Material: {p['material']}")
    pt = price_text()
    if pt:                 parts.append(f"Price: {pt}")
    if has("shipping_note"): parts.append(f"Shipping: {p['shipping_note']}")
    if has("return_note"):   parts.append(f"Returns: {p['return_note']}")
    summary = "; ".join(parts) if parts else "No extra details available."
    return f"{name} — {summary}"

# PRODUCT MENU HANDLING

PRODUCT_MENU_TEXT = (
    "What would you like to browse?\n"
    "1) Trending products\n"
    "2) On-sale products\n"
    "3) Men\n"
    "4) Women\n"
    "5) Accessories\n"
    "6) Go back to main menu\n"
    "Please key in your choice:"
)

def get_product_menu() -> str:
    return PRODUCT_MENU_TEXT

def _fetch_products(where_sql: str, params: tuple = (), limit: int = 10, offset: int = 0) -> list[dict]:
    sql = f"""
        SELECT id, sku, name, category, price, sale_price, is_trending, is_on_sale,
               sizes, colors, material, description, stock_qty, shipping_note, return_note
        FROM faq_db_products
        {where_sql}
        ORDER BY name
        LIMIT ? OFFSET ?
    """
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql, params + (limit, offset))
        return [dict(r) for r in cur.fetchall()]

def get_products_by_choice(choice: int, page: int = 1, page_size: int = 10) -> list[dict]:
    offset = (page - 1) * page_size
    if choice == 1:
        return _fetch_products("WHERE is_trending = 1", (), page_size, offset)
    if choice == 2:
        return _fetch_products("WHERE is_on_sale = 1", (), page_size, offset)
    if choice == 3:
        return _fetch_products("WHERE LOWER(category) = 'men'", (), page_size, offset)
    if choice == 4:
        return _fetch_products("WHERE LOWER(category) = 'women'", (), page_size, offset)
    if choice == 5:
        return _fetch_products("WHERE LOWER(category) = 'accessories'", (), page_size, offset)
    return []

SECTION_URLS = {
    1: "https://your.site/shop?sort=trending",
    2: "https://your.site/shop?sale=1",
    3: "https://your.site/shop/men",
    4: "https://your.site/shop/women",
    5: "https://your.site/shop/accessories",
}

def format_product_list(products: list[dict]) -> str:
    if not products:
        return "No products found in this section."
    lines = ["Here are some items:"]
    for i, p in enumerate(products, 1):
        price = p.get("price")
        sale = p.get("sale_price")
        if p.get("is_on_sale") and sale is not None and price is not None:
            price_txt = f"RM{sale:.2f} (was RM{price:.2f})"
        elif price is not None:
            price_txt = f"RM{price:.2f}"
        else:
            price_txt = "Price N/A"
        sku = f" • SKU {p['sku']}" if p.get("sku") else ""
        lines.append(f"{i}) {p['name']} — {price_txt}{sku}")
    lines.append("\nReply with a number to see details, or type 'menu' to go back.")
    return "\n".join(lines)

# Keep your existing fetch_product_by_id + format_product_answer()

def handle_product_menu_turn(user_input: str, ctx: dict) -> tuple[str, dict]:
    # ctx is your session state dict
    if ctx.get("menu_state") is None:
        ctx["menu_state"] = "root"
        return get_product_menu(), ctx

    if ctx["menu_state"] == "root":
        try:
            n = int(user_input.strip())
        except ValueError:
            return "Please enter a number 1–5.", ctx
        if n not in (1,2,3,4,5):
            return "Please enter a number 1–5.", ctx
        products = get_products_by_choice(n, page=1, page_size=10)
        ctx["menu_state"] = f"list_{n}"
        ctx["last_choice"] = n
        ctx["last_results"] = [p["id"] for p in products]  # map index → id
        return format_product_list(products), ctx

    if ctx["menu_state"].startswith("list_"):
        if user_input.strip().lower() == "menu":
            ctx["menu_state"] = "root"
            return get_product_menu(), ctx
        try:
            idx = int(user_input.strip()) - 1
        except ValueError:
            return "Please pick an item number from the list, or type 'menu' to go back.", ctx
        ids = ctx.get("last_results", [])
        if not (0 <= idx < len(ids)):
            return "That number isn’t on the list. Try again.", ctx
        pid = ids[idx]
        product = fetch_product_by_id(pid)
        if not product:
            return "Sorry, I couldn’t load that item.", ctx
        # facet handling optional; pass None to show overview
        return format_product_answer(product, facet=None), ctx

# Non-blocking main menu for chat
FALLBACK_MENU = [
    ("Track Your Order",        "track_order"),
    ("Create Your Account",     "create_account"),
    ("Return & Refund",         "return_policy"),
    ("Product Damage",          "package_lost_damaged"),
    ("Contact Us",              "contact_customer_support"),
    ("Need agent support",      "send_glink"),
]

def fallback_menu_text() -> str:
    lines = ["Main menu:"]
    for i, (label, _) in enumerate(FALLBACK_MENU, 1):
        lines.append(f"{i}) {label}")
    lines.append("Please enter 1–6:")
    return "\n".join(lines)

def fallback_menu_resolve(n: int) -> str | None:
    if 1 <= n <= len(FALLBACK_MENU):
        return FALLBACK_MENU[n-1][1]  # return intent slug
    return None

# --- 3. DECISION TREE (CONVERSATIONAL FLOW) & MAIN LOOP ---

def chatbot_response(user_input, conversation_context, interactive: bool = True):
    def _preserve_user(ctx):
        return {'user': ctx.get('user')}

    # --- A0) waiting: choose product section (1–5) ---
    if conversation_context.get('waiting_for') == 'choose_product_section':
        choice_raw = user_input.strip().lower()
        if choice_raw in ("menu", "back"):
            ctx = _preserve_user(conversation_context)
            return (PRODUCT_MENU_TEXT, ctx)

        if not choice_raw.isdigit():
            return ("Please enter a number 1–5 (or type 'menu' to see options).",
                    conversation_context)

        choice = int(choice_raw)

        if choice == 6:
            ctx = _preserve_user(conversation_context)
            ctx['waiting_for'] = 'fallback_menu_choice'   # expect a number next
            return (fallback_menu_text(), ctx)    

        # Build WHERE by choice
        if choice == 1:
            where_sql, params = "WHERE is_trending = 1", ()
        elif choice == 2:
            where_sql, params = "WHERE is_on_sale = 1", ()
        elif choice == 3:
            where_sql, params = "WHERE LOWER(category) = 'men'", ()
        elif choice == 4:
            where_sql, params = "WHERE LOWER(category) = 'women'", ()
        else:  # 5
            where_sql, params = "WHERE LOWER(category) = 'accessories'", ()

        # Query products for this section (first page, up to 10)
        import sqlite3
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(f"""
                SELECT id, sku, name, category, price, sale_price, is_trending, is_on_sale,
                    sizes, colors, material, description, stock_qty, shipping_note, return_note
                FROM faq_db_products
                {where_sql}
                ORDER BY name
                LIMIT 10
            """, params)
            products = [dict(r) for r in cur.fetchall()]

        if not products:
            ctx = _preserve_user(conversation_context)
            ctx['waiting_for'] = 'choose_product_section'
            return ("No products found in this section. Type 1–5 to pick another section, or 'menu' to see options.",
                    ctx)

        # Build the numbered list
        lines = ["Here are some items:"]
        for i, p in enumerate(products, 1):
            sku = f" • SKU {p['sku']}" if p.get('sku') else ""
            if p.get('is_on_sale') and p.get('sale_price') is not None and p.get('price') is not None:
                price_txt = f"RM{p['sale_price']:.2f} (was RM{p['price']:.2f})"
            elif p.get('price') is not None:
                price_txt = f"RM{p['price']:.2f}"
            else:
                price_txt = "Price N/A"
            lines.append(f"{i}) {p['name']} — {price_txt}{sku}")
        lines.append("\nReply with an item number to see details, or type 'menu' to go back.")
        sec_url = SECTION_URLS.get(choice, "https://your.site/shop")
        lines.append(f"More products: {sec_url}")
        menu_text = "\n".join(lines)

        ctx = _preserve_user(conversation_context)
        ctx['waiting_for'] = 'choose_product_item'
        ctx['product_choice_ids'] = [p['id'] for p in products]
        return (menu_text, ctx)

    # --- A1) waiting: choose a specific product item ---
    if conversation_context.get('waiting_for') == 'choose_product_item':
        choice_raw = user_input.strip().lower()
        if choice_raw in ("menu", "back"):
            ctx = _preserve_user(conversation_context)
            ctx['waiting_for'] = 'choose_product_section'
            return (PRODUCT_MENU_TEXT, ctx)
        if not choice_raw.isdigit():
            return ("Please enter the item number from the list, or type 'menu' to go back.",
                    conversation_context)
        idx = int(choice_raw)
        ids = conversation_context.get('product_choice_ids', [])
        if not ids or not (1 <= idx <= len(ids)):
            return ("That number isn’t in the list. Try again, or type 'menu' to go back.",
                    conversation_context)

        pid = ids[idx - 1]
        product = fetch_product_by_id(pid)
        if not product:
            ctx = _preserve_user(conversation_context)
            return ("Sorry, I couldn’t load that item. Type 'menu' to pick again.",
                    ctx)

        # Clear waiting state after showing details (or keep it if you want further actions)
        ctx = _preserve_user(conversation_context)
        # Optionally keep the list for quick back navigation:
        # ctx['waiting_for'] = 'choose_product_item'
        return (format_product_answer(product, facet=None), ctx)

    # --- AX) waiting: choose from main (fallback) menu ---
    if conversation_context.get('waiting_for') == 'fallback_menu_choice':
        choice_raw = user_input.strip().lower()
        if choice_raw in ("menu", "back"):
            ctx = _preserve_user(conversation_context)
            return (fallback_menu_text(), ctx)

        if not choice_raw.isdigit():
            return ("Please enter a valid number 1–6 from the main menu.", conversation_context)

        n = int(choice_raw)
        slug = fallback_menu_resolve(n)
        if not slug:
            ctx = _preserve_user(conversation_context)
            ctx['waiting_for'] = 'fallback_menu_choice'
            return ("Please enter a valid number 1–6 from the main menu.", ctx)

        # Clear the menu state
        ctx = _preserve_user(conversation_context)
        ctx.pop('waiting_for', None)

        # Route by slug
        if slug == "track_order":
            user = conversation_context.get('user') or {}
            user_id = user.get('user_id')
            if not user_id:
                return ("I need to know who you are first. Please restart and provide your name + email.", ctx)
            open_orders = fetch_open_orders_for_user(user_id)
            if not open_orders:
                msg = ("I didn’t find any processing/in-transit orders. "
                    "You can type an order number to search for a specific order.")
                return (msg, ctx)
            menu_text = format_open_orders_menu(open_orders)
            ctx['waiting_for'] = 'choose_order_to_track'
            ctx['order_choice_ids'] = [o['id'] for o in open_orders]
            return (menu_text, ctx)

        if slug == "create_account":
            return (get_answer_for_intent('create_account'), ctx)

        if slug == "return_policy":
            return (get_answer_for_intent('return_policy'), ctx)

        if slug == "package_lost_damaged":
            return (get_answer_for_intent('package_lost_damaged'), ctx)

        if slug == "contact_customer_support":
            SUPPORT_FORM_URL = "https://example.com/support-form"
            return (f"You can reach us here: {SUPPORT_FORM_URL}", ctx)

        if slug == "send_glink":
            SUPPORT_FORM_URL = "https://example.com/support-form"
            ctx['end_session'] = True
            return (f"I'm sorry I can’t resolve that here. Please fill out this form and our support team will contact you: {SUPPORT_FORM_URL}", ctx)

        # default guard (shouldn't hit)
        return ("Okay—back to the main menu. How can I help you?", ctx)


    # --- A) waiting choose order to track ---
    if conversation_context.get('waiting_for') == 'choose_order_to_track':
        # Expecting a number
        choice_raw = user_input.strip()
        if not choice_raw.isdigit():
            return ("Please enter a valid number from the list (e.g., 1 or 2).",
                    conversation_context)
        idx = int(choice_raw)
        order_ids: list[int] = conversation_context.get('order_choice_ids', [])
        if not order_ids or not (1 <= idx <= len(order_ids)):
            return ("That number isn’t in the list. Please try again.",
                    conversation_context)

        selected_id = order_ids[idx - 1]
        order, items = fetch_order_bundle_by_id(selected_id)
        if not order:
            # very unlikely, but handle gracefully
            ctx = _preserve_user(conversation_context)
            return ("Sorry, I couldn’t retrieve that order just now. Please try another one.",
                    ctx)

        # clear waiting state
        ctx = _preserve_user(conversation_context)
        return (summarize_order(order, items), ctx)

    # (keep your existing "waiting_for == 'order_number'" block here if you still use it anywhere else)

    # --- B) normal intent detection ---
    intent, entity = get_intent(user_input)

    # Early keyword router so typos like "woud" still work
    txt = user_input.lower()
    if conversation_context.get('waiting_for') is None and any(
        k in txt for k in ("product", "products", "browse products", "shop", "catalog")
    ):
        ctx = _preserve_user(conversation_context)
        ctx['waiting_for'] = 'choose_product_section'
        return (PRODUCT_MENU_TEXT, ctx)

    # Entry point for product browsing
    if intent in ('product', 'browse_products', 'show_products'):
        ctx = _preserve_user(conversation_context)
        ctx['waiting_for'] = 'choose_product_section'
        return (PRODUCT_MENU_TEXT, ctx)

    # --- C) advanced track_order branch ---
    if intent == 'track_order':
        # 1) identify user
        user = conversation_context.get('user') or {}
        user_id = user.get('user_id')
        if not user_id:
            return ("I need to know who you are first. Please restart and provide your name + email.",
                    _preserve_user(conversation_context))

        # 2) fetch open orders (processing / shipped / in_transit)
        open_orders = fetch_open_orders_for_user(user_id)

        # 3) if any open orders → show numbered menu and wait for choice
        if open_orders:
            menu_text = format_open_orders_menu(open_orders)
            ctx = _preserve_user(conversation_context)
            ctx['waiting_for'] = 'choose_order_to_track'
            ctx['order_choice_ids'] = [o['id'] for o in open_orders]
            return (menu_text, ctx)

        # 4) no open orders → check if this user has any orders at all
        if not user_has_any_orders(user_id):
            return ("You don't have any orders with us yet. Please create an account and place your first order. Is there anything else I can help you with?",
                    _preserve_user(conversation_context))

        # 5) user has past orders but nothing active
        return ("You currently have no processing or in-transit orders.",
                _preserve_user(conversation_context))


    # --- D) other intents / fallbacks (keep your existing logic) ---
    if intent == 'fallback':
        # Non-interactive (API mode): show menu text and wait for a choice on next turn
        if not interactive:
            ctx = _preserve_user(conversation_context)
            ctx['waiting_for'] = 'fallback_menu_choice'
            # Return the fallback menu prompt (non-blocking)
            return (fallback_menu_text(), ctx)

        # Interactive (terminal mode): keep your original behavior
        print(get_answer_for_intent('fallback'))
        selected_intent = fallback_menu()
        if selected_intent is None:
            response = "No problem. Ending the session. Have a great day!"
            ctx = _preserve_user(conversation_context); ctx['end_session'] = True
            return response, ctx
        if selected_intent == 'track_order':
            user = conversation_context.get('user') or {}
            user_id = user.get('user_id')
            open_orders = fetch_open_orders_for_user(user_id)
            if not open_orders:
                msg = ("I didn’t find any processing/in-transit orders. "
                       "You can type an order number to search for a specific order.")
                return (msg, _preserve_user(conversation_context))
            menu_text = format_open_orders_menu(open_orders)
            ctx = _preserve_user(conversation_context)
            ctx['waiting_for'] = 'choose_order_to_track'
            ctx['order_choice_ids'] = [o['id'] for o in open_orders]
            return (menu_text, ctx)
        if selected_intent == 'send_glink':
            SUPPORT_FORM_URL = "https://example.com/support-form"
            response = f"I'm sorry I can’t resolve that here. Please fill out this form and our support team will contact you: {SUPPORT_FORM_URL}"
            ctx = _preserve_user(conversation_context); ctx['end_session'] = True
            return response, ctx
        return get_answer_for_intent(selected_intent), _preserve_user(conversation_context)


    if intent == 'goodbye':
        response = get_answer_for_intent('goodbye')
        ctx = _preserve_user(conversation_context); ctx['end_session'] = True
        return response, ctx

    return get_answer_for_intent(intent), _preserve_user(conversation_context)



def bot_send(response, min_delay=3, max_delay=5):
    """Simulate bot thinking/typing, then print the response."""
    delay = random.uniform(min_delay, max_delay)

    # typing indicator
    msg = "Bot is typing..."
    sys.stdout.write(msg)
    sys.stdout.flush()
    t0 = time.time()
    dot = 0
    while time.time() - t0 < delay:
        sys.stdout.write("." * ((dot % 3) + 1) + "\r" + msg + "   \r")
        sys.stdout.flush()
        time.sleep(0.4)
        dot += 1

    # clear the line and print the actual bot message
    sys.stdout.write(" " * (len(msg) + 3) + "\r")
    sys.stdout.flush()
    print(f"Bot: {response}", flush=True)


def main():

        # One-line, anchored regex so we only trigger when the whole input is an end cue.
    END_TRIGGER_RE = re.compile(
        r"^\s*(?:"
        r"quit|exit|bye|goodbye|"
        r"ok(?:ay)?|can|done|got it|"
        r"no more|nothing else|that(?:'|’)?s all|all good|i(?:'|’)?m good|im good|"
        r"no thanks|no thank you|thanks"
        r")\s*[.!?]*\s*$",
        re.IGNORECASE
    )

    """Main function to run the chatbot."""
    setup_database()
    # ensure_user_table()
    ensure_order_tables()

    # 🔹 Single-shot capture
    user = capture_user_profile()

    print("\n--- E-commerce Chatbot ---")
    print("Bot: Hello! How can I assist you today?")

    conversation_context = {"user": user}


    while True:
        user_input = input("You: ")
        print(f"You: {user_input}", flush=True)

        # 🔹 If user typed quit, confirm before ending
                # 🔹 Treat many phrases as “I’m done”
        if END_TRIGGER_RE.match(user_input):
            # Confirm before actually ending
            conversation_context, should_end = confirm_before_end(conversation_context)
            if should_end:
                break
            else:
                # user wants to continue → skip intent this turn
                continue

        # Normal turn
        response, conversation_context = chatbot_response(user_input, conversation_context)
        bot_send(response, min_delay=3, max_delay=5)

        # 🔹 If any branch set end_session, confirm before ending
        if conversation_context.get('end_session'):
            conversation_context, should_end = confirm_before_end(conversation_context)
            if should_end:
                break
            else:
                # user wants to continue → keep chatting
                continue

def generate_reply_api(user_input: str, conversation_context: dict | None = None) -> tuple[str, dict]:
    """
    Public entry point for FastAPI.
    - user_input: the user's message
    - conversation_context: a dict you keep on the frontend between turns
    Returns: (reply_text, new_context_dict)
    """
    if conversation_context is None:
        conversation_context = {}

    # IMPORTANT: non-interactive mode for API
    reply, new_ctx = chatbot_response(user_input, conversation_context, interactive=False)
    return reply, new_ctx


if __name__ == "__main__":
    main()

