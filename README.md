# Scramble Star Spelling Game

A Flask-powered interactive spelling scramble game.

## Features

- Custom word lists
- Letter-position feedback system
- Session-based round tracking
- Duplicate-word filtering
- Persistent word bank storage

## Built With

- Python
- Flask
- JavaScript
- HTML/CSS

## How It Works

1. Enter between 1 and 15 spelling words.
2. Start the round to generate a scrambled game board.
3. Solve one scrambled word at a time.
4. Use the feedback tiles to spot letters in the wrong position.
5. Move to the next word after a correct answer.

## Getting Started

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the Flask app:

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## Project Structure

```text
app.py
templates/
static/
words/
```
