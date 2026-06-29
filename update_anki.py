#!/usr/bin/env python3

import sys
import os
import re
import requests

ANKI_CONNECT = "http://localhost:8765"


# -----------------------------
# Anki Connect
# -----------------------------
def check_anki_connection():
    try:
        r = requests.post(
            ANKI_CONNECT,
            json={"action": "version", "version": 6},
            timeout=3
        )

        r.raise_for_status()
        data = r.json()

        if "result" not in data:
            raise RuntimeError("Invalid AnkiConnect response")

        print(f"[OK] AnkiConnect running (version {data['result']})")

    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Cannot connect to AnkiConnect.")
        print("→ Is Anki open?")
        print("→ Is the AnkiConnect add-on installed?")
        print("→ Expected endpoint: http://localhost:8765\n")
        sys.exit(1)

    except requests.exceptions.Timeout:
        print("\n[ERROR] AnkiConnect is not responding (timeout).")
        print("→ Anki may be frozen or still starting.\n")
        sys.exit(1)

    except Exception as e:
        print("\n[ERROR] Unexpected AnkiConnect failure:")
        print(str(e))
        print("\n→ Check Anki + AnkiConnect add-on\n")
        sys.exit(1)


def anki_find_notes(deck):
    payload = {
        "action": "findNotes",
        "version": 6,
        "params": {"query": f'deck:"{deck}"'}
    }
    r = requests.post(ANKI_CONNECT, json=payload)
    return r.json()["result"]


def anki_get_notes(note_ids):
    payload = {
        "action": "notesInfo",
        "version": 6,
        "params": {"notes": note_ids}
    }
    r = requests.post(ANKI_CONNECT, json=payload)
    return r.json()["result"]


def anki_update_note(note):
    # Flatten field values: AnkiConnect expects plain strings, not {value, order} objects
    fields = {
        k: (v["value"] if isinstance(v, dict) else v)
        for k, v in note["fields"].items()
    }
    payload = {
        "action": "updateNoteFields",
        "version": 6,
        "params": {
            "note": {
                "id": note["noteId"],
                "fields": fields
            }
        }
    }
    r = requests.post(ANKI_CONNECT, json=payload)
    result = r.json()
    if result.get("error"):
        print(f"  [ERROR] AnkiConnect: {result['error']}")


def anki_add_tag(note_id, tag):
    payload = {
        "action": "addTags",
        "version": 6,
        "params": {"notes": [note_id], "tags": tag}
    }
    requests.post(ANKI_CONNECT, json=payload)


# -----------------------------
# Sense parsing
# -----------------------------
def parse_senses(block):
    if "NO_DEFINITION" in block:
        return []

    senses = []
    lines = block.splitlines()

    for line in lines:
        if re.match(r"^\d+\.", line.strip()):
            senses.append({"definition": line.split(".", 1)[1].strip(), "example": ""})
        elif "example:" in line.lower() and senses:
            senses[-1]["example"] = line.split(":", 1)[1].strip()

    return senses


# -----------------------------
# Interactive sense selection
# -----------------------------
def select_sense(word, lang):
    llm_cache = f"./output/{lang}/{word}.llm.txt"

    if not os.path.exists(llm_cache):
        print(f"  [skipped] {llm_cache} not found — run define_words.py first")
        return None

    with open(llm_cache) as f:
        llm_output = f.read()

    senses = parse_senses(llm_output)

    if not senses:
        print(f"  No definition found for '{word}'")
        return None

    print(f"\nSenses for '{word}':")
    for i, s in enumerate(senses):
        print(f"  {i+1}. {s['definition']}")
        if s["example"]:
            print(f"     e.g. {s['example']}")

    while True:
        choice = input("\nSelect sense(s) (e.g. 1,3, or 0 to skip, or q to quit): ").strip()

        if choice.lower() in ("q", "quit"):
            print("Quitting.")
            sys.exit(0)

        if choice == "0":
            return None

        # Parse comma-delimited numbers
        parts = [p.strip() for p in choice.split(",") if p.strip()]
        indices = []
        valid = True
        for p in parts:
            if not p.isdigit():
                valid = False
                break
            idx = int(p)
            if idx < 1 or idx > len(senses):
                valid = False
                break
            indices.append(idx)

        if not valid or not indices:
            print(f"  Invalid input. Enter numbers between 1 and {len(senses)}, comma-separated (e.g. 1,3).")
            continue

        # Deduplicate while preserving order
        seen = set()
        unique_indices = []
        for idx in indices:
            if idx not in seen:
                seen.add(idx)
                unique_indices.append(idx)

        selected = [senses[i - 1] for i in unique_indices]
        return selected


# -----------------------------
# Run over Anki deck
# -----------------------------
def run(deck, lang, field_name="Back"):
    note_ids = anki_find_notes(deck)
    notes = anki_get_notes(note_ids)

    print(f"[{deck}] Found {len(notes)} notes")

    for note in notes:
        fields = note["fields"]

        if any("auto-defined" in tag for tag in note.get("tags", [])):
            continue

        word = fields.get("Front", {}).get("value", "").strip()
        if not word:
            continue

        results = select_sense(word, lang)

        if not results:
            continue

        existing = fields[field_name]["value"]

        for result in results:
            new_text = existing + f"<hr><b>{word}</b><br>{result['definition']}"

            if result["example"]:
                new_text += f"<br><i>{result['example']}</i>"

            existing = new_text

        fields[field_name]["value"] = existing

        anki_update_note(note)
        anki_add_tag(note["noteId"], "auto-defined-" + lang)

        print("  Updated ✔")


if __name__ == "__main__":
    check_anki_connection()
    run("English Vocabulary", "en")
    run("Spanish Vocabulary", "es")