"""
Reverb Arbitrage Bot - Scanner
Polls Reverb for new listings and fires alerts for profitable deals.
"""

import json
import os
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from config_loader import load_config
from scorer import score_listing
from notifier import send_notification
from price_guide import get_price_estimate

# ── Paths ────────────────────────────────────────────────────────────────────
SEEN_FILE = Path(__file__).parent / "seen_listings.json"

# ── Reverb GraphQL query (extracted from live traffic) ───────────────────────
GQL_SEARCH = """
query Core_Marketplace_CombinedMarketplaceSearch(
  $inputListings: Input_reverb_search_ListingsSearchRequest
  $shouldntLoadBumps: Boolean!
  $shouldntLoadSuggestions: Boolean!
  $usingListView: Boolean!
  $signalGroups: [reverb_signals_Signal_Group]
  $useSignalSystem: Boolean!
) {
  listingsSearch(input: $inputListings) {
    total
    offset
    limit
    listings {
      _id
      id
      title
      slug
      make
      model
      bumped
      publishedAt { seconds }
      condition { displayName conditionSlug conditionUuid }
      pricing {
        buyerPrice { display amount amountCents currency }
        originalPrice { display }
        typicalNewPriceDisplay { amountDisplay }
      }
      priceRecommendation {
        priceMiddle { amountCents currency }
      }
      images(input: {transform: "card_square", count: 1, scope: "photos", type: "Product"}) {
        source
      }
      shipping {
        freeExpeditedShipping
        localPickupOnly
        shippingPrices {
          shippingMethod
          rate { amount amountCents display }
        }
      }
      shop {
        name
        address { locality region countryCode displayLocation }
        returnPolicy { usedReturnWindowDays newReturnWindowDays }
      }
      offersEnabled
      isBuyerOfferEligible
      inventory
      csp { id slug }
    }
  }
}
"""

GQL_ENDPOINT = "https://gql.reverb.com/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "x-reverb-app": "REVERB",
    "Accept": "*/*",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}


def load_seen() -> set:
    if SEEN_FILE.exists():
        try:
            data = json.loads(SEEN_FILE.read_text())
            return set(data.get("ids", []))
        except Exception:
            return set()
    return set()


def save_seen(seen: set):
    # Keep only the last 10,000 IDs to prevent unbounded growth
    ids = list(seen)[-10000:]
    SEEN_FILE.write_text(json.dumps({"ids": ids, "updated": datetime.now().isoformat()}))


def fetch_listings(query: str, limit: int = 45, condition_slugs: list = None) -> list:
    condition_slugs = condition_slugs or []
    body = {
        "operationName": "Core_Marketplace_CombinedMarketplaceSearch",
        "variables": {
            "inputListings": {
                "query": query,
                "categorySlugs": [],
                "brandSlugs": [],
                "conditionSlugs": condition_slugs,
                "shippingRegionCodes": [],
                "itemState": [],
                "itemCity": [],
                "curatedSetSlugs": [],
                "saleSlugs": [],
                "withProximityFilter": {"proximity": False},
                "boostedItemRegionCode": "US",
                "useExperimentalRecall": True,
                "traitValues": [],
                "excludeCategoryUuids": [],
                "excludeBrandSlugs": [],
                "likelihoodToSellExperimentGroup": 3,
                "countryOfOrigin": [],
                "contexts": ["INITIAL_QUERY"],
                "autodirects": "IMPROVED_DATA",
                "multiClientExperiments": [{"name": "spell_check_autocorrect", "group": "1"}],
                "canonicalFinishes": [],
                "skipAutocorrect": False,
                "limit": limit,
                "offset": 0,
                "fallbackToOr": False,
                "collapsible": None,
                "sort": "PUBLISHED_AT_DESC",  # Always newest first for arbitrage
            },
            "shouldntLoadBumps": True,
            "shouldntLoadSuggestions": True,
            "usingListView": False,
            "signalGroups": ["MP_GRID_CARD"],
            "useSignalSystem": False,
        },
        "query": GQL_SEARCH,
    }

    try:
        resp = requests.post(GQL_ENDPOINT, json=body, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("listingsSearch", {}).get("listings", [])
    except Exception as e:
        print(f"  [ERROR] fetch_listings({query}): {e}")
        return []


def process_listing(listing: dict, watch: dict, config: dict) -> Optional[dict]:
    """
    Evaluate a single listing. Returns deal info dict if it passes, else None.
    """
    price_cents = listing.get("pricing", {}).get("buyerPrice", {}).get("amountCents", 0)
    if not price_cents:
        return None

    buy_price = price_cents / 100

    # Max buy price filter
    max_buy = watch.get("max_buy_price")
    if max_buy and buy_price > max_buy:
        return None

    # Skip local pickup only
    if listing.get("shipping", {}).get("localPickupOnly"):
        return None

    # Get market value - prefer Price Guide data, fall back to priceMiddle
    csp = listing.get("csp", {})
    condition_uuid = listing.get("condition", {}).get("conditionUuid")
    market_cents = None

    if csp.get("id") and condition_uuid and config.get("use_price_guide", True):
        pg = get_price_estimate(csp["id"], condition_uuid)
        if pg:
            market_cents = pg.get("priceMiddle")

    # Fall back to inline priceRecommendation
    if not market_cents:
        market_cents = (
            listing.get("priceRecommendation", {})
            .get("priceMiddle", {})
            .get("amountCents")
        )

    if not market_cents:
        return None

    market_price = market_cents / 100

    # Score the listing
    result = score_listing(
        listing=listing,
        buy_price=buy_price,
        market_price=market_price,
        min_profit=watch.get("min_profit", config.get("default_min_profit", 15)),
        config=config,
    )

    return result


def run_scan():
    config = load_config()
    seen = load_seen()
    new_seen = set()
    alerts_fired = 0

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting scan — {len(config['watches'])} watches")

    for watch in config["watches"]:
        if not watch.get("enabled", True):
            continue

        query = watch["query"]
        print(f"  Scanning: '{query}'")

        listings = fetch_listings(
            query=query,
            limit=watch.get("scan_limit", 30),
            condition_slugs=watch.get("condition_slugs", []),
        )

        print(f"    Got {len(listings)} listings")

        for listing in listings:
            lid = listing.get("id")
            if not lid:
                continue
            new_seen.add(lid)

            if lid in seen:
                continue  # Already processed

            result = process_listing(listing, watch, config)
            if result:
                send_notification(result, config)
                alerts_fired += 1
                # Rate limit notifications
                time.sleep(0.5)

        # Be polite to Reverb's servers
        time.sleep(2)

    # Merge seen sets
    seen.update(new_seen)
    save_seen(seen)

    print(f"  Done. {alerts_fired} alert(s) fired. Total seen: {len(seen)}")
    return alerts_fired


if __name__ == "__main__":
    run_scan()
