import os
from typing import Any

import requests
from fastmcp import FastMCP

mcp = FastMCP("fixify_amazon_india")

SERPAPI_URL = "https://serpapi.com/search.json"


def _api_key() -> str:
    key = os.getenv("SERPAPI_KEY")
    if not key:
        raise RuntimeError("Missing SERPAPI_KEY environment variable")
    return key


def _price_to_number(value: Any) -> float | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    # SerpApi may return prices as strings such as "₹42,990"
    text = str(value).replace(",", "").replace("₹", "").strip()

    try:
        return float(text)
    except ValueError:
        return None


def _normalise_product(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": item.get("title"),
        "price_inr": _price_to_number(item.get("price")),
        "mrp_inr": _price_to_number(item.get("extracted_price")),
        "rating": item.get("rating"),
        "reviews": item.get("reviews"),
        "asin": item.get("asin"),
        "url": item.get("link"),
        "delivery": item.get("delivery"),
    }


@mcp.tool()
def search_mat(
    query: str,
    max_results: int = 10,
) -> dict[str, Any]:
    """
    Search Amazon India for mats using a natural-language query.

    The calling LLM should provide the search query in normal language,
    for example:
      - "1.5 ton 5 star inverter AC under 45000"
      - "8 kg front load washing machine"
      - "double door refrigerator under 40000"

    Returns structured Amazon.in product results. This tool does not
    recommend or rank products beyond Amazon's returned ordering.
    """
    query = query.strip()

    if not query:
        raise ValueError("query cannot be empty")

    max_results = max(1, min(int(max_results), 20))

    params = {
        "api_key": _api_key(),
        "engine": "amazon",
        "k": query,
        "amazon_domain": "amazon.in",
        "language": "en_IN",
        "page": 1,
        "output": "json",
    }

    response = requests.get(
        SERPAPI_URL,
        params=params,
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"SerpApi request failed: HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    data = response.json()

    if data.get("error"):
        raise RuntimeError(f"SerpApi error: {data['error']}")

    organic_results = data.get("organic_results", [])

    products = [
        _normalise_product(item)
        for item in organic_results[:max_results]
    ]

    return {
        "marketplace": "Amazon.in",
        "currency": "INR",
        "query": query,
        "count": len(products),
        "products": products,
        "source": "SerpApi Amazon Search",
    }


@mcp.tool()
def get_mat(
    asin: str,
) -> dict[str, Any]:
    """
    Retrieve the current Amazon India product page for a specific ASIN.

    Useful when Brain already has an ASIN from search_mat.
    """
    asin = asin.strip()

    if not asin:
        raise ValueError("asin cannot be empty")

    params = {
        "api_key": _api_key(),
        "engine": "amazon_product",
        "asin": asin,
        "amazon_domain": "amazon.in",
        "language": "en_IN",
        "output": "json",
    }

    response = requests.get(
        SERPAPI_URL,
        params=params,
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"SerpApi request failed: HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    data = response.json()

    if data.get("error"):
        raise RuntimeError(f"SerpApi error: {data['error']}")

    product = data.get("product_results") or {}

    return {
        "marketplace": "Amazon.in",
        "currency": "INR",
        "asin": asin,
        "product": {
            "name": product.get("title"),
            "price_inr": _price_to_number(product.get("price")),
            "mrp_inr": _price_to_number(product.get("old_price")),
            "rating": product.get("rating"),
            "reviews": product.get("reviews"),
            "url": product.get("link"),
            "offers": product.get("offers"),
            "emi": product.get("emi"),
        },
        "source": "SerpApi Amazon Product Search",
    }


if __name__ == "__main__":
    # Render supplies PORT automatically.
    # FastMCP exposes the MCP endpoint at /mcp.
    port = int(os.getenv("PORT", "8000"))

    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=port,
    )
