# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the local `data/listings.json` dataset for secondhand items that match the user's description and optional filters. It filters by size and price first, then ranks the remaining listings by keyword overlap across fields like `title`, `description`, `category`, and `style_tags`.

**Input parameters:**
- `description` (str): The main item the user wants, such as `"vintage graphic tee"` or `"90s track jacket"`.
- `size` (str): An optional size filter such as `"M"`, `"S/M"`, `"W30"`, or `"US 8"`. Matching should be case-insensitive and flexible enough to handle values like `"S/M"` or `"M/L"`.
- `max_price` (float): An optional maximum price in dollars. Only listings priced at or below this amount should be returned.

**What it returns:**
A `list[dict]` sorted from most relevant to least relevant. Each listing dict contains the dataset fields:
`id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.
The agent will use the first item in this list as `selected_item`.

**What happens if it fails or returns nothing:**
If no listings match, the tool returns an empty list instead of raising an exception. The agent stores a helpful message in `session["error"]`, tells the user no results were found for the current constraints, suggests broadening the description or increasing the budget, and stops without calling `suggest_outfit` or `create_fit_card`.

---

### Tool 2: suggest_outfit

**What it does:**
Uses the selected thrift listing plus the user's wardrobe to generate 1 to 2 outfit ideas. When the wardrobe has items, it should reference specific pieces by name; when the wardrobe is empty, it should fall back to general styling advice for the new item.

**Input parameters:**
- `new_item` (dict): The listing chosen from `search_listings`. It includes the listing's title, description, size, price, colors, style tags, platform, and other metadata.
- `wardrobe` (dict): A wardrobe object with an `items` list. Each wardrobe item includes `id`, `name`, `category`, `colors`, `style_tags`, and optional `notes`.

**What it returns:**
A non-empty `str` containing either:
1. Specific outfit combinations using named wardrobe pieces from `wardrobe["items"]`, or
2. General styling advice if `wardrobe["items"]` is empty.

The output should mention concrete pairings and a clear vibe instead of generic praise.

**What happens if it fails or returns nothing:**
If the wardrobe is empty, the tool should not fail. It should return general advice such as what bottoms, shoes, or layers would work with the new item, and the agent should continue to `create_fit_card`. If the LLM call fails or returns a blank string, the agent stores an error like `"I found a listing, but I couldn't build an outfit idea right now."` and stops before the fit card step.

---

### Tool 3: create_fit_card

**What it does:**
Turns the outfit suggestion and selected listing into a short social-style caption. The caption should sound like a human outfit post, mention the item naturally, and reflect the vibe of the suggested look rather than sounding like a product description.

**Input parameters:**
- `outfit` (str): The outfit suggestion returned by `suggest_outfit`. This is the styling context the caption should reflect.
- `new_item` (dict): The same selected listing dict used in the outfit step so the caption can mention the item title, price, and resale platform naturally.

**What it returns:**
A `str` of about 2 to 4 sentences that works like an Instagram or TikTok caption. It should mention the thrifted item, include the price and platform once each, and capture the mood of the outfit in a casual voice.

**What happens if it fails or returns nothing:**
If `outfit` is empty, whitespace-only, or obviously incomplete, the tool should return an error message string instead of crashing. The agent should surface that message to the user and not pretend the fit card succeeded.

---

### Additional Tools (if any)

No additional tools are planned yet.

---

## Planning Loop

**How does your agent decide which tool to call next?**
The planning loop is a simple conditional pipeline that changes behavior based on what each step returns.

1. Start a new session dict with keys for `query`, `parsed`, `search_results`, `selected_item`, `wardrobe`, `outfit_suggestion`, `fit_card`, and `error`.
2. Parse the natural-language query into:
   `description` as the requested item,
   `size` if a size phrase such as `"size M"` or `"US 8"` appears,
   `max_price` if a price phrase such as `"under $30"` appears.
3. Call `search_listings(description, size, max_price)`.
4. Check `search_results`.
   If the list is empty, set `session["error"]` to a helpful no-results message and return the session immediately.
   If the list is not empty, set `session["selected_item"] = session["search_results"][0]`.
5. Call `suggest_outfit(session["selected_item"], session["wardrobe"])`.
6. Check `outfit_suggestion`.
   If it is blank or the tool failed to produce usable text, set `session["error"]` and return early.
   If the wardrobe was empty but the tool returned general styling advice, treat that as a valid success and continue.
7. Call `create_fit_card(session["outfit_suggestion"], session["selected_item"])`.
8. Check `fit_card`.
   If the tool returned an error-style message because the outfit input was incomplete, surface that message to the user in the session result.
   Otherwise, return the completed session with listing, outfit suggestion, and fit card.
9. The loop is done when either:
   an error causes an early return, or
   all three tools finish successfully and `fit_card` is populated.

---

## State Management

**How does information from one tool get passed to the next?**
The agent keeps all per-request data inside one session dict so every later step can read what earlier steps produced. The most important state fields are:

- `query`: the original user request.
- `parsed`: the extracted `description`, `size`, and `max_price`.
- `search_results`: the full ranked result list from `search_listings`.
- `selected_item`: the top listing chosen from `search_results`.
- `wardrobe`: the wardrobe dict selected by the UI, either `get_example_wardrobe()` or `get_empty_wardrobe()`.
- `outfit_suggestion`: the text returned by `suggest_outfit`.
- `fit_card`: the final caption returned by `create_fit_card`.
- `error`: a message explaining why the run ended early.

State flows in one direction through the session:
the parsed query drives `search_listings`,
the chosen `selected_item` feeds `suggest_outfit`,
the resulting `outfit_suggestion` plus the same `selected_item` feed `create_fit_card`.
Because the exact same dict objects are stored and reused, the user never has to re-enter the selected item or outfit details between steps.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | The agent returns early with a message like: `"I couldn't find any listings for a vintage graphic tee under $30 with those filters. Try raising the price limit, removing the size filter, or using broader keywords."` It does not call the next two tools. |
| suggest_outfit | Wardrobe is empty | The tool returns general styling advice instead of closet-specific pairings. The agent tells the user something like: `"I found a listing, and since your wardrobe is empty, I'll suggest a few general ways to style it."` Then it continues to the fit card step. |
| create_fit_card | Outfit input is missing or incomplete | The tool returns a descriptive error string. The agent surfaces it directly, such as: `"I found an item, but I couldn't generate the final fit card because the outfit description was incomplete. Please rerun after the outfit step succeeds."` |

---

## Architecture

```text
User query + wardrobe choice
    │
    ▼
