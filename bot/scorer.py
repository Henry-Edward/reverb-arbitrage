"""
Deal Scorer
Evaluates a listing for profitability and quality signals.
Returns a structured result dict or None if the deal doesn't pass.
"""

# ── Keyword lists ────────────────────────────────────────────────────────────
RED_FLAG_KEYWORDS = [
    "as-is", "as is", "for parts", "not working", "broken", "untested",
    "needs repair", "needs work", "damaged", "cracked", "missing",
    "faulty", "dead", "no power", "won't turn on", "spares or repair",
    "sold as is", "unknown condition", "water damage", "flood",
]

GREEN_FLAG_KEYWORDS = [
    "original box", "mint condition", "barely used", "studio kept",
    "studio use only", "like new", "only used once", "never gigged",
    "never gigged", "never left the studio", "comes with case",
    "full kit", "complete set", "original packaging", "low hours",
]

# Reverb fee structure (as of 2025)
REVERB_SELLING_FEE_PCT = 0.05       # 5%
PAYMENT_PROCESSING_PCT = 0.0319     # 3.19%
PAYMENT_PROCESSING_FLAT = 0.49      # $0.49


def calculate_profit(buy_price: float, sell_price: float, shipping_cost: float = 0.0) -> dict:
    """Calculate realistic profit after all fees."""
    reverb_fee = sell_price * REVERB_SELLING_FEE_PCT
    payment_fee = (sell_price * PAYMENT_PROCESSING_PCT) + PAYMENT_PROCESSING_FLAT
    total_fees = reverb_fee + payment_fee
    net_revenue = sell_price - total_fees
    profit = net_revenue - buy_price - shipping_cost

    return {
        "buy_price": buy_price,
        "sell_price": sell_price,
        "reverb_fee": round(reverb_fee, 2),
        "payment_fee": round(payment_fee, 2),
        "total_fees": round(total_fees, 2),
        "shipping_cost": shipping_cost,
        "net_revenue": round(net_revenue, 2),
        "profit": round(profit, 2),
        "profit_pct": round((profit / buy_price) * 100, 1) if buy_price > 0 else 0,
        "roi_pct": round((profit / buy_price) * 100, 1) if buy_price > 0 else 0,
    }


def scan_keywords(text: str) -> dict:
    """Scan title/description for red and green flag keywords."""
    text_lower = text.lower()
    red_flags = [kw for kw in RED_FLAG_KEYWORDS if kw in text_lower]
    green_flags = [kw for kw in GREEN_FLAG_KEYWORDS if kw in text_lower]
    return {"red_flags": red_flags, "green_flags": green_flags}


def get_deal_grade(profit: float, profit_pct: float, red_flags: list, green_flags: list) -> str:
    """Assign a letter grade to the deal."""
    if red_flags:
        return "D"  # Always downgrade if red flags present
    base_score = 0
    if profit >= 50:
        base_score += 3
    elif profit >= 25:
        base_score += 2
    elif profit >= 10:
        base_score += 1

    if profit_pct >= 40:
        base_score += 2
    elif profit_pct >= 25:
        base_score += 1

    if green_flags:
        base_score += 1

    if base_score >= 5:
        return "A"
    elif base_score >= 3:
        return "B"
    elif base_score >= 1:
        return "C"
    else:
        return "D"


def estimate_shipping(listing: dict) -> float:
    """Estimate shipping cost we'd pay as buyer."""
    shipping = listing.get("shipping", {})
    if shipping.get("freeExpeditedShipping"):
        return 0.0
    prices = shipping.get("shippingPrices", [])
    if prices:
        # Take the first (usually domestic) rate
        rate = prices[0].get("rate", {}).get("amountCents", 0)
        return rate / 100
    return 8.0  # Conservative estimate if unknown


def score_listing(listing: dict, buy_price: float, market_price: float,
                  min_profit: float, config: dict) -> dict | None:
    """
    Full evaluation of a listing. Returns deal dict or None.
    """
    title = listing.get("title", "")
    keywords = scan_keywords(title)

    # Hard skip on red flags if configured
    if keywords["red_flags"] and config.get("skip_red_flags", True):
        return None

    # Estimate what we'd pay in shipping
    buyer_shipping = estimate_shipping(listing)

    # We sell at market middle (conservative target)
    # Use market_price as our target sell price
    financials = calculate_profit(
        buy_price=buy_price,
        sell_price=market_price,
        shipping_cost=buyer_shipping,
    )

    if financials["profit"] < min_profit:
        return None

    grade = get_deal_grade(
        profit=financials["profit"],
        profit_pct=financials["profit_pct"],
        red_flags=keywords["red_flags"],
        green_flags=keywords["green_flags"],
    )

    # Skip D-grade deals
    if grade == "D":
        return None

    # Build the URL
    slug = listing.get("slug", "")
    listing_url = f"https://reverb.com/item/{slug}"

    # Get image
    images = listing.get("images", [])
    image_url = images[0]["source"] if images else None

    condition = listing.get("condition", {}).get("displayName", "Unknown")
    shop = listing.get("shop", {})
    location = shop.get("address", {}).get("displayLocation", "Unknown")

    return {
        "id": listing.get("id"),
        "title": title,
        "url": listing_url,
        "image_url": image_url,
        "condition": condition,
        "shop_name": shop.get("name", ""),
        "location": location,
        "offers_enabled": listing.get("isBuyerOfferEligible") or listing.get("offersEnabled"),
        "free_shipping": listing.get("shipping", {}).get("freeExpeditedShipping", False),
        "financials": financials,
        "market_price": market_price,
        "grade": grade,
        "green_flags": keywords["green_flags"],
        "red_flags": keywords["red_flags"],
        "scanned_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
