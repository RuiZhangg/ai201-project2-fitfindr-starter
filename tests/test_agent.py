import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import agent
import app
from utils.data_loader import get_example_wardrobe


def test_run_agent_happy_path_preserves_state(monkeypatch):
    selected_item = {
        "id": "lst_test",
        "title": "Vintage Graphic Tee",
        "description": "Faded tee",
        "category": "tops",
        "style_tags": ["vintage", "graphic tee"],
        "size": "M",
        "condition": "good",
        "price": 24.0,
        "colors": ["black"],
        "brand": None,
        "platform": "depop",
    }
    calls = {}

    def fake_search(description, size, max_price):
        calls["search"] = (description, size, max_price)
        return [selected_item]

    def fake_suggest(new_item, wardrobe):
        calls["suggest"] = (new_item, wardrobe)
        return "Pair it with baggy jeans and chunky sneakers."

    def fake_fit_card(outfit, new_item):
        calls["fit_card"] = (outfit, new_item)
        return "Found this on Depop for $24 and styled it with easy denim."

    monkeypatch.setattr(agent, "search_listings", fake_search)
    monkeypatch.setattr(agent, "suggest_outfit", fake_suggest)
    monkeypatch.setattr(agent, "create_fit_card", fake_fit_card)

    wardrobe = get_example_wardrobe()
    session = agent.run_agent(
        "I'm looking for a vintage graphic tee under $30, size M.",
        wardrobe,
    )

    assert session["error"] is None
    assert session["parsed"] == {
        "description": "vintage graphic tee",
        "size": "M",
        "max_price": 30.0,
    }
    assert session["selected_item"] is selected_item
    assert session["search_results"] == [selected_item]
    assert session["outfit_suggestion"] == "Pair it with baggy jeans and chunky sneakers."
    assert session["fit_card"] == "Found this on Depop for $24 and styled it with easy denim."
    assert calls["search"] == ("vintage graphic tee", "M", 30.0)
    assert calls["suggest"][0] is selected_item
    assert calls["suggest"][1] is wardrobe
    assert calls["fit_card"] == (
        "Pair it with baggy jeans and chunky sneakers.",
        selected_item,
    )


def test_run_agent_returns_early_when_search_is_empty(monkeypatch):
    def fake_search(description, size, max_price):
        return []

    def fail_suggest(*args, **kwargs):
        raise AssertionError("suggest_outfit should not be called on empty search results")

    def fail_fit_card(*args, **kwargs):
        raise AssertionError("create_fit_card should not be called on empty search results")

    monkeypatch.setattr(agent, "search_listings", fake_search)
    monkeypatch.setattr(agent, "suggest_outfit", fail_suggest)
    monkeypatch.setattr(agent, "create_fit_card", fail_fit_card)

    session = agent.run_agent(
        "designer ballgown size XXS under $5",
        get_example_wardrobe(),
    )

    assert "couldn't find any listings" in session["error"].lower()
    assert session["selected_item"] is None
    assert session["outfit_suggestion"] is None
    assert session["fit_card"] is None


def test_handle_query_returns_error_for_blank_input():
    listing, outfit, fit_card = app.handle_query("   ", "Example wardrobe")
    assert "please enter a description" in listing.lower()
    assert outfit == ""
    assert fit_card == ""


def test_handle_query_formats_successful_session(monkeypatch):
    fake_session = {
        "error": None,
        "selected_item": {
            "title": "Vintage Graphic Tee",
            "price": 24.0,
            "size": "M",
            "condition": "good",
            "platform": "depop",
            "brand": None,
            "colors": ["black"],
            "style_tags": ["vintage", "graphic tee"],
            "description": "Soft and worn-in",
        },
        "outfit_suggestion": "Pair it with baggy jeans.",
        "fit_card": "Found this on Depop for $24.",
    }

    monkeypatch.setattr(app, "run_agent", lambda query, wardrobe: fake_session)

    listing, outfit, fit_card = app.handle_query(
        "vintage graphic tee under $30",
        "Example wardrobe",
    )

    assert "Vintage Graphic Tee" in listing
    assert "Price: $24.00" in listing
    assert outfit == "Pair it with baggy jeans."
    assert fit_card == "Found this on Depop for $24."
