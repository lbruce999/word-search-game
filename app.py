import json
import os
import random
import re
from pathlib import Path

from flask import Flask, jsonify, render_template, request, session


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_WORD_BANK_PATH = BASE_DIR / "words" / "word_bank.json"
FALLBACK_WORD_BANK_PATH = Path.home() / ".word-search-game" / "word_bank.json"
MAX_WORDS = 15
WORD_PATTERN = re.compile(r"^[A-Z]+$")
SUCCESS_MESSAGE = "Bingo! You spelled it right!"
SESSION_KEY = "spelling_round"


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "spelling-round-dev-key")


def parse_word_bank(path):
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    if not isinstance(data, list):
        return []

    words = []
    seen = set()
    for item in data:
        if not isinstance(item, str):
            continue

        word = item.strip().upper()
        if WORD_PATTERN.fullmatch(word) and word not in seen:
            seen.add(word)
            words.append(word)

    return words


def resolve_word_bank_path():
    env_path = os.environ.get("WORD_BANK_PATH")
    candidates = []

    if env_path:
        candidates.append(Path(env_path).expanduser())

    candidates.extend([DEFAULT_WORD_BANK_PATH, FALLBACK_WORD_BANK_PATH])
    seed_words = parse_word_bank(DEFAULT_WORD_BANK_PATH)

    for path in candidates:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            if not path.exists():
                initial_words = seed_words if path != DEFAULT_WORD_BANK_PATH else []
                initial_payload = f"{json.dumps(initial_words, indent=2)}\n" if initial_words else "[]\n"
                path.write_text(initial_payload, encoding="utf-8")
            else:
                with path.open("a", encoding="utf-8"):
                    pass

            return path
        except OSError:
            continue

    raise RuntimeError("Could not initialize a writable word bank path.")


WORD_BANK_PATH = resolve_word_bank_path()


def save_word_bank(words):
    WORD_BANK_PATH.write_text(f"{json.dumps(words, indent=2)}\n", encoding="utf-8")


def load_word_bank():
    return parse_word_bank(WORD_BANK_PATH)


def append_words_to_bank(new_words):
    saved_words = load_word_bank()
    saved_set = set(saved_words)

    for word in new_words:
        if word not in saved_set:
            saved_words.append(word)
            saved_set.add(word)

    save_word_bank(saved_words)


def normalize_submitted_words(raw_words):
    non_empty_words = []
    valid_words = []
    invalid_words = []
    seen = set()

    for raw_word in raw_words:
        cleaned_word = str(raw_word or "").strip()
        if not cleaned_word:
            continue

        non_empty_words.append(cleaned_word)
        uppercase_word = cleaned_word.upper()

        if not WORD_PATTERN.fullmatch(uppercase_word):
            invalid_words.append(cleaned_word)
            continue

        if uppercase_word in seen:
            continue

        seen.add(uppercase_word)
        valid_words.append(uppercase_word)

    if len(non_empty_words) > MAX_WORDS:
        return None, f"Enter no more than {MAX_WORDS} words."

    if invalid_words:
        joined_words = ", ".join(invalid_words[:3])
        return None, f"Use letters only. Fix these words: {joined_words}."

    if not valid_words:
        return None, "Enter at least one word before starting the game."

    return valid_words, None


def scramble_word(word):
    if len(word) < 2:
        return word

    letters = list(word)
    shuffled = word
    attempts = 0

    while shuffled == word and attempts < 24:
        random.shuffle(letters)
        shuffled = "".join(letters)
        attempts += 1

    return shuffled


def build_feedback(guess, target_word):
    feedback = []
    for index, expected_letter in enumerate(target_word):
        guessed_letter = guess[index] if index < len(guess) else ""
        is_match = guessed_letter == expected_letter and guessed_letter != ""

        if guessed_letter == "":
            state = "missing"
        elif is_match:
            state = "correct"
        else:
            state = "incorrect"

        feedback.append(
            {
                "char": guessed_letter,
                "state": state,
                "is_match": is_match,
            }
        )

    return feedback


def create_round(words):
    randomized_words = list(words)
    random.shuffle(randomized_words)

    return {
        "words": [
            {
                "word": word,
                "scrambled": scramble_word(word),
                "tries": 0,
                "solved": False,
                "last_guess": "",
                "last_feedback": [],
                "message": "",
            }
            for word in randomized_words
        ],
        "current_index": 0,
    }


def get_round():
    round_state = session.get(SESSION_KEY)
    if not round_state or not round_state.get("words"):
        return None

    return round_state


