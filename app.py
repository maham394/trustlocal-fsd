from __future__ import annotations
import json
import os
import re
import streamlit as st
from dotenv import load_dotenv
from core import load_businesses, interpret_query_fallback, search_and_rank, validate_model_result

load_dotenv()
MODEL_ID = os.getenv("GEMMA_MODEL_ID", "gemma-4-26b-a4b-it")

st.set_page_config(page_title="TrustLocal FSD", page_icon="🔎", layout="wide")
st.markdown("""
<style>
.block-container {max-width: 1180px; padding-top: 2rem; padding-bottom: 3rem;}
.hero {padding: 1.5rem 1.6rem; border-radius: 18px; background: linear-gradient(120deg,#123b35,#236d5e); color: white; margin-bottom: 1rem;}
.hero h1 {color: white; margin-bottom: .3rem;}
.small-muted {font-size: .88rem; color: #667085;}
.score-number {font-size: 2rem; font-weight: 750; line-height: 1.15;}
.evidence-chip {display:inline-block; padding:.22rem .55rem; border-radius:999px; background:#edf5f2; color:#145448; font-size:.78rem; margin-right:.25rem;}
</style>
<div class="hero"><h1>🔎 TrustLocal FSD</h1><div>Discover locally. Compare transparently. Decide confidently.</div></div>
""", unsafe_allow_html=True)
st.info("Prototype notice: every listing and price below is fictional demonstration data. This app does not recommend real businesses or independently verify claims.")

try:
    businesses = load_businesses()
except Exception as exc:
    st.error(f"Could not load the local listings dataset: {exc}")
    st.stop()

with st.sidebar:
    st.header("About this prototype")
    st.write("TrustLocal helps compare the information available about relevant options. It does not determine which business is honest or objectively best.")
    st.markdown("**Evidence labels**")
    st.write("- Source provided: record provenance is listed")
    st.write("- Business claim: a description supplied in a listing")
    st.write("- Not independently verified: no outside verification was performed")
    st.write("- Information missing: the dataset does not contain that detail")
    st.divider()
    st.caption(f"Configured model: `{MODEL_ID}`")
    st.caption("The app only reports AI mode after a successful API response.")

st.subheader("What are you looking for?")
query = st.text_input("Describe your needs in everyday language", placeholder="Affordable printing near GCUF", key="search_query")
st.caption("Try: Affordable printing near GCUF · Budget clothing in D-Ground under 2000 · Phone repair near Susan Road")
examples = st.columns(3)
for col, example in zip(examples, ["Affordable printing near GCUF", "Budget clothing in D-Ground under 2000", "Phone repair near Susan Road"]):
    if col.button(example, use_container_width=True):
        st.session_state.search_query = example
        st.rerun()

def get_ai_interpretation(user_query: str, model_id: str, api_key: str) -> tuple[dict | None, str | None]:
    """Ask Gemma to parse the query. Returns a validated dictionary or an error."""
    if not api_key:
        return None, "No API key configured; deterministic fallback is active."
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        prompt = f'''You are the query interpreter for TrustLocal FSD. Return ONLY valid JSON with keys category, area, budget_max, preferences. category must be one of: printing, clothing, phone repair, or null. area must be one of: GCUF, D-Ground, People's Colony, Susan Road, or null. budget_max must be a number or null. preferences must be a short string. Do not invent businesses or facts. User request: {user_query!r}'''
        response = client.models.generate_content(model=model_id, contents=prompt)
        raw = (getattr(response, "text", None) or "").strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE)
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None, "Gemma returned an unexpected format; deterministic fallback is active."
        allowed_categories = {"printing", "clothing", "phone repair", None}
        allowed_areas = {"GCUF", "D-Ground", "People's Colony", "Susan Road", None}
        category = data.get("category")
        area = data.get("area")
        budget = data.get("budget_max")
        if category not in allowed_categories or area not in allowed_areas:
            return None, "Gemma returned an unsupported category or area; deterministic fallback is active."
        if budget is not None and (not isinstance(budget, (int, float)) or budget < 0):
            return None, "Gemma returned an invalid budget; deterministic fallback is active."
        return {"category": category, "area": area, "budget_max": int(budget) if budget is not None else None, "preferences": str(data.get("preferences", user_query))[:500]}, None
    except Exception as exc:
        # Log diagnostic details in the terminal, not in the UI.
        print(f"Gemma query interpretation error: {type(exc).__name__}: {exc}")
        return None, f"Gemma API unavailable ({type(exc).__name__}); deterministic fallback is active."

