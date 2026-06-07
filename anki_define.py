#!/usr/bin/env python3

import argparse
import html
import time
from typing import Optional

import requests
from wiktionaryparser import WiktionaryParser


ANKI_CONNECT_URL = "http://localhost:8765"

ENGLISH_DECK = "English Vocabulary"
SPANISH_DECK = "Spanish Vocabulary"

ENGLISH_TAG = "auto-defined-en"
SPANISH_TAG = "auto-defined-es"
FAILED_TAG = "auto-define-failed"

RATE_LIMIT_SECONDS = 1


parser = WiktionaryParser()


def anki(action, **params):
    response = requests.post(
        ANKI_CONNECT_URL,
        json={
            "action": action,
            "version": 6,
            "params": params,
        },
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()

    if data["error"] is not None:
        raise RuntimeError(data["error"])

    return data["result"]


def find_notes(query: str):
    return anki("findNotes", query=query)


def notes_info(note_ids):
    return anki("notesInfo", notes=note_ids)


def update_note_fields(note_id, fields):
    return anki(
        "updateNoteFields",
        note={
            "id": note_id,
            "fields": fields,
        },
    )


def add_tags(note_ids, tags):
    return anki(
        "addTags",
        notes=note_ids,
        tags=tags,
    )


def get_first_definition(word: str, language: str):
    """
    Returns:
        {
            "definition": str,
            "example": str | None,
            "part_of_speech": str | None,
        }
    """

    results = parser.fetch(word, language)

    if not results:
        return None

    for entry in results:
        definitions = entry.get("definitions", [])

        for definition_block in definitions:
            text_list = definition_block.get("text", [])

            if len(text_list) < 2:
                continue

            definition = text_list[1].strip()
            example = None

            examples = definition_block.get("examples", [])
            if examples:
                example = examples[0].strip()

            return {
                "definition": definition,
                "example": example,
                "part_of_speech": definition_block.get("partOfSpeech"),
            }

    return None


def build_english_html(data):
    parts = [
        "<hr>",
        '<div class="auto-definition">',
        "<b>Definition</b><br>",
        html.escape(data["definition"]),
    ]

    if data["example"]:
        parts.extend(
            [
                "<br><br>",
                "<b>Example</b><br>",
                html.escape(data["example"]),
            ]
        )

    parts.extend(
        [
            "<br><br>",
            "<small>Source: Wiktionary</small>",
            "</div>",
        ]
    )

    return "".join(parts)


def build_spanish_html(data):
    parts = [
        "<hr>",
        '<div class="auto-definition">',
        "<b>English</b><br>",
        html.escape(data["definition"]),
    ]

    if data["part_of_speech"]:
        parts.extend(
            [
                "<br><br>",
                "<b>Part of Speech</b><br>",
                html.escape(data["part_of_speech"]),
            ]
        )

    if data["example"]:
        parts.extend(
            [
                "<br><br>",
                "<b>Example (Spanish)</b><br>",
                html.escape(data["example"]),
            ]
        )

    parts.extend(
        [
            "<br><br>",
            "<small>Source: Wiktionary</small>",
            "</div>",
        ]
    )

    return "".join(parts)


def process_deck(
    deck_name: str,
    tag_name: str,
    language: str,
    dry_run: bool,
):
    query = f'deck:"{deck_name}" -tag:{tag_name}'

    note_ids = find_notes(query)

    print(f"\n[{deck_name}] Found {len(note_ids)} notes")

    if not note_ids:
        return

    notes = notes_info(note_ids)

    for note in notes:
        note_id = note["noteId"]

        try:
            word = note["fields"]["Front"]["value"].strip()
            back = note["fields"]["Back"]["value"]

            if not word:
                continue

            print(f"Processing: {word}")

            data = get_first_definition(word, language)

            if not data:
                print("  No definition found")

                if not dry_run:
                    add_tags([note_id], FAILED_TAG)

                continue

            if language == "english":
                addition = build_english_html(data)
            else:
                addition = build_spanish_html(data)

            updated_back = back + addition

            if dry_run:
                print("  DRY RUN")
                print(f"  Definition: {data['definition']}")
            else:
                update_note_fields(
                    note_id,
                    {
                        "Back": updated_back,
                    },
                )

                add_tags([note_id], tag_name)

                print("  Updated")

            time.sleep(RATE_LIMIT_SECONDS)

        except Exception as exc:
            print(f"  ERROR: {exc}")

            if not dry_run:
                try:
                    add_tags([note_id], FAILED_TAG)
                except Exception:
                    pass


def main():
    arg_parser = argparse.ArgumentParser()

    arg_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show changes without modifying Anki",
    )

    args = arg_parser.parse_args()

    process_deck(
        deck_name=ENGLISH_DECK,
        tag_name=ENGLISH_TAG,
        language="english",
        dry_run=args.dry_run,
    )

    process_deck(
        deck_name=SPANISH_DECK,
        tag_name=SPANISH_TAG,
        language="spanish",
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