Planning Loop / run_agent() --------------------------------------------------------┐
    │                                                                               │
    ├─► Session initialized                                                         │
    │      query = original user request                                            │
    │      wardrobe = get_example_wardrobe() or get_empty_wardrobe()                │
    │      parsed = {}                                                              │
    │      search_results = []                                                      │
    │      selected_item = None                                                     │
    │      outfit_suggestion = None                                                 │
    │      fit_card = None                                                          │
    │      error = None                                                             │
    │                                                                               │
    ├─► Parse query                                                                 │
    │      extract description, size, max_price                                     │
    │      Session: parsed = {                                                      │
    │          "description": "...",                                                │
    │          "size": "..." or None,                                               │
    │          "max_price": ... or None                                             │
    │      }                                                                        │
    │                                                                               │
    ├─► search_listings(description, size, max_price)                               │
    │       │                                                                       │
    │       ├──► results = []                                                       │
    │       │      Session: error = "No listings found for those filters.           │
    │       │                       Try broader keywords, a higher budget,          │
    │       │                       or no size filter."                             │
    │       │      └──► return session early                                        │
    │       │                                                                       │
    │       └──► results = [item, ...]                                              │
    │              Session: search_results = results                                │
    │              Session: selected_item = results[0]                              │
    │                                                                               │
    ├─► suggest_outfit(selected_item, wardrobe)                                     │
    │       │                                                                       │
    │       ├──► wardrobe["items"] is empty                                         │
    │       │      return general styling advice for the new item                   │
    │       │                                                                       │
    │       ├──► outfit response is blank / tool fails                              │
    │       │      Session: error = "I found a listing, but I couldn't build        │
    │       │                       an outfit idea right now."                      │
    │       │      └──► return session early                                        │
    │       │                                                                       │
    │       └──► outfit response is usable                                          │
    │              Session: outfit_suggestion = "Pair this with ..."                │
    │                                                                               │
    └─► create_fit_card(outfit_suggestion, selected_item)                           │
            │                                                                       │
            ├──► outfit input missing / incomplete                                  │
            │      Session: error = "I couldn't generate the final fit card         │
            │                       because the outfit description was incomplete." │
            │      └──► return session                                              │
            │                                                                       │
            └──► fit card created successfully                                      │
                   Session: fit_card = "Found this on Depop for $24 ..."            │
                   │                                                                │
                   └──► Return completed session -----------------------------------┘
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**
I will use ChatGPT or Codex one tool at a time instead of asking for the whole project at once.

