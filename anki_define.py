#!/usr/bin/env python3

import re
import sys
import argparse
import html
import time
import requests
import unicodedata

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
# Parser for Ollama responses
# -------------------------

def parse_senses(text):
    senses = []

    blocks = re.split(r"\n\s*\d+\.\s", "\n" + text)
    blocks = [b.strip() for b in blocks if b.strip()]

    for b in blocks:
        lines = b.split("\n")
        definition = lines[0].strip()

        example = None
        for line in lines:
            if line.lower().startswith("example:") or line.lower().startswith("ejemplo:"):
                example = line.split(":", 1)[1].strip()

        senses.append({
            "definition": definition,
            "example": example,
        })

    return senses


# -------------------------
# Ollama lookup
# -------------------------

def ollama_lookup(word, lang):
    if lang == "es":
        prompt = f"""
Define the Spanish word: {word}

Return up to 5 senses.

Format:
1. <definición>
   ejemplo: <oración>

2. <definición>
   ejemplo: <oración>

Rules:
- Spanish only
- concise
"""
    else:
        prompt = f"""
Define the English word: {word}

Return up to 5 senses.

Format:
1. <definition>
   example: <sentence>

2. <definition>
   example: <sentence>

Rules:
- concise
"""

    r = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "qwen2.5:7b",
            "prompt": prompt,
            "stream": False,
        },
        timeout=60,
    )

    senses = parse_senses(r.json()["response"])
    return senses if senses else None


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
        "<small>Source: Qwen2.5 (Ollama)</small>",
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
            word = unicodedata.normalize("NFD", note["fields"]["Front"]["value"].strip().lower())
            back = note["fields"]["Back"]["value"]

            if not word:
                continue

            print(f"Processing: {word}")

            senses = ollama_lookup(word, lang)

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