def get_ai_comparison(user_query: str, results: list[dict], model_id: str, api_key: str) -> tuple[dict | None, str | None]:
    """Ask Gemma to explain only the supplied results and validate its response."""
    if not api_key or not results:
        return None, "AI comparison unavailable; deterministic explanation is active."
    try:
        from google import genai
        from core import validate_model_result
        client = genai.Client(api_key=api_key)
        allowed_ids = {item["id"] for item in results}
        compact = [{
            "id": item["id"], "name": item["name"], "category": item["category"],
            "area": item["area"], "price": item.get("price"),
            "service_details": item.get("service_details"), "policies": item.get("policies"),
            "missing_information": item.get("missing_information", []),
            "transparency_score": item["transparency"]["score"],
            "match_reasons": item["match_reasons"],
            "evidence_note": item.get("evidence_notes"),
        } for item in results]
        prompt = f"""You are TrustLocal FSD's evidence-first comparison assistant. Use ONLY this supplied JSON data; do not invent facts, prices, reviews, verification, or businesses. A Transparency Score measures information completeness only, not honesty or quality. All records are fictional demonstration data. Explain the main trade-offs neutrally and mention missing evidence. Return ONLY JSON with exactly these keys: comparison_summary (string, max 1000 chars), verification_questions (array of 3-5 strings), listing_ids (array containing only IDs from the supplied records). Do not rank a business as objectively best. User request: {user_query!r}. Supplied records: {json.dumps(compact, ensure_ascii=False)}"""
        response = client.models.generate_content(model=model_id, contents=prompt)
        raw = (getattr(response, "text", None) or "").strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE)
        payload = json.loads(raw)
        validated = validate_model_result(payload, allowed_ids)
        if validated is None:
            return None, "Gemma comparison output failed validation; deterministic explanation is active."
        return validated, None
    except Exception as exc:
        # Log diagnostic details in the terminal, not in the UI.
        print(f"Gemma comparison error: {type(exc).__name__}: {exc}")
        return None, f"Gemma comparison unavailable ({type(exc).__name__}); deterministic explanation is active."
if st.button("Compare options", type="primary", disabled=not query.strip()):
    st.session_state.run_search = query.strip()