For `search_listings`, I will give the AI the Tool 1 section from this file plus the note that it must use `load_listings()` from `utils/data_loader.py`. I expect it to produce the function body for `search_listings()` in `tools.py`. Before trusting it, I will verify that it keeps the exact function signature, filters by both optional inputs, ranks by relevance, and returns `[]` on no results instead of raising an exception.

For `suggest_outfit`, I will give the AI the Tool 2 section, the Error Handling row for an empty wardrobe, and the relevant wardrobe fields from `wardrobe_schema.json`. I expect it to produce a Groq-powered implementation that references named wardrobe items when present and falls back to general styling advice when `wardrobe["items"]` is empty. I will verify that it handles both example and empty wardrobes without crashing.

For `create_fit_card`, I will give the AI the Tool 3 section and the style requirements from this file. I expect it to produce a function that guards against empty outfit text and generates a short caption with the listing title, price, and platform. I will verify that the guard clause works and that repeated runs can vary in tone instead of returning the same caption every time.

**Milestone 4 — Planning loop and state management:**
I will give the AI the Planning Loop, State Management, Error Handling, Architecture, and A Complete Interaction sections from this file. I expect it to produce the `run_agent()` logic in `agent.py` and, if needed later, the UI mapping in `app.py`.

Before using that code, I will check that:
- the session keys match this spec,
- the agent returns early when `search_listings` finds nothing,
- the same `selected_item` object is passed into `suggest_outfit`,
- the `outfit_suggestion` is passed into `create_fit_card`,
- the agent does not call later tools after an earlier failure.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

FitFindr needs to turn one natural-language thrift request into a full styling workflow. First it finds a relevant resale listing, then it decides how that item fits with the user's wardrobe, and finally it turns the result into a shareable fit card. If search fails, the flow stops early with a specific suggestion for how to broaden the request; if the wardrobe is empty, the agent still continues by switching from closet-based pairing to general styling advice.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The agent starts a new session and parses the query. It extracts:
`description = "vintage graphic tee"`,
`size = None`,
`max_price = 30.0`.
Then it calls:
`search_listings("vintage graphic tee", size=None, max_price=30.0)`.

Based on the mock dataset, one strong match is `lst_006`, `"Graphic Tee — 2003 Tour Bootleg Style"`, which is a top listing because its title, description, and style tags all overlap with `graphic tee`, `vintage`, and `grunge/streetwear`, and its price is `$24`.

**Step 2:**
`search_listings` returns a ranked list of matching listing dicts, and the agent stores the first one as `session["selected_item"]`.
Next it calls:
`suggest_outfit(new_item=session["selected_item"], wardrobe=get_example_wardrobe())`.

An expected outfit suggestion could be:
`"Pair the faded graphic tee with your baggy straight-leg jeans and chunky white sneakers for an easy vintage streetwear base. Throw on the vintage black denim jacket and finish with the black crossbody bag. If you want a slightly sharper version, swap in the wide-leg khaki trousers and brown leather belt."`

**Step 3:**
The agent stores that text in `session["outfit_suggestion"]` and calls:
`create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])`.

An expected fit card could be:
`"Found this faded bootleg-style graphic tee on Depop for $24 and it was exactly the kind of worn-in piece I was hoping for. Styled it with my baggy dark-wash jeans, chunky sneakers, and a black denim jacket for a laid-back 90s thrift run vibe. Definitely one of those finds that makes the whole outfit feel easy."`

**Final output to user:**
The user sees three pieces of output:
1. A readable summary of the top listing, including the title, price, size, condition, and platform.
2. An outfit suggestion that references their actual wardrobe pieces.
3. A short fit card caption they could post or share.
