"""
Price Guide Module
Uses Reverb's internal Price Guide API to fetch real sold transaction data.
This is significantly more reliable than the inline priceRecommendation field.
"""

import requests
from datetime import datetime, timedelta
from functools import lru_cache

GQL_ENDPOINT = "https://gql.reverb.com/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "x-reverb-app": "REVERB",
    "Accept": "*/*",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

# Condition UUIDs (from HAR analysis)
# These map condition slugs to the UUIDs the Price Guide API requires
CONDITION_UUID_MAP = {
    "mint":            "ac5b9c1e-dc78-466d-b0b3-7cf712967a48",
    "mint-inventory":  "ac5b9c1e-dc78-466d-b0b3-7cf712967a48",  # new/dealer = mint tier
    "brand-new":       "ac5b9c1e-dc78-466d-b0b3-7cf712967a48",
    "excellent":       "ae4d9114-1bd7-4ec5-a4ba-6653af5ac84d",
    "very-good":       "ae4d9114-1bd7-4ec5-a4ba-6653af5ac84d",
    "good":            "6a9dfcad-600b-46c8-9e08-ce6e5057921e",
    "fair":            "6a9dfcad-600b-46c8-9e08-ce6e5057921e",
    "poor":            "6a9dfcad-600b-46c8-9e08-ce6e5057921e",
}

GQL_PRICE_ESTIMATES = """
query DataServices_PriceGuideToolEstimatesContainer($priceRecommendationQueries: [Input_reverb_pricing_PriceRecommendationQuery]) {
  priceRecommendations(input: {priceRecommendationQueries: $priceRecommendationQueries}) {
    priceRecommendations {
      priceLow { amountCents currency }
      priceMiddle { amountCents currency }
      priceHigh { amountCents currency }
      priceMiddleThirtyDaysAgo { amountCents currency }
    }
  }
}
"""

GQL_PRICE_HISTORY = """
query Search_PriceGuideToolTransactionGraph(
  $canonicalProductIds: [String]
  $sellerCountries: [String]
  $conditionUuids: [String]
  $createdAfterDate: String
  $actionableStatuses: [String]
) {
  priceRecordsSearch(input: {
    canonicalProductIds: $canonicalProductIds
    sellerCountries: $sellerCountries
    listingConditionUuids: $conditionUuids
    createdAfterDate: $createdAfterDate
    actionableStatuses: $actionableStatuses
    withAverageMonthlyProductPricesAggregations: true
  }) {
    averageMonthlyProductPrices {
      date
      docCount
      averageProductPrice { amount amountCents currency display }
    }
  }
}
"""

GQL_CSP_LOOKUP = """
query Core_PriceGuideToolFormContainer($cspSlug: String) {
  csp(input: {slug: $cspSlug}) {
    _id
    id
    title
    canonicalProducts { _id id finish model name year }
    slug
  }
}
"""

# Simple in-memory cache to avoid hammering the API
_price_cache = {}
CACHE_TTL_SECONDS = 3600  # 1 hour


def _cache_key(canonical_product_id: str, condition_uuid: str) -> str:
    return f"{canonical_product_id}:{condition_uuid}"


def get_price_estimate(canonical_product_id: str, condition_uuid: str) -> dict | None:
    """
    Fetch price low/mid/high from Reverb's Price Guide for a specific product + condition.
    Returns dict with amountCents values or None on failure.
    """
    key = _cache_key(canonical_product_id, condition_uuid)
    cached = _price_cache.get(key)
    if cached:
        age = (datetime.now() - cached["fetched_at"]).total_seconds()
        if age < CACHE_TTL_SECONDS:
            return cached["data"]

    body = {
        "operationName": "DataServices_PriceGuideToolEstimatesContainer",
        "variables": {
            "priceRecommendationQueries": [
                {
                    "canonicalProductId": canonical_product_id,
                    "conditionUuid": condition_uuid,
                    "countryCode": "US",
                }
            ]
        },
        "query": GQL_PRICE_ESTIMATES,
    }

    try:
        resp = requests.post(GQL_ENDPOINT, json=body, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        recs = (
            resp.json()
            .get("data", {})
            .get("priceRecommendations", {})
            .get("priceRecommendations", [])
        )
        if not recs:
            return None

        rec = recs[0]
        result = {
            "priceLow": rec.get("priceLow", {}).get("amountCents"),
            "priceMiddle": rec.get("priceMiddle", {}).get("amountCents"),
            "priceHigh": rec.get("priceHigh", {}).get("amountCents"),
            "priceMiddleThirtyDaysAgo": rec.get("priceMiddleThirtyDaysAgo", {}).get("amountCents"),
        }

        _price_cache[key] = {"data": result, "fetched_at": datetime.now()}
        return result

    except Exception as e:
        print(f"  [WARN] Price guide lookup failed for {canonical_product_id}: {e}")
        return None


def get_price_history(canonical_product_id: str, condition_uuid: str, months: int = 12) -> list:
    """
    Fetch monthly average sold prices for a product+condition.
    Returns list of {date, docCount, averagePrice} dicts.
    """
    after_date = (datetime.now() - timedelta(days=months * 30)).strftime("%Y-%m-%01")

    body = {
        "operationName": "Search_PriceGuideToolTransactionGraph",
        "variables": {
            "canonicalProductIds": [canonical_product_id],
            "conditionUuids": [condition_uuid],
            "sellerCountries": ["US"],
            "createdAfterDate": after_date,
            "actionableStatuses": ["shipped", "picked_up", "received"],
        },
        "query": GQL_PRICE_HISTORY,
    }

    try:
        resp = requests.post(GQL_ENDPOINT, json=body, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        months_data = (
            resp.json()
            .get("data", {})
            .get("priceRecordsSearch", {})
            .get("averageMonthlyProductPrices", [])
        )
        return [
            {
                "date": m["date"],
                "count": m["docCount"],
                "avg_price_cents": m["averageProductPrice"]["amountCents"],
                "avg_price_display": m["averageProductPrice"]["display"],
            }
            for m in months_data
        ]
    except Exception as e:
        print(f"  [WARN] Price history lookup failed: {e}")
        return []


def lookup_csp_by_slug(slug: str) -> dict | None:
    """Look up a canonical product by its slug. Returns CSP info including canonicalProduct IDs."""
    body = {
        "operationName": "Core_PriceGuideToolFormContainer",
        "variables": {"cspSlug": slug},
        "query": GQL_CSP_LOOKUP,
    }
    try:
        resp = requests.post(GQL_ENDPOINT, json=body, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json().get("data", {}).get("csp")
    except Exception:
        return None
