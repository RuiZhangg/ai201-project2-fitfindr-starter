"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── parsing helpers ───────────────────────────────────────────────────────────

_PRICE_PATTERNS = [
    r"(?:under|below|less than)\s*\$?\s*(\d+(?:\.\d+)?)",
    r"max(?:imum)?\s*\$?\s*(\d+(?:\.\d+)?)",
]

_SIZE_PATTERNS = [
    r"\bsize\s+([a-z0-9/]+(?:\s*[a-z0-9/]+)?)",
    r"\bin\s+size\s+([a-z0-9/]+(?:\s*[a-z0-9/]+)?)",
]


def _extract_price(query: str) -> float | None:
    """Return a price ceiling if the user included one."""
    for pattern in _PRICE_PATTERNS:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _extract_size(query: str) -> str | None:
    """Return a size string if the user included one."""
    lowered = query.lower()
    for pattern in _SIZE_PATTERNS:
        match = re.search(pattern, lowered, flags=re.IGNORECASE)
        if match:
            size_text = match.group(1)
            size_text = re.split(
                r"\b(?:under|below|less|max(?:imum)?|for|with|and)\b",
                size_text,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]
            return size_text.strip(" ,.-").upper() or None
    return None


def _clean_description(query: str) -> str:
    """Remove routing phrases so search_listings gets the item request."""
    first_sentence = re.split(r"[.!?]", query, maxsplit=1)[0].strip()

    cleaned = re.sub(
        r"^\s*(i'm looking for|i am looking for|looking for|find me|show me|need|want)\s+",
        "",
        first_sentence,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^\s*(?:a|an)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\b(?:in\s+)?size\s+[a-z0-9/]+(?:\s*[a-z0-9/]+)?",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?:under|below|less than|max(?:imum)?)\s*\$?\s*\d+(?:\.\d+)?",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\$\s*\d+(?:\.\d+)?", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
    return cleaned


def _parse_query(query: str) -> dict:
    """Extract the search parameters used by the first tool."""
    description = _clean_description(query)
    size = _extract_size(query)
    max_price = _extract_price(query)
    return {
        "description": description,
        "size": size,
        "max_price": max_price,
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    session = _new_session(query, wardrobe)

    session["parsed"] = _parse_query(query)
    description = session["parsed"].get("description")
    size = session["parsed"].get("size")
    max_price = session["parsed"].get("max_price")

    if not description:
        session["error"] = (
            "I couldn't tell what item you want yet. Try describing the piece "
            "you're looking for, like 'vintage graphic tee under $30'."
        )
        return session

    session["search_results"] = search_listings(description, size, max_price)
    if not session["search_results"]:
        filter_bits = []
        if size:
            filter_bits.append(f"size {size}")
        if max_price is not None:
            filter_bits.append(f"under ${max_price:.0f}")

        filter_text = f" with {' and '.join(filter_bits)}" if filter_bits else ""
        session["error"] = (
            f"I couldn't find any listings for {description}{filter_text}. "
            "Try broader keywords, a higher budget, or removing the size filter."
        )
        return session

    session["selected_item"] = session["search_results"][0]
    session["outfit_suggestion"] = suggest_outfit(
        session["selected_item"],
        session["wardrobe"],
    )

    if not session["outfit_suggestion"] or not session["outfit_suggestion"].strip():
        session["error"] = "I found a listing, but I couldn't build an outfit idea right now."
        session["outfit_suggestion"] = None
        return session

    if "couldn't build an outfit idea" in session["outfit_suggestion"].lower():
        session["error"] = session["outfit_suggestion"]
        session["outfit_suggestion"] = None
        return session

    session["fit_card"] = create_fit_card(
        session["outfit_suggestion"],
        session["selected_item"],
    )

    if not session["fit_card"] or not session["fit_card"].strip():
        session["error"] = (
            "I found an item, but I couldn't generate the final fit card right now."
        )
        session["fit_card"] = None
        return session

    fit_card_lower = session["fit_card"].lower()
    if "couldn't generate" in fit_card_lower or "empty or incomplete" in fit_card_lower:
        session["error"] = session["fit_card"]
        session["fit_card"] = None

    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