def summarize_round(round_state):
    words = round_state.get("words", [])
    total_words = len(words)
    total_tries = sum(word.get("tries", 0) for word in words)
    solved_words = sum(1 for word in words if word.get("solved"))

    return {
        "total_words": total_words,
        "solved_words": solved_words,
        "total_tries": total_tries,
    }


def build_snapshot(round_state):
    if not round_state:
        return {"status": "idle"}

    words = round_state.get("words", [])
    current_index = round_state.get("current_index", 0)

    if current_index >= len(words):
        return {
            "status": "complete",
            "summary": summarize_round(round_state),
        }

    current_word = words[current_index]

    return {
        "status": "word-correct" if current_word.get("solved") else "playing",
        "progress": {
            "current": current_index + 1,
            "total": len(words),
        },
        "word": {
            "scrambled": current_word["scrambled"],
            "answer_length": len(current_word["word"]),
            "tries": current_word["tries"],
            "last_guess": current_word.get("last_guess", ""),
            "feedback": current_word.get("last_feedback", []),
            "message": current_word.get("message", ""),
        },
        "can_advance": current_word.get("solved", False),
    }


def save_round(round_state):
    session[SESSION_KEY] = round_state
    session.modified = True


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/game/state")
def get_game_state():
    return jsonify(build_snapshot(get_round()))


@app.post("/api/game/start")
def start_game():
    payload = request.get_json(silent=True) or {}
    submitted_words = payload.get("words", [])

    if not isinstance(submitted_words, list):
        return jsonify({"error": "Words must be sent as a list."}), 400

    normalized_words, error_message = normalize_submitted_words(submitted_words)
    if error_message:
        return jsonify({"error": error_message}), 400

    append_words_to_bank(normalized_words)

    round_state = create_round(normalized_words)
    save_round(round_state)

    return jsonify(build_snapshot(round_state))


@app.post("/api/game/check")
def check_guess():
    round_state = get_round()
    if not round_state:
        return jsonify({"error": "Start a round before checking an answer."}), 400

    current_index = round_state.get("current_index", 0)
    words = round_state.get("words", [])

    if current_index >= len(words):
        return jsonify({"error": "This round is already complete."}), 400

    current_word = words[current_index]
    if current_word.get("solved"):
        return jsonify({"error": "Use Next to move to the next word."}), 400

    payload = request.get_json(silent=True) or {}
    guess = str(payload.get("guess", "") or "").strip().upper()

    current_word["tries"] += 1
    current_word["last_guess"] = guess
    current_word["last_feedback"] = build_feedback(guess, current_word["word"])

    if not guess:
        current_word["message"] = "Type your spelling word first."
        save_round(round_state)
        snapshot = build_snapshot(round_state)
        snapshot.update(
            {
                "result": "incorrect",
                "tries": current_word["tries"],
                "message": current_word["message"],
                "feedback": current_word["last_feedback"],
                "can_advance": False,
            }
        )
        return jsonify(snapshot)

    if not WORD_PATTERN.fullmatch(guess):
        current_word["message"] = "Use letters only."
        save_round(round_state)
        snapshot = build_snapshot(round_state)
        snapshot.update(
            {
                "result": "incorrect",
                "tries": current_word["tries"],
                "message": current_word["message"],
                "feedback": current_word["last_feedback"],
                "can_advance": False,
            }
        )
        return jsonify(snapshot)

    if guess == current_word["word"]:
        current_word["solved"] = True
        current_word["message"] = SUCCESS_MESSAGE
        result = "correct"
    else:
        current_word["message"] = "Not yet. Fix the red letters and try again."
        result = "incorrect"

    save_round(round_state)
    snapshot = build_snapshot(round_state)
    snapshot.update(
        {
            "result": result,
            "tries": current_word["tries"],
            "message": current_word["message"],
            "feedback": current_word["last_feedback"],
            "can_advance": current_word["solved"],
        }
    )

    return jsonify(snapshot)


@app.post("/api/game/next")
def next_word():
    round_state = get_round()
    if not round_state:
        return jsonify({"error": "Start a round first."}), 400

    current_index = round_state.get("current_index", 0)
    words = round_state.get("words", [])

    if current_index >= len(words):
        return jsonify(build_snapshot(round_state))

    current_word = words[current_index]
    if not current_word.get("solved"):
        return jsonify({"error": "Spell the current word correctly before moving on."}), 400

    round_state["current_index"] = current_index + 1
    save_round(round_state)

    return jsonify(build_snapshot(round_state))


if __name__ == "__main__":
    app.run(debug=True)
