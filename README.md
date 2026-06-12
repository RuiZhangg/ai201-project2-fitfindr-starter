# FitFindr

FitFindr is a multi-tool thrift styling agent. A user describes a secondhand piece they want, the agent searches the mock listings dataset, chooses a top match, suggests how to style it with the user's wardrobe, and then turns the result into a short fit-card caption.

This project uses three tools connected by a planning loop:
- `search_listings()` finds matching items in the local dataset.
- `suggest_outfit()` uses the selected item plus the wardrobe to generate styling ideas.
- `create_fit_card()` turns the styling result into a shareable caption.

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Add a `.env` file in the project root:

```env
GROQ_API_KEY=your_key_here
GROQ_PROXY_URL=your_proxy_address
```

`GROQ_PROXY_URL` is optional, but this project supports it through `config.py`.

## Run

Run the Gradio app:

```bash
.venv/bin/python app.py
```

Run the tests:

```bash
.venv/bin/pytest tests/
```

Current local verification: `14 passed`.

## Tool Inventory

### `search_listings(description: str, size: str | None = None, max_price: float | None = None) -> list[dict]`

Purpose:
Search the mock resale listings and return relevant items ranked by match quality.

Inputs:
- `description` (`str`): The item the user wants, such as `"vintage graphic tee"` or `"90s track jacket"`.
- `size` (`str | None`): Optional size filter such as `"M"`, `"S/M"`, `"W30"`, or `"US 8"`.
- `max_price` (`float | None`): Optional maximum price in dollars.

