"""Deterministic data, scoring, filtering and ranking for TrustLocal FSD."""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any

SCORE_WEIGHTS = {
    "price": 25,
    "area": 20,
    "contact_method": 15,
    "service_details": 15,
    "policies": 15,
    "source_and_updated": 10,
}


def load_businesses(path: str | Path | None = None) -> list[dict[str, Any]]:
    file_path = Path(path) if path else Path(__file__).with_name("businesses.json")
    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("businesses.json must contain a list")
    ids = [item.get("id") for item in data]
    if any(not item_id for item_id in ids) or len(ids) != len(set(ids)):
        raise ValueError("Every listing must have a unique, non-empty ID")
    return data


def has_information(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip().lower()
    return bool(text) and not any(marker in text for marker in (
        "not supplied", "not provided", "not available", "unknown", "n/a", "none"
    ))


def transparency_score(business: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic score and breakdown. A score is not a trust verdict."""
    checks = {
        "price": has_information(business.get("price")) and "not supplied" not in str(business.get("price", "")).lower(),
        "area": has_information(business.get("area")),
        "contact_method": has_information(business.get("contact_method")),
        "service_details": has_information(business.get("service_details")),
        "policies": has_information(business.get("policies")),
        "source_and_updated": has_information(business.get("source_type")) and has_information(business.get("source_reference")) and has_information(business.get("last_updated")),
    }
    breakdown = {}
    score = 0
    for key, weight in SCORE_WEIGHTS.items():
        awarded = weight if checks[key] else 0
        score += awarded
        breakdown[key] = {"label": {
            "price": "Price or range disclosed", "area": "Location/service area disclosed",
            "contact_method": "Contact method disclosed", "service_details": "Relevant service details disclosed",
            "policies": "Applicable policy disclosed", "source_and_updated": "Source and last-updated date recorded",
        }[key], "possible": weight, "awarded": awarded, "met": checks[key]}
    return {"score": score, "breakdown": breakdown}


def interpret_query_fallback(query: str) -> dict[str, Any]:
    """Small deterministic parser used when Gemma is unavailable."""
    q = query.lower()
    category = None
    category_terms = {
        "printing": ["print", "printing", "photocopy", "photocopying", "binding"],
        "clothing": ["clothing", "clothes", "dress", "shirt", "wardrobe", "fashion"],
        "phone repair": ["phone repair", "mobile repair", "repair phone", "phone fixing"],
    }
    for cat, terms in category_terms.items():
        if any(term in q for term in terms):
            category = cat
            break
    # If a user clearly names an unsupported category, do not return unrelated listings.
    unsupported_category_terms = ["dentist", "dentistry", "restaurant", "salon", "pharmacy", "grocery", "plumber", "electrician"]
    if category is None and any(term in q for term in unsupported_category_terms):
        category = "unsupported category"
    area = None
    areas = ["gcuf", "d-ground", "d ground", "people's colony", "peoples colony", "susan road"]
    for known_area in areas:
        if known_area in q:
            canonical = {
                "gcuf": "GCUF", "d-ground": "D-Ground", "d ground": "D-Ground",
                "people's colony": "People's Colony", "peoples colony": "People's Colony",
                "susan road": "Susan Road",
            }
            area = canonical[known_area]
            break
    budget = None
    # Supports common patterns like "under 1000", "below PKR 2,000", "budget 1500".
    match = re.search(r"(?:under|below|less than|max(?:imum)?|budget(?: of)?|up to)\s*(?:pkr\s*)?([\d,]+)", q)
    if match:
        try:
            budget = int(match.group(1).replace(",", ""))
        except ValueError:
            budget = None
    return {"category": category, "area": area, "budget_max": budget, "preferences": query.strip()}


def listing_relevance(business: dict[str, Any], parsed: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    wanted_category = parsed.get("category")
    if wanted_category:
        if str(business.get("category", "")).lower() == wanted_category.lower():
            score += 5
            reasons.append(f"Category matches: {business.get('category')}")
        else:
            return 0, []
    wanted_area = parsed.get("area")
    if wanted_area:
        if str(business.get("area", "")).lower().replace(" ", "-") == wanted_area.lower().replace(" ", "-"):
            score += 4
            reasons.append(f"Area matches: {business.get('area')}")
        else:
            # Area is a preference; keep category matches but mark location mismatch.
            reasons.append(f"Located in {business.get('area')}; requested area was {wanted_area}")
    budget = parsed.get("budget_max")
    if budget is not None:
        min_price = business.get("price_min")
        max_price = business.get("price_max")
        if min_price is not None and min_price > budget:
            return 0, []
        if min_price is None and max_price is not None and max_price > budget:
            reasons.append("Budget fit is uncertain because only an upper price estimate is recorded")
        elif min_price is None and max_price is None:
            reasons.append("Budget fit cannot be determined because numeric price data is missing")
        elif min_price is not None and min_price <= budget and (max_price is None or max_price <= budget):
            score += 2
            reasons.append(f"Sample price data appears within the stated budget of PKR {budget:,}")
        elif min_price is not None and min_price <= budget:
            score += 1
            reasons.append("Some sample price information may fit the budget; confirm total cost")
        else:
            reasons.append(f"Sample price data may exceed the stated budget of PKR {budget:,}")
    if not wanted_category and not wanted_area and budget is None:
        terms = set(re.findall(r"[a-z]+", parsed.get("preferences", "").lower()))
        fields = " ".join(str(business.get(k, "")) for k in ("category", "area", "service_details", "name")).lower()
        overlap = terms.intersection(set(re.findall(r"[a-z]+", fields)))
        if overlap:
            score += min(3, len(overlap))
            reasons.append("Matches words in your request: " + ", ".join(sorted(overlap)))
    if not wanted_category and not wanted_area and budget is None and not score:
        return 0, []
    return score, reasons


def search_and_rank(businesses: list[dict[str, Any]], parsed: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    results = []
    for business in businesses:
        relevance, reasons = listing_relevance(business, parsed)
        if relevance <= 0:
            continue
        scored = transparency_score(business)
        item = dict(business)
        item["relevance_score"] = relevance
        item["match_reasons"] = reasons
        item["transparency"] = scored
        results.append(item)
    # Relevance is primary; transparency is secondary; stable ID is deterministic tie-breaker.
    results.sort(key=lambda x: (-x["relevance_score"], -x["transparency"]["score"], x["id"]))
    return results[:limit]


def validate_model_result(payload: Any, allowed_ids: set[str]) -> dict[str, Any] | None:
    """Reject malformed model output and any ID not present in the actual dataset."""
    if not isinstance(payload, dict):
        return None
    explanation = payload.get("comparison_summary")
    questions = payload.get("verification_questions")
    ids = payload.get("listing_ids", [])
    if not isinstance(explanation, str) or not isinstance(questions, list) or not isinstance(ids, list):
        return None
    if not all(isinstance(q, str) for q in questions):
        return None
    if not all(isinstance(item_id, str) and item_id in allowed_ids for item_id in ids):
        return None
    return {"comparison_summary": explanation[:2000], "verification_questions": questions[:6], "listing_ids": ids}
