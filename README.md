# anki-vocab

Augment Anki vocabulary cards with LLM-curated definitions from multiple online dictionaries.

## Workflow

Two scripts, run in order:

### 1. `anki_define.py` — Generate definitions

Scrapes 2–4 dictionary sources per word, feeds them to a local Ollama model to extract clean definitions, and caches results on disk.

```
python anki_define.py
```

- Targets decks: `English Vocabulary`, `Spanish Vocabulary`
- Sources (EN): Wiktionary, WordReference
- Sources (ES): SpanishDict, RAE, Wiktionary, WordReference
- Model: `qwen3.5:9b` (Ollama, localhost:11434)
- Caches raw scrapes → `./output/{lang}/{word}.original.txt`
- Caches LLM output  → `./output/{lang}/{word}.llm.txt`
- Skips notes already tagged `auto-defined`

### 2. `update_anki.py` — Apply to Anki interactively

Reads cached LLM definitions, prompts you to pick a sense for each word, and appends formatted HTML to the Back field.

```
python update_anki.py
```

- Displays parsed senses with example sentences
- Select by number; `0` to skip
- Appends: `<hr><b>word</b><br>definition<i>example</i>`
- Tags processed notes: `auto-defined-en` / `auto-defined-es`

## Requirements

- **Anki** with [AnkiConnect](https://ankiweb.net/shared/info/2055492167) add-on
- **Ollama** running at `http://localhost:11434` with model `qwen3.5:9b`
- **Python packages:**
  ```
  pip install requests beautifulsoup4 lxml humanize
  ```

## Deck requirements

Each note must have:
- `Front` → vocabulary word
- `Back` → existing content (definitions are appended, never overwritten)

## Tags

| Tag | When |
|---|---|
| `auto-defined-en` | Note updated (English deck) |
| `auto-defined-es` | Note updated (Spanish deck) |

## Cache

All output lives in `./output/{lang}/`. Re-running is idempotent — cached definitions are reused. Delete cache files to force re-generation.