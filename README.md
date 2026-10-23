# TrustLocal FSD

**Discover locally. Compare transparently. Decide confidently.**

TrustLocal FSD is a small, evidence-first local-business comparison prototype. Users describe a need in everyday language; the app interprets supported categories, areas and budgets, compares matching sample records, calculates a transparent information-completeness score, and displays missing information and verification questions.

> **Prototype disclaimer:** all listing names, prices, details and source references in `businesses.json` are fictional demonstration data. They are not real business recommendations and have not been independently verified.

## What it demonstrates

- Streamlit UI for natural-language requests and comparison cards.
- Optional Gemma API query interpretation using Google's `google-genai` SDK.
- Deterministic Python filtering, relevance-first ranking, and Transparency Score calculation.
- Visible score breakdown, source information, missing fields, and questions to verify.
- Deterministic fallback when no API key is present or the model call fails.
- Tests for score calculation, filtering/ranking, and model-output validation.

## Transparency Score

| Criterion | Points |
|---|---:|
| Price or range disclosed | 25 |
| Location/service area disclosed | 20 |
| Contact method disclosed | 15 |
| Relevant service details disclosed | 15 |
| Applicable policy disclosed | 15 |
| Source reference and last-updated date recorded | 10 |
| **Maximum** | **100** |

This score measures information completeness and traceability only. It does **not** measure business quality, honesty, legitimacy, or customer satisfaction. A business claim is not independently verified merely because it is recorded. In this prototype, records are synthetic, so no real business has been independently verified.

Ranking is relevance-first, Transparency Score second, and listing ID as a deterministic tie-breaker. An irrelevant listing should not rank higher simply because it has more fields filled in.

## Requirements

- Python 3.10 or newer recommended
- A Google AI Studio API key only if you want to test the model-backed interpretation
- Internet access for installing packages and calling the API

## Windows setup

Open PowerShell in this folder and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` in VS Code and replace `replace_with_your_key` with your own key. Do not paste the key into `app.py`, commit it, or share it in screenshots. If PowerShell blocks activation, use `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` for that terminal session, then activate again.

Start the app:

```powershell
python -m streamlit run app.py
```

Streamlit will print a local URL, usually `http://localhost:8501`.

## Model and license disclosure — verify before submission

The intended default model ID is `gemma-4-26b-a4b-it`, requested through the Google Gen AI SDK. Google's current Gemma API guide lists `gemma-4-26b-a4b-it` and `gemma-4-31b-it` as supported Gemma 4 API model IDs. The official Gemma 4 model card lists the model family under Apache 2.0. API access remains subject to the provider's API terms and account availability. The application reports successful Gemma query interpretation only when a call returns parseable, validated output. If the key is missing or the call fails, the app visibly switches to deterministic fallback mode.

**Do not claim successful Gemma 4 usage until you run the app with a valid key and verify that this exact model ID works for your account.** The MIT license in this repository covers this project's source code only; it does not license the model or override model/API terms. If the model ID is unavailable, do not silently substitute another model or claim the Gemma prize requirement is satisfied.

Official resources to cite/check before submission:

- Gemma on the Gemini API (model IDs and API example): https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api
- Gemma 4 model card (license information): https://ai.google.dev/gemma/docs/core/model_card_4
- Gemini API documentation and terms: https://ai.google.dev/gemini-api/docs
- MLH challenge rules supplied by the event organizer

## Tests

Run:

```powershell
python -m unittest -v
```

These local tests do not require an API key. They test the deterministic logic and validation. They do not prove that the remote Gemma API works.

## Public GitHub checklist

1. Create a public repository named `trustlocal-fsd`.
2. Ensure `.env` is not tracked (`git status --short` and `git check-ignore .env`).
3. Commit `app.py`, `core.py`, `businesses.json`, `requirements.txt`, `.env.example`, `.gitignore`, `LICENSE`, `README.md`, and tests.
4. Push the repository and test setup from a clean clone if time permits.
5. Record the exact model ID tested, date tested, and result in the README. Do not write “tested successfully” unless you observed a successful response.
6. Confirm the organizer's current rules and the actual model license/terms. Final prize eligibility is decided by the organizers.

## Three-minute demo script

**0:00–0:25 — Problem and principle**
“TrustLocal FSD helps people compare what local listings disclose. It does not label businesses trustworthy or dishonest; it makes information gaps visible.”

**0:25–0:55 — Search**
Enter `Affordable printing near GCUF`, then run Compare options. Explain whether Gemma interpretation or the clearly labelled fallback is active.

**0:55–1:35 — Compare**
Show the fictional listing cards. Explain that matching category/location relevance is considered before Transparency Score, so a complete but irrelevant record cannot automatically win.

**1:35–2:10 — Score and evidence**
Open a score breakdown. Explain the 25/20/15/15/15/10 weights. Point out that the score measures completeness, not quality or honesty.

**2:10–2:40 — Missing information**
Open “What is missing?” and “Questions to verify.” Explain how this helps users ask better questions without inventing reviews or verification.

**2:40–3:00 — Open source and limitations**
Show the public repository, MIT license, model documentation, and tests. State clearly that the current dataset is fictional and that real-world utility requires permissioned, sourced, maintained records.
