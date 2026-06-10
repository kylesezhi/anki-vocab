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

def choose_sense(word, senses):
    if len(senses) == 1:
        return senses[0]

    print()
    print("=" * 60)
    print(f"Word: {word}")
    print()

    for idx, sense in enumerate(senses, start=1):
        print(f"{idx}. {sense['definition']}")

        if sense.get("example"):
            print()
            print(f"   Example: {sense['example']}")

        print()

    while True:
        choice = input(
            f"Select definition [1-{len(senses)}]: "
        ).strip()

        try:
            selected = int(choice)

            if 1 <= selected <= len(senses):
                return senses[selected - 1]

        except ValueError:
            pass

        print("Invalid choice.")

# -------------------------
# WiktAPI lookup
# -------------------------

def lookup_word(word, lang):
    url = f"https://api.wiktapi.dev/v1/{lang}/word/{word}/definitions"

    r = requests.get(
        url,
        params={"lang": lang},
        timeout=30,
    )

    r.raise_for_status()

    data = r.json()

    definitions = data.get("definitions", [])
    if not definitions:
        return None

    senses_out = []
    seen_definitions = set()

    for definition in definitions:
        pos = definition.get("pos")

        for sense in definition.get("senses", []):
            glosses = sense.get("glosses", [])
            if not glosses:
                continue

            gloss = glosses[0].strip()

            # Deduplicate identical definitions
            if gloss.lower() in seen_definitions:
                continue

            seen_definitions.add(gloss.lower())

            example = None

            examples = sense.get("examples", [])
            if examples:
                first_example = examples[0]

                if isinstance(first_example, dict):
                    example = first_example.get("text")
                else:
                    example = str(first_example)

            senses_out.append({
                "pos": pos,
                "definition": gloss,
                "example": example,
            })

    if not senses_out:
        return None

    return senses_out

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
# HTML builder
# -------------------------

def build_html(data):
    parts = [
        "<hr>",
        '<div class="auto-definition">',
    ]

    if data.get("pos"):
        parts += [
            "<b>Part of speech</b><br>",
            html.escape(data["pos"]),
            "<br><br>",
        ]

    parts += [
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

            senses = lookup_word(word, lang)

            if not senses:
                print("  No definition found")

                if not dry_run:
                    add_tags([note_id], FAIL_TAG)

                continue

            data = choose_sense(word, senses)
            addition = build_html(data)
            new_back = back + addition

            if dry_run:
                print("  DRY RUN")

                if data.get("pos"):
                    print(f"  POS: {data['pos']}")

                print(f"  DEF: {data['definition']}")

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
