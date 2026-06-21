#!/usr/bin/env python3

import requests
import concurrent.futures as futures
from bs4 import BeautifulSoup
import time
import re
import humanize, datetime
import os
import sys

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen3.5:9b"

ANKI_CONNECT = "http://localhost:8765"


# -----------------------------
# Anki Connect — find notes only
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


# -----------------------------
# Fetching
# -----------------------------
def fetch(url):
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        return {
            "url": url,
            "status": r.status_code,
            "html": r.text if r.status_code == 200 else ""
        }
    except Exception as e:
        return {"url": url, "status": 0, "html": "", "error": str(e)}


def fetch_all(urls):
    with futures.ThreadPoolExecutor(max_workers=6) as ex:
        return list(ex.map(fetch, urls))


# -----------------------------
# Generic extraction (no brittle CSS)
# -----------------------------
def extract_text(html):
    if not html:
        return ""

    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text("\n", strip=True)

    # collapse noise
    text = re.sub(r"\n{2,}", "\n", text)

    return text[:12000]  # keep bounded


# -----------------------------
# Ollama normalization
# -----------------------------
def ollama_batch(word_payload):
    prompt = """
You are a dictionary normalization engine.

You will receive dictionary excerpts from multiple sources for a single word.

Rules:
- Use ONLY provided text
- Do NOT invent meanings
- Return up to 5 senses
- Exclude < and > in your responses - they mark where you enter information
- If there is no suitable example, exclude the "example: " line
- Examples MUST be in the same language as the word itself
- Keep format EXACT:

1. <definition>
   example: <example or blank>

2. <definition>
   example: <example or blank>

If no usable definition:
NO_DEFINITION

-------------------------
"""

    prompt += word_payload

    start = time.time()
    r = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.2,
            "think": False
        },
        timeout=60 * 60,
    )
    end = time.time()
    elapsed = humanize.naturaldelta(datetime.timedelta(seconds=end - start))
    print(f"{OLLAMA_MODEL} took {elapsed}")

    return r.json()["response"]


# -----------------------------
# Source routing
# -----------------------------
def get_sources(word, lang):
    if lang == "es":
        return [
            f"https://www.spanishdict.com/translate/{word}",
            f"https://dle.rae.es/{word}",
            f"https://en.wiktionary.org/wiki/{word}",
            f"https://www.wordreference.com/es/en/translation.asp?spen={word}"
        ]
    else:
        return [
            f"https://en.wiktionary.org/wiki/{word}",
            f"https://www.wordreference.com/enes/{word}"
        ]


# -----------------------------
# Build LLM payload
# -----------------------------
def build_payload(word, fetched, lang):
    payload = [f"\nWORD: {word}\n"]

    for f in fetched:
        if f.get("status") == 200:
            text = extract_text(f["html"])
            payload.append(f"SOURCE: {f['url']}\n{text}\n")

    os.makedirs(f"./output/{lang}", exist_ok=True)
    with open(f"./output/{lang}/{word}.original.txt", "w") as f:
        f.write("".join(payload))

    return "\n".join(payload)


# -----------------------------
# Generate LLM definitions and write files
# -----------------------------
def process_word(word, lang):
    print(f"\nProcessing: {word}")

    # Check cache for fetched (original) data
    original_cache = f"./output/{lang}/{word}.original.txt"
    if os.path.exists(original_cache):
        print(f"  [cached] reading {original_cache}")
        with open(original_cache) as f:
            payload = f.read()
    else:
        urls = get_sources(word, lang)
        fetched = fetch_all(urls)
        payload = build_payload(word, fetched, lang)

    # Check cache for LLM output
    llm_cache = f"./output/{lang}/{word}.llm.txt"
    if os.path.exists(llm_cache):
        print(f"  [cached] reading {llm_cache}")
        with open(llm_cache) as f:
            llm_output = f.read()
    else:
        llm_output = ollama_batch(payload)
        os.makedirs(f"./output/{lang}", exist_ok=True)
        with open(llm_cache, "w") as f:
            f.write(llm_output)

    print(f"  Done — LLM output written to {llm_cache}")


# -----------------------------
# Run over Anki deck
# -----------------------------
def run(deck, lang):
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

        process_word(word, lang)


if __name__ == "__main__":
    check_anki_connection()
    run("English Vocabulary", "en")
    run("Spanish Vocabulary", "es")