Output:
- A `list[dict]` sorted from best match to weakest match.
- Each result dict includes `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Implementation notes:
- Uses `load_listings()` from `utils/data_loader.py`.
- Applies size and price filters first.
- Scores results by keyword overlap across title, description, category, style tags, colors, and brand.

### `suggest_outfit(new_item: dict, wardrobe: dict) -> str`

Purpose:
Generate 1 to 2 outfit ideas for the selected thrift item.

Inputs:
- `new_item` (`dict`): The listing selected from `search_listings()`.
- `wardrobe` (`dict`): A wardrobe object with an `items` list. Each wardrobe item includes `id`, `name`, `category`, `colors`, `style_tags`, and optional `notes`.

Output:
- A non-empty `str` containing either specific wardrobe-based outfit suggestions or general styling advice.

Implementation notes:
- Calls Groq with `llama-3.3-70b-versatile`.
- If `wardrobe["items"]` is empty, it switches to general styling advice instead of failing.
- If the LLM call fails, it returns a clear fallback message instead of raising an exception.

### `create_fit_card(outfit: str, new_item: dict) -> str`

Purpose:
Convert the outfit suggestion into a short social-style caption.

Inputs:
- `outfit` (`str`): The text returned by `suggest_outfit()`.
- `new_item` (`dict`): The same listing dict used in the previous step.

Output:
- A `str` of about 2 to 4 sentences that sounds like a real outfit post.

Implementation notes:
- Calls Groq with a higher temperature than `suggest_outfit()` so the output feels less repetitive.
- Mentions the item title, price, and platform naturally.
- Returns a descriptive error string if `outfit` is blank or incomplete.

## Planning Loop

The agent uses a conditional planning loop in `run_agent()` instead of blindly calling every tool.

1. Start a new session dict.
2. Parse the user query into `description`, `size`, and `max_price`.
3. Call `search_listings(description, size, max_price)`.
4. If `search_results` is empty:
   set `session["error"]` and return immediately.
5. If results exist:
   store the full list in `session["search_results"]` and the top match in `session["selected_item"]`.
6. Call `suggest_outfit(selected_item, wardrobe)`.
7. If outfit generation fails or returns blank text:
   set `session["error"]` and return immediately.
8. Otherwise store the result in `session["outfit_suggestion"]`.
9. Call `create_fit_card(outfit_suggestion, selected_item)`.
10. If fit card generation fails:
   store the failure message in `session["error"]` and stop.
11. Otherwise store the final caption in `session["fit_card"]` and return the completed session.

The important adaptive behavior is that the agent does not continue after a failed search. It also treats an empty wardrobe differently from a broken LLM call: an empty wardrobe still produces a useful result and continues through the loop.

## State Management

The agent stores everything for one user turn in a single session dict. The main fields are:

- `query`: the original natural-language request.
- `parsed`: the extracted `description`, `size`, and `max_price`.
- `search_results`: the ranked list returned by `search_listings()`.
- `selected_item`: the exact top listing chosen from `search_results`.
- `wardrobe`: the wardrobe selected in the UI.
- `outfit_suggestion`: the string returned by `suggest_outfit()`.
- `fit_card`: the final caption returned by `create_fit_card()`.
- `error`: an early-stop message if any step fails.

State is passed forward directly:
- `parsed` feeds `search_listings()`.
- `selected_item` from search is passed into `suggest_outfit()`.
- `outfit_suggestion` and the same `selected_item` are passed into `create_fit_card()`.

The tests in [tests/test_agent.py](/Users/ruizhang/Desktop/career/codepath/AI201_Su26/Week2/ai201-project2-fitfindr-starter/tests/test_agent.py:13) verify that the same selected item object is reused across steps rather than being rebuilt or re-entered.

## Error Handling Strategy

### `search_listings` failure mode: no results

Behavior:
- The tool returns `[]` instead of crashing.
- The agent stops before calling the LLM tools.

Concrete example:
- Query: `"designer ballgown size XXS under $5"`
- Agent response:
  `"I couldn't find any listings for designer ballgown with size XXS and under $5. Try broader keywords, a higher budget, or removing the size filter."`

### `suggest_outfit` failure mode: empty wardrobe

Behavior:
- This is handled as a graceful fallback, not a hard failure.
- The tool returns general styling advice instead of wardrobe-specific pairings.

Concrete example:
- Example query in the app:
  `"vintage graphic tee under $30"` with wardrobe choice `"Empty wardrobe (new user)"`
- Expected behavior:
  the tool should suggest bottoms, shoes, and layers that work with the thrifted piece even though no saved wardrobe items exist.

### `create_fit_card` failure mode: missing or incomplete outfit input

Behavior:
- The tool returns a descriptive string instead of raising an exception.

Concrete example:
- Direct test case:
  `create_fit_card("", new_item)`
- Returned message:
  `"I couldn't generate a fit card because the outfit description was empty or incomplete."`

## Testing

I tested the tools in isolation first, then tested the planning loop separately.

Tool tests in [tests/test_tools.py](/Users/ruizhang/Desktop/career/codepath/AI201_Su26/Week2/ai201-project2-fitfindr-starter/tests/test_tools.py:39) cover:
- search success
- zero-result search
- price filtering
- flexible size matching
- empty wardrobe behavior
- LLM failure handling in `suggest_outfit()`
- empty outfit handling in `create_fit_card()`
- LLM failure handling in `create_fit_card()`

Planning loop tests in [tests/test_agent.py](/Users/ruizhang/Desktop/career/codepath/AI201_Su26/Week2/ai201-project2-fitfindr-starter/tests/test_agent.py:13) cover:
- state flowing from `search_listings()` to `suggest_outfit()` to `create_fit_card()`
- early return when search returns no results
- blank query handling in the UI
- formatting of the UI output panels

I used mocks for the LLM-backed unit tests so the test suite can verify agent behavior without depending on a live network call.

## Spec Reflection

One way the spec helped:
Writing `planning.md` first made the control flow much easier to implement. The planning loop section was detailed enough that `run_agent()` became a direct translation of the spec instead of a guess.

One way implementation diverged from the spec:
The spec described the planning loop as a simple sequence, but the final code needed more query-parsing cleanup than I originally expected. I added regex-based parsing helpers to strip phrases like `"I'm looking for"` and extract cleaner `size` and `max_price` values so the search tool would behave consistently.

## AI Usage Transparency

### Instance 1: implementing `search_listings()`

I used Codex with the Tool 1 section from `planning.md` as the prompt context. I asked it to implement `search_listings()` using `load_listings()` from `utils/data_loader.py`, with size filtering, price filtering, and relevance ranking.

What I reviewed and changed:
- I checked that the function kept the exact signature from the spec.
- I verified that no-results returns `[]` instead of throwing an exception.
- I kept the ranking logic but added explicit helper functions for tokenization, size normalization, and scoring so the behavior was easier to test.

### Instance 2: implementing the planning loop in `agent.py`

I used Codex with the Planning Loop, State Management, Error Handling, and Architecture sections from `planning.md`. I asked it to wire the three tools through a session dict and stop early when search fails.

What I reviewed and changed:
- I checked that later tools were not called when `search_listings()` returned an empty list.
- I verified that the same `selected_item` object moved from search to outfit generation to fit card generation.
- I revised the first version of the query parser after a test failure showed it was preserving an extra leading `"a"` in the description and over-capturing size text in a no-results query.

### Instance 3: implementing and tightening the test suite

I used Codex to draft pytest tests for both the tools and the planning loop. I then revised the test setup so the tests could import project modules correctly from the `tests/` directory and so the LLM calls were mocked instead of hitting the live API.

What I reviewed and changed:
- I added a project-root `sys.path` setup in the tests after pytest initially failed to import `tools`.
- I used fake Groq client objects to test the LLM-backed tools deterministically.
- I reran the suite after each fix until all tests passed.

## Notes

The app includes clickable examples for both normal flows and Milestone 5 failure-mode checks in [app.py](/Users/ruizhang/Desktop/career/codepath/AI201_Su26/Week2/ai201-project2-fitfindr-starter/app.py:78).

Live LLM-backed outfit generation and fit-card creation depend on a working Groq API key and, if needed in your environment, a working proxy configuration. The automated tests validate the logic and failure handling paths with mocked LLM responses.
