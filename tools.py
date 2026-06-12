"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import re

from groq import Groq

from config import GROQ_API_KEY, LLM_MODEL
from utils.data_loader import load_listings


STOP_WORDS = {
    "a",
    "an",
    "and",
    "for",
    "i",
    "im",
    "in",
    "looking",
    "of",
    "the",
    "to",
    "under",
    "with",
}


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    if not GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=GROQ_API_KEY)


# ── helpers ───────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Normalize freeform text into lowercase keyword tokens."""
    return [
        token for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if token not in STOP_WORDS
    ]


def _normalize_size(size: str | None) -> list[str]:
    """Split a size string into comparable tokens like 'm', 'w30', '8'."""
    return re.findall(r"[a-z0-9]+", (size or "").lower())


def _size_matches(listing_size: str, requested_size: str | None) -> bool:
    """Allow flexible matching such as M -> S/M and W30 -> W30 L30."""
    if not requested_size:
        return True

    requested_tokens = set(_normalize_size(requested_size))
    listing_tokens = set(_normalize_size(listing_size))

    if not requested_tokens:
        return True

    normalized_listing = " ".join(_normalize_size(listing_size))
    normalized_requested = " ".join(_normalize_size(requested_size))

    return (
        requested_tokens.issubset(listing_tokens)
        or normalized_requested in normalized_listing
        or normalized_listing in normalized_requested
    )


def _score_listing(listing: dict, keywords: list[str], phrase: str) -> int:
    """Score a listing based on keyword overlap in important fields."""
    title_tokens = set(_tokenize(listing.get("title", "")))
    description_tokens = set(_tokenize(listing.get("description", "")))
    category_tokens = set(_tokenize(listing.get("category", "")))
    style_tokens = set(_tokenize(" ".join(listing.get("style_tags", []))))
    color_tokens = set(_tokenize(" ".join(listing.get("colors", []))))
    brand_tokens = set(_tokenize(listing.get("brand") or ""))
    listing_blob = " ".join(
        [
            listing.get("title", ""),
            listing.get("description", ""),
            listing.get("category", ""),
            " ".join(listing.get("style_tags", [])),
            " ".join(listing.get("colors", [])),
            listing.get("brand") or "",
        ]
    ).lower()

    score = 0
    if phrase and phrase in listing_blob:
        score += 5

    for keyword in keywords:
        if keyword in title_tokens:
            score += 4
        if keyword in style_tokens:
            score += 3
        if keyword in description_tokens:
            score += 2
        if keyword in category_tokens:
            score += 2
        if keyword in color_tokens:
            score += 1
        if keyword in brand_tokens:
            score += 1

    return score


def _format_listing(listing: dict) -> str:
    """Build a compact description of a listing for LLM prompts."""
    brand = listing.get("brand") or "Unknown brand"
    style_tags = ", ".join(listing.get("style_tags", []))
    colors = ", ".join(listing.get("colors", []))
    return (
        f"Title: {listing.get('title', 'Unknown item')}\n"
        f"Category: {listing.get('category', 'unknown')}\n"
        f"Description: {listing.get('description', '')}\n"
        f"Size: {listing.get('size', 'unknown')}\n"
        f"Condition: {listing.get('condition', 'unknown')}\n"
        f"Price: ${listing.get('price', 'unknown')}\n"
        f"Colors: {colors}\n"
        f"Style tags: {style_tags}\n"
        f"Brand: {brand}\n"
        f"Platform: {listing.get('platform', 'unknown')}"
    )


def _format_wardrobe_items(wardrobe_items: list[dict]) -> str:
    """Format wardrobe pieces into readable prompt lines."""
    lines = []
    for item in wardrobe_items:
        colors = ", ".join(item.get("colors", []))
        tags = ", ".join(item.get("style_tags", []))
        notes = item.get("notes") or "No extra notes."
        lines.append(
            f"- {item.get('name', 'Unnamed item')} "
            f"(category: {item.get('category', 'unknown')}; "
            f"colors: {colors}; style tags: {tags}; notes: {notes})"
        )
    return "\n".join(lines)


def _call_llm(system_prompt: str, user_prompt: str, temperature: float) -> str:
    """Send a chat completion request to Groq and return plain text."""
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=300,
    )
    return (response.choices[0].message.content or "").strip()


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    keywords = _tokenize(description)
    if not keywords:
        return []

    phrase = " ".join(keywords)
    matches: list[tuple[int, dict]] = []

    for listing in load_listings():
        if max_price is not None and listing.get("price", 0.0) > max_price:
            continue
        if size and not _size_matches(listing.get("size", ""), size):
            continue

        score = _score_listing(listing, keywords, phrase)
        if score > 0:
            matches.append((score, listing))

    matches.sort(
        key=lambda item: (
            -item[0],
            item[1].get("price", float("inf")),
            item[1].get("title", ""),
        )
    )
    return [listing for _, listing in matches]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    if not new_item:
        return "I couldn't suggest an outfit because no listing was provided."

    wardrobe_items = wardrobe.get("items", []) if isinstance(wardrobe, dict) else []
    item_summary = _format_listing(new_item)

    if not wardrobe_items:
        system_prompt = (
            "You are a helpful fashion stylist. Give practical styling advice "
            "for one thrifted item when the user has not shared wardrobe items."
        )
        user_prompt = (
            "A user found this thrifted item:\n"
            f"{item_summary}\n\n"
            "The wardrobe is empty, so give general styling advice instead of "
            "referencing closet pieces. Suggest 1-2 wearable outfit ideas, name "
            "what kinds of bottoms, shoes, and layers would pair well, and keep "
            "the tone casual and specific."
        )
    else:
        system_prompt = (
            "You are a helpful fashion stylist. Build outfit ideas using the "
            "new thrifted item and specific named pieces from the user's wardrobe."
        )
        user_prompt = (
            "The user is considering this thrifted item:\n"
            f"{item_summary}\n\n"
            "Here are the wardrobe pieces you can use:\n"
            f"{_format_wardrobe_items(wardrobe_items)}\n\n"
            "Suggest 1-2 complete outfits that explicitly mention named wardrobe "
            "pieces from the list. Explain the vibe and any small styling move "
            "that makes the outfit feel intentional."
        )

    try:
        response = _call_llm(system_prompt, user_prompt, temperature=0.7)
    except Exception:
        return "I found a listing, but I couldn't build an outfit idea right now."

    if not response.strip():
        return "I found a listing, but I couldn't build an outfit idea right now."
    return response


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return (
            "I couldn't generate a fit card because the outfit description was "
            "empty or incomplete."
        )

    if not new_item:
        return "I couldn't generate a fit card because the listing details were missing."

    system_prompt = (
        "You write short, natural outfit captions for social posts. Keep them "
        "specific, casual, and human."
    )
    user_prompt = (
        "Write a 2-4 sentence caption for a thrifted outfit post.\n\n"
        f"Listing details:\n{_format_listing(new_item)}\n\n"
        f"Outfit idea:\n{outfit}\n\n"
        "Requirements:\n"
        "- Mention the item title naturally once.\n"
        "- Mention the price once.\n"
        "- Mention the resale platform once.\n"
        "- Capture the outfit vibe in specific terms.\n"
        "- Sound like a real OOTD caption, not a product listing."
    )

    try:
        response = _call_llm(system_prompt, user_prompt, temperature=1.0)
    except Exception:
        return (
            "I couldn't generate the final fit card right now. Please try again "
            "after the outfit step succeeds."
        )

    if not response.strip():
        return (
            "I couldn't generate the final fit card right now. Please try again "
            "after the outfit step succeeds."
        )
    return response
