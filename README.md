# Anki Auto Dictionary Augmenter

This script enriches Anki vocabulary cards by fetching definitions and examples from Wiktionary and appending them to the back of existing notes. It supports both English and Spanish decks via AnkiConnect.

---

## Features

* Uses AnkiConnect (no direct database access)
* Fetches definitions from Wiktionary
* Adds:

  * English definitions + optional example sentences (English deck)
  * English gloss + part of speech + optional example (Spanish deck)
* Appends formatted HTML to existing card back fields
* Tags processed cards to prevent duplicate processing
* Rate-limited requests (1s delay between lookups)
* Dry-run mode for safe testing
* Failure tagging for missing or problematic entries

---

## Requirements

### 1. Anki + AnkiConnect

Install the AnkiConnect add-on in Anki:

https://ankiweb.net/shared/info/2055492159

Ensure Anki is running before executing the script.

Default endpoint:

```
http://localhost:8765
```

---

### 2. Python dependencies

Install required packages:

```bash
pip install requests wiktionaryparser
```

---

## Deck Setup

The script expects two decks:

* `English Vocabulary`
* `Spanish Vocabulary`

Each note type must include:

* `Front` (word)
* `Back` (existing content to be appended)

---

## Tags Used

* `auto-defined-en` → English deck processed notes
* `auto-defined-es` → Spanish deck processed notes
* `auto-define-failed` → lookup failures or parsing errors

---

## Usage

### Dry run (recommended first)

```bash
python anki_define.py --dry-run
```

Shows what would be updated without modifying Anki.

---

### Live run

```bash
python anki_define.py
```

Processes both decks automatically.

---

## Behavior

### English cards

Appends:

* First Wiktionary definition
* Optional example sentence

### Spanish cards

Appends:

* English gloss (first available meaning)
* Part of speech (if available)
* Optional Spanish example sentence

---

## Rate limiting

* 1 second delay between Wiktionary requests
* Prevents excessive requests and improves stability

---

## Failure handling

If a word cannot be resolved via Wiktionary:

* The note is tagged with:

  ```
  auto-define-failed
  ```
* Processing continues for remaining notes

---

## Notes

* Existing content in the `Back` field is preserved and appended to
* Only notes not already tagged are processed
* Wiktionary structure varies; some entries may lack examples or clean definitions
* Spanish gloss extraction depends on Wiktionary formatting and may require tuning

---

## Safety / Recommendations

* Always run `--dry-run` first
* Test on a small subset of cards before bulk processing
* Review failed-tagged notes periodically

---

## Future improvements

Possible extensions:

* Better Spanish semantic extraction
* Support for multiple definitions per card
* OpenAI fallback for missing examples
* GUI or CLI progress UI
* Caching to reduce repeated lookups

