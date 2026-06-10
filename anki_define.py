#!/usr/bin/env python3

import sys
import argparse
import html
import time
import requests

ANKI_CONNECT_URL = "http://localhost:8765"

ENGLISH_DECK = "English Vocabulary"
SPANISH_DECK = "Spanish Vocabulary"

EN_TAG = "auto-defined-en"
ES_TAG = "auto-defined-es"
FAIL_TAG = "auto-define-failed"

RATE_LIMIT_SECONDS = 1


# -------------------------
# AnkiConnect helpers
# -------------------------

def anki(action, **params):
    try:
        r = requests.post(
            ANKI_CONNECT_URL,
            json={"action": action, "version": 6, "params": params},
            timeout=5,
        )

        r.raise_for_status()

    except requests.exceptions.ConnectionError:
        print(
            "\nERROR: Cannot connect to AnkiConnect.\n"
            "\n"
            "Make sure:\n"
            "  1. Anki is running\n"
            "  2. The AnkiConnect add-on is installed\n"
            "  3. AnkiConnect is listening on http://localhost:8765\n"
        )
        sys.exit(1)

    except requests.exceptions.Timeout:
        print(
            "\nERROR: Timed out waiting for AnkiConnect.\n"
            "Is Anki currently starting up or frozen?\n"
        )
        sys.exit(1)

    data = r.json()

    if data.get("error"):
        raise RuntimeError(data["error"])

    return data["result"]

def find_notes(query):
    return anki("findNotes", query=query)


def notes_info(note_ids):
    return anki("notesInfo", notes=note_ids)


def update_note(note_id, fields):
    return anki(
        "updateNoteFields",
        note={"id": note_id, "fields": fields},
    )


def add_tags(note_ids, tag):
    return anki("addTags", notes=note_ids, tags=tag)


# -------------------------
# WiktAPI lookup
# -------------------------

def lookup_word(word, lang):
    url = f"https://api.wiktapi.dev/v1/{lang}/word/{word}/definitions"

    r = requests.get(url, timeout=30)
    r.raise_for_status()

    data = r.json()

    definitions = data.get("definitions", [])
    if not definitions:
        return None

    first_def = definitions[0]
    senses = first_def.get("senses", [])

    if not senses:
        return None

    sense = senses[0]

    glosses = sense.get("glosses", [])
    if not glosses:
        return None

    return {
        "pos": first_def.get("pos"),
        "definition": glosses[0],
        "example": _extract_example(sense),
    }


def _extract_example(sense):
    examples = sense.get("examples", [])
    if not examples:
        return None

    first = examples[0]

    # API returns objects like {"text": "..."}
    if isinstance(first, dict):
        return first.get("text")

    return str(first)


# -------------------------
# HTML builders
# -------------------------

def build_en_html(data):
    parts = [
        "<hr>",
        '<div class="auto-definition">',
        "<b>Definition</b><br>",
        html.escape(data["definition"]),
    ]

    if data.get("example"):
        parts += [
            "<br><br>",
            "<b>Example</b><br>",
            html.escape(data["example"]),
        ]

    parts += [
        "<br><br>",
        "<small>Source: WiktAPI</small>",
        "</div>",
    ]

    return "".join(parts)


def build_es_html(data):
    parts = [
        "<hr>",
        '<div class="auto-definition">',
        "<b>English gloss</b><br>",
        html.escape(data["definition"]),
    ]

    if data.get("pos"):
        parts += [
            "<br><br>",
            "<b>Part of speech</b><br>",
            html.escape(data["pos"]),
        ]

    if data.get("example"):
        parts += [
            "<br><br>",
            "<b>Example</b><br>",
            html.escape(data["example"]),
        ]

    parts += [
        "<br><br>",
        "<small>Source: WiktAPI</small>",
        "</div>",
    ]

    return "".join(parts)


# -------------------------
# Processing
# -------------------------

def process_deck(deck, tag, lang, dry_run):
    query = f'deck:"{deck}" -tag:{tag}'
    note_ids = find_notes(query)

    print(f"\n[{deck}] Found {len(note_ids)} notes")

    notes = notes_info(note_ids)

    for note in notes:
        note_id = note["noteId"]

        try:
            word = note["fields"]["Front"]["value"].strip().lower()
            back = note["fields"]["Back"]["value"]

            if not word:
                continue

            print(f"Processing: {word}")

            data = lookup_word(word, lang)

            if not data:
                print("  No definition found")

                if not dry_run:
                    add_tags([note_id], FAIL_TAG)

                continue

            if lang == "en":
                addition = build_en_html(data)
            else:
                addition = build_es_html(data)

            new_back = back + addition

            if dry_run:
                print("  DRY RUN")
                print(f"  POS: {data.get('pos')}")
                print(f"  → {data['definition']}")

                if data.get("example"):
                    print(f"  EX: {data['example']}")
            else:
                update_note(note_id, {"Back": new_back})
                add_tags([note_id], tag)
                print("  Updated")

            time.sleep(RATE_LIMIT_SECONDS)

        except Exception as e:
            print(f"  ERROR: {e}")

            if not dry_run:
                try:
                    add_tags([note_id], FAIL_TAG)
                except Exception:
                    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    process_deck(ENGLISH_DECK, EN_TAG, "en", args.dry_run)
    process_deck(SPANISH_DECK, ES_TAG, "es", args.dry_run)


if __name__ == "__main__":
    main()
