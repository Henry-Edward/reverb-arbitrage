"""
Notifier Module
Sends deal alerts via ntfy.sh with rich formatting.
"""

import requests


def send_notification(deal: dict, config: dict):
    """Send a deal alert to ntfy.sh."""
    ntfy_topic = config.get("ntfy_topic")
    if not ntfy_topic:
        print(f"  [ALERT] No ntfy_topic configured. Deal found: {deal['title']}")
        _print_deal(deal)
        return

    financials = deal["financials"]
    grade = deal["grade"]
    grade_emoji = {"A": "🔥", "B": "✅", "C": "💡", "D": "⚠️"}.get(grade, "📦")

    # Title line
    title = f"{grade_emoji} [{grade}] ${financials['buy_price']:.0f} → +${financials['profit']:.0f} profit"

    # Body
    lines = [
        deal["title"],
        "",
        f"💰 Buy:    ${financials['buy_price']:.2f}",
        f"📈 Market: ${deal['market_price']:.2f}",
        f"💵 Profit: ${financials['profit']:.2f} ({financials['profit_pct']:.0f}% ROI)",
        f"🏪 {deal['shop_name']} — {deal['location']}",
        f"📦 Condition: {deal['condition']}",
    ]

    if deal.get("free_shipping"):
        lines.append("🚚 Free Shipping")
    if deal.get("offers_enabled"):
        lines.append("🤝 Accepts Offers (could buy lower!)")
    if deal.get("green_flags"):
        lines.append(f"✨ {', '.join(deal['green_flags'][:2])}")

    lines += ["", f"🔗 {deal['url']}"]

    body = "\n".join(lines)

    # Priority: A=5 (urgent), B=4 (high), C=3 (default)
    priority_map = {"A": 5, "B": 4, "C": 3}
    priority = priority_map.get(grade, 3)

    tags = ["moneybag"]
    if grade == "A":
        tags += ["rotating_light", "fire"]
    elif grade == "B":
        tags.append("white_check_mark")

    headers = {
        "Title": title,
        "Priority": str(priority),
        "Tags": ",".join(tags),
        "Click": deal["url"],
    }

    if deal.get("image_url"):
        headers["Attach"] = deal["image_url"]

    ntfy_url = f"https://ntfy.sh/{ntfy_topic}"

    try:
        resp = requests.post(
            ntfy_url,
            data=body.encode("utf-8"),
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        print(f"  [SENT] Grade {grade} deal: {deal['title'][:60]} (+${financials['profit']:.2f})")
    except Exception as e:
        print(f"  [ERROR] Failed to send notification: {e}")
        _print_deal(deal)


def _print_deal(deal: dict):
    """Fallback: print deal to console."""
    f = deal["financials"]
    print(f"""
  ┌─ {deal['grade']} DEAL ────────────────────────────────
  │ {deal['title'][:65]}
  │ Buy: ${f['buy_price']:.2f}  Market: ${deal['market_price']:.2f}  Profit: ${f['profit']:.2f}
  │ ROI: {f['profit_pct']:.0f}%  Fees: ${f['total_fees']:.2f}
  │ {deal['url']}
  └────────────────────────────────────────────────────
""")