active_query = st.session_state.get("run_search", "")
if active_query:
    st.divider()
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    with st.spinner("Interpreting your request and comparing available listing information..."):
        parsed = None
        ai_error = None
        if api_key:
            parsed, ai_error = get_ai_interpretation(active_query, MODEL_ID, api_key)
        else:
            ai_error = "No GOOGLE_API_KEY found in .env; deterministic fallback is active."
        ai_used = parsed is not None
        if parsed is None:
            parsed = interpret_query_fallback(active_query)
        results = search_and_rank(businesses, parsed, limit=3)
        comparison = None
        comparison_error = None
        if ai_used and results:
            comparison, comparison_error = get_ai_comparison(active_query, results, MODEL_ID, api_key)
    if ai_used:
        st.success(f"Gemma query interpretation succeeded using `{MODEL_ID}`. Listing facts and scores remain controlled by the local dataset and Python.")
    else:
        st.warning(ai_error or "AI interpretation unavailable; deterministic fallback is active.")
    if parsed.get("category") or parsed.get("area") or parsed.get("budget_max") is not None:
        st.write("**Interpreted request:** " + " · ".join([str(x) for x in [parsed.get("category"), parsed.get("area"), f"budget up to PKR {parsed['budget_max']:,}" if parsed.get("budget_max") is not None else None] if x]))
    if not results:
        st.warning("No matching fictional sample listings were found. Try a supported category or area, or remove a restrictive preference.")
    else:
        if comparison:
            st.subheader("Gemma's evidence-based comparison")
            st.write(comparison["comparison_summary"])
            st.caption("AI-generated explanation based only on supplied fictional records; listing facts and scores remain controlled by the app.")
            with st.expander("Gemma's verification questions"):
                for question in comparison["verification_questions"]:
                    st.write(f"• {question}")
        else:
            st.subheader("Comparison summary (deterministic fallback)")
            top = results[0]
            st.write(f"{top['name']} is the first result because it is relevant to the interpreted request and then ranked by information completeness. Its score is {top['transparency']['score']}/100; this does not establish business quality or honesty. Compare the visible missing-information notes before making any real-world decision.")
            if comparison_error:
                st.caption(comparison_error)
        st.subheader(f"Relevant sample listings ({len(results)})")
        st.caption("Results are ranked by request relevance first, Transparency Score second, and listing ID third. A higher score is not proof of quality or honesty.")
        cards = st.columns(min(3, len(results)))
        for col, item in zip(cards, results):
            with col:
                with st.container(border=True):
                    st.markdown(f"### {item['name']}")
                    st.caption(f"{item['category'].title()} · {item['area']}")
                    st.markdown(f"<div class='score-number'>{item['transparency']['score']}<span style='font-size:1rem;font-weight:500'> / 100</span></div>", unsafe_allow_html=True)
                    st.caption("Transparency Score · information completeness only")
                    st.progress(item['transparency']['score'] / 100)
                    st.markdown("**Why it matched**")
                    if item["match_reasons"]:
                        for reason in item["match_reasons"]:
                            st.write(f"• {reason}")
                    st.markdown("**Information supplied**")
                    st.write(f"**Price:** {item.get('price') or 'Information missing'}")
                    st.write(f"**Service:** {item.get('service_details') or 'Information missing'}")
                    st.write(f"**Contact:** {item.get('contact_method') or 'Information missing'}")
                    st.markdown("<span class='evidence-chip'>Synthetic data</span> <span class='evidence-chip'>Not independently verified</span>", unsafe_allow_html=True)
                    with st.expander("View score breakdown"):
                        for detail in item["transparency"]["breakdown"].values():
                            mark = "✓" if detail["met"] else "—"
                            st.write(f"{mark} {detail['label']}: **{detail['awarded']}/{detail['possible']}**")
                    with st.expander("What is missing? / Evidence"):
                        st.write("**Missing or needs confirmation**")
                        for missing in item.get("missing_information", []):
                            st.write(f"• {missing}")
                        st.write("**Source type:** " + str(item.get("source_type", "Information missing")))
                        st.write("**Source reference:** " + str(item.get("source_reference", "Information missing")))
                        st.write("**Last updated:** " + str(item.get("last_updated", "Information missing")))
                        st.write("**Evidence note:** " + str(item.get("evidence_notes", "No evidence note supplied")))
                    with st.expander("Questions to verify"):
                        questions = ["Can you confirm the current price and any extra charges?", "How can I verify this business and its service details?", "What are the applicable delivery, return, exchange, or warranty terms?"]
                        for question in questions:
                            st.write(f"• {question}")
        st.caption("All listing names, prices, source references, and service details are fictional examples. They must not be treated as actual Faisalabad business recommendations.")

st.divider()
with st.expander("How the Transparency Score works"):
    st.write("The score measures whether useful information is present and traceable—not whether a business is good, honest, legitimate, or customer-approved.")
    st.markdown("- Price or range disclosed: **25 points**\n- Location/service area disclosed: **20 points**\n- Contact method disclosed: **15 points**\n- Relevant service details disclosed: **15 points**\n- Applicable policy disclosed: **15 points**\n- Source reference and last-updated date recorded: **10 points**")
    st.write("A disclosed business claim is still a claim. These synthetic records have not been independently verified.")
