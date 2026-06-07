# Anki Auto Vocabulary Augmenter (WiktAPI-based)

This script enriches Anki vocabulary cards by fetching definitions and example sentences from the WiktAPI service and appending them to existing notes.

It supports separate English and Spanish decks and uses AnkiConnect for safe, local automation.

---

## Features

* Uses AnkiConnect (no direct Anki database access)
* Uses WiktAPI (structured Wiktionary data)
* Supports:

  * English Vocabulary deck
  * Spanish Vocabulary deck
* Appends content to existing Back field (never overwrites)
* Extracts:

  * First definition (gloss)
  * First example sentence (if available)
  * Part of speech (for Spanish + metadata)
* Tags processed notes to prevent duplicate enrichment
* Dry-run mode for safe inspection
* Rate limiting (1 second between requests)
* Automatic normalization (lowercasing input words)

---

## Requirements

### 1. Anki + AnkiConnect

Install AnkiConnect add-on:

https://ankiweb.net/shared/info/2055492159

Ensure Anki is running before executing the script.

Default endpoint:

```
http://localhost:8765
```

---

### 2. Python dependencies

```bash
pip install requests
```

(No additional parsing libraries required anymore.)

---

## Deck Configuration

The script expects two decks:

* `English Vocabulary`
* `Spanish Vocabulary`

Each note must contain:

* `Front` → vocabulary word
* `Back` → existing content to be appended

---

## Tags Used

### Success tags

* `auto-defined-en`
* `auto-defined-es`

### Failure tag

* `auto-define-failed`

Used when:

* no definition is found
* API errors occur

---

## Usage

### Dry run (recommended first)

```bash
python anki_define.py --dry-run
```

Shows what would be added without modifying Anki.

Example output:

```
Processing: insouciant
  DRY RUN
  POS: adjective
  → casually unconcerned
  EX: an insouciant gesture
```

---

### Live run

```bash
python anki_define.py
```

Updates Anki notes and appends enriched content.

---

## Behavior

### Word normalization

All words are normalized before lookup:

* stripped of whitespace
* converted to lowercase

Example:

```
"Insouciant" → "insouciant"
```

---

### English deck behavior

For each word:

* Fetches WiktAPI English definition
* Selects:

  * first sense
  * first gloss (definition)
  * first example (if available)
* Appends formatted HTML to Back field

---

### Spanish deck behavior

For each word:

* Fetches WiktAPI Spanish entry
* Extracts:

  * English gloss
  * part of speech
  * example sentence (if available)
* Appends formatted HTML to Back field

---

## Rate limiting

To avoid excessive API usage:

* 1 second delay between requests

---

## Output format (Anki Back field)

Each note gets appended HTML like:

### English example:

* Definition
* Example sentence
* Source label (WiktAPI)

### Spanish example:

* English gloss
* Part of speech
* Example sentence

---

## Dry-run mode

Dry-run prints:

* word being processed
* part of speech
* selected definition
* example sentence (if present)

No changes are made to Anki.

---

## Failure handling

If lookup fails:

* note is tagged with `auto-define-failed`
* processing continues for remaining notes

---

## Design Notes

### Why WiktAPI

This tool replaces:

* Wiktionary scraping
* wiktionaryparser (deprecated/fragile)
* raw MediaWiki parsing

WiktAPI provides:

* structured JSON
* clean separation of senses
* glosses and examples
* stable API surface

---

## Limitations

* Only first sense is used (no sense ranking)
* Only first example is used
* Some entries may lack examples entirely
* Spanish coverage depends on Wiktionary data completeness

---

## Future improvements

Possible enhancements:

* Sense ranking (frequency-aware selection)
* Multiple examples per card
* Local caching layer
* Pronunciation (IPA) support
* Better Spanish → English disambiguation
* CLI progress bar
* Deduplication of repeated runs

---

## Safety notes

* Always run `--dry-run` first
* Test on a small subset of notes before full deck runs
* WiktAPI is a third-party service; availability may change

