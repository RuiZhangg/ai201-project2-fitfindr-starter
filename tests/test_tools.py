import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import tools
from tools import create_fit_card, search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe


class FakeCompletions:
    def __init__(self, content: str = "", error: Exception | None = None):
        self.content = content
        self.error = error
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content)
                )
            ]
        )


class FakeClient:
    def __init__(self, content: str = "", error: Exception | None = None):
        self.completions = FakeCompletions(content=content, error=error)
        self.chat = SimpleNamespace(completions=self.completions)


def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0
    assert results[0]["id"] == "lst_006"


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter_matches_flexible_sizes():
    results = search_listings("baby tee", size="M", max_price=30)
    result_ids = [item["id"] for item in results]
    assert "lst_002" in result_ids


def test_suggest_outfit_with_empty_wardrobe_returns_general_advice(monkeypatch):
    fake_client = FakeClient(content="Try it with loose jeans and chunky sneakers.")
    monkeypatch.setattr(tools, "_get_groq_client", lambda: fake_client)

    new_item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    response = suggest_outfit(new_item, get_empty_wardrobe())

    assert response == "Try it with loose jeans and chunky sneakers."
    prompt = fake_client.completions.calls[0]["messages"][1]["content"]
    assert "wardrobe is empty" in prompt.lower()
    assert fake_client.completions.calls[0]["model"] == tools.LLM_MODEL


def test_suggest_outfit_with_wardrobe_references_named_pieces_in_prompt(monkeypatch):
    fake_client = FakeClient(content="Use the baggy jeans and black denim jacket.")
    monkeypatch.setattr(tools, "_get_groq_client", lambda: fake_client)

    new_item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    response = suggest_outfit(new_item, get_example_wardrobe())

    assert response == "Use the baggy jeans and black denim jacket."
    prompt = fake_client.completions.calls[0]["messages"][1]["content"]
    assert "Baggy straight-leg jeans, dark wash" in prompt
    assert "Vintage black denim jacket" in prompt


def test_suggest_outfit_handles_llm_failure(monkeypatch):
    fake_client = FakeClient(error=RuntimeError("network down"))
    monkeypatch.setattr(tools, "_get_groq_client", lambda: fake_client)

    new_item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    response = suggest_outfit(new_item, get_example_wardrobe())

    assert "couldn't build an outfit idea" in response.lower()


def test_create_fit_card_empty_outfit_returns_error():
    new_item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    response = create_fit_card("", new_item)
    assert "empty or incomplete" in response.lower()


def test_create_fit_card_returns_caption_from_llm(monkeypatch):
    fake_client = FakeClient(
        content="Found this tee on Depop for $24 and styled it with loose denim."
    )
    monkeypatch.setattr(tools, "_get_groq_client", lambda: fake_client)

    new_item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    response = create_fit_card("Pair it with baggy jeans and sneakers.", new_item)

    assert response == "Found this tee on Depop for $24 and styled it with loose denim."
    call = fake_client.completions.calls[0]
    assert call["temperature"] == 1.0
    prompt = call["messages"][1]["content"]
    assert new_item["title"] in prompt
    assert str(int(new_item["price"])) in prompt
    assert new_item["platform"] in prompt


def test_create_fit_card_handles_llm_failure(monkeypatch):
    fake_client = FakeClient(error=RuntimeError("llm unavailable"))
    monkeypatch.setattr(tools, "_get_groq_client", lambda: fake_client)

    new_item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    response = create_fit_card("Pair it with baggy jeans and sneakers.", new_item)

    assert "couldn't generate the final fit card" in response.lower()
