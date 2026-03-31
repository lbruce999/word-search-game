document.addEventListener("DOMContentLoaded", () => {
    const ui = {
        setupPanel: document.getElementById("setup-panel"),
        playPanel: document.getElementById("play-panel"),
        completePanel: document.getElementById("complete-panel"),
        wordForm: document.getElementById("word-form"),
        answerForm: document.getElementById("answer-form"),
        formMessage: document.getElementById("form-message"),
        progressBadge: document.getElementById("progress-badge"),
        triesBadge: document.getElementById("tries-badge"),
        scrambleRow: document.getElementById("scramble-row"),
        guessInput: document.getElementById("guess-input"),
        messageBanner: document.getElementById("message-banner"),
        feedbackRow: document.getElementById("feedback-row"),
        nextWordButton: document.getElementById("next-word-btn"),
        newRoundButton: document.getElementById("new-round-btn"),
        playAgainButton: document.getElementById("play-again-btn"),
        completeCopy: document.getElementById("complete-copy"),
        checkAnswerButton: document.getElementById("check-answer-btn"),
        startButton: document.getElementById("submit-words-btn"),
    };

    const state = {
        mode: "idle",
        lastSnapshot: null,
        formError: "",
    };

    function sanitizeWord(value) {
        return value.toUpperCase().replace(/[^A-Z]/g, "");
    }

    function setVisibleMode(mode) {
        state.mode = mode;
        ui.setupPanel.classList.toggle("is-hidden", !(mode === "idle"));
        ui.playPanel.classList.toggle("is-hidden", !(mode === "playing" || mode === "word-correct"));
        ui.completePanel.classList.toggle("is-hidden", mode !== "complete");
        document.body.dataset.mode = mode;
    }

    function setFormMessage(message, isError = false) {
        ui.formMessage.textContent = message;
        ui.formMessage.classList.toggle("is-error", isError);
        ui.formMessage.classList.toggle("is-success", Boolean(message) && !isError);
    }

    function setMessageBanner(message, tone = "neutral") {
        ui.messageBanner.textContent = message;
        ui.messageBanner.className = "message-banner";
        if (message) {
            ui.messageBanner.classList.add(`is-${tone}`);
        }
    }

    function renderTiles(container, letters, className, emptyLabel) {
        container.innerHTML = "";

        letters.forEach((letter) => {
            const tile = document.createElement("span");
            tile.className = className;
            tile.textContent = letter || emptyLabel;
            container.appendChild(tile);
        });
    }

    function renderScrambledWord(scrambledWord) {
        renderTiles(ui.scrambleRow, scrambledWord.split(""), "letter-tile scramble-tile", " ");
    }

    function renderFeedback(feedback) {
        ui.feedbackRow.innerHTML = "";

        if (!feedback || feedback.length === 0) {
            const hint = document.createElement("p");
            hint.className = "feedback-empty";
            hint.textContent = "Check an answer to see letter-by-letter feedback.";
            ui.feedbackRow.appendChild(hint);
            return;
        }

        feedback.forEach((item) => {
            const tile = document.createElement("span");
            tile.className = `letter-tile feedback-tile is-${item.state}`;
            tile.textContent = item.char || " ";
            ui.feedbackRow.appendChild(tile);
        });
    }

    function renderPlayingState(snapshot) {
        const { progress, word, can_advance } = snapshot;
        state.lastSnapshot = snapshot;

        setVisibleMode(can_advance ? "word-correct" : "playing");
        ui.progressBadge.textContent = `Word ${progress.current} of ${progress.total}`;
        ui.triesBadge.textContent = `Tries: ${word.tries}`;
        renderScrambledWord(word.scrambled);
        renderFeedback(word.feedback || []);

        ui.guessInput.value = word.last_guess || "";
        ui.guessInput.maxLength = word.answer_length;
        ui.guessInput.placeholder = `${word.answer_length} letters`;
        ui.guessInput.disabled = can_advance;
        ui.checkAnswerButton.disabled = can_advance;
        ui.nextWordButton.classList.toggle("is-hidden", !can_advance);

        if (word.message) {
            setMessageBanner(word.message, can_advance ? "success" : "warning");
        } else {
            setMessageBanner("Unscramble the letters and spell the word correctly.");
        }

        if (!can_advance) {
            ui.guessInput.focus();
            ui.guessInput.select();
        }
    }

    function renderCompleteState(snapshot) {
        const summary = snapshot.summary || { solved_words: 0, total_tries: 0 };
        state.lastSnapshot = snapshot;

        setVisibleMode("complete");
        const solvedWordCount = summary.solved_words ?? summary.total_words ?? 0;
        const solvedLabel = solvedWordCount === 1 ? "word" : "words";
        const triesLabel = summary.total_tries === 1 ? "try" : "tries";
        ui.completeCopy.textContent = `You solved ${solvedWordCount} ${solvedLabel} in ${summary.total_tries} ${triesLabel}. Add more words and play again.`;
    }

    function renderIdleState() {
        state.lastSnapshot = null;
        setVisibleMode("idle");
        ui.wordForm.reset();
        ui.answerForm.reset();
        ui.feedbackRow.innerHTML = "";
        ui.scrambleRow.innerHTML = "";
        setMessageBanner("");
        renderFeedback([]);
        setFormMessage("Words are saved for future rounds when you start the game.");
    }

    function applySnapshot(snapshot) {
        if (!snapshot || snapshot.status === "idle") {
            renderIdleState();
            return;
        }

        if (snapshot.status === "complete") {
            renderCompleteState(snapshot);
            return;
        }

        renderPlayingState(snapshot);
    }

    async function requestJson(url, options = {}) {
        const response = await fetch(url, {
            headers: {
                "Content-Type": "application/json",
            },
            ...options,
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Something went wrong.");
        }

        return data;
    }

    async function restoreGameState() {
        try {
            const snapshot = await requestJson("/api/game/state");
            applySnapshot(snapshot);
        } catch (error) {
            renderIdleState();
            setFormMessage("The game could not restore right now.", true);
        }
    }

    ui.wordForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const words = Array.from(ui.wordForm.querySelectorAll("input"))
            .map((input) => sanitizeWord(input.value))
            .filter(Boolean);

        if (words.length === 0) {
            setFormMessage("Enter at least one word to start the round.", true);
            return;
        }

        ui.startButton.disabled = true;
        setFormMessage("Building your scramble round...");

        try {
            const snapshot = await requestJson("/api/game/start", {
                method: "POST",
                body: JSON.stringify({ words }),
            });

            setFormMessage("");
            applySnapshot(snapshot);
        } catch (error) {
            setFormMessage(error.message, true);
        } finally {
            ui.startButton.disabled = false;
        }
    });

    ui.answerForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const guess = sanitizeWord(ui.guessInput.value);
        ui.guessInput.value = guess;
        ui.checkAnswerButton.disabled = true;

        try {
            const snapshot = await requestJson("/api/game/check", {
                method: "POST",
                body: JSON.stringify({ guess }),
            });

            applySnapshot(snapshot);
        } catch (error) {
            setMessageBanner(error.message, "warning");
        } finally {
            if (state.mode !== "word-correct") {
                ui.checkAnswerButton.disabled = false;
            }
        }
    });

    ui.nextWordButton.addEventListener("click", async () => {
        ui.nextWordButton.disabled = true;

        try {
            const snapshot = await requestJson("/api/game/next", {
                method: "POST",
                body: JSON.stringify({}),
            });

            applySnapshot(snapshot);
            ui.checkAnswerButton.disabled = false;
        } catch (error) {
            setMessageBanner(error.message, "warning");
        } finally {
            ui.nextWordButton.disabled = false;
        }
    });

    ui.newRoundButton.addEventListener("click", () => {
        renderIdleState();
    });

    ui.playAgainButton.addEventListener("click", () => {
        renderIdleState();
    });

    ui.wordForm.querySelectorAll("input").forEach((input) => {
        input.addEventListener("input", () => {
            input.value = sanitizeWord(input.value);
        });
    });

    ui.guessInput.addEventListener("input", () => {
        ui.guessInput.value = sanitizeWord(ui.guessInput.value).slice(0, Number(ui.guessInput.maxLength || 99));
    });

    window.render_game_to_text = () =>
        JSON.stringify({
            mode: state.mode,
            progress: state.lastSnapshot?.progress || null,
            scrambled: state.lastSnapshot?.word?.scrambled || "",
            tries: state.lastSnapshot?.word?.tries || 0,
            canAdvance: state.lastSnapshot?.can_advance || false,
            message: state.lastSnapshot?.word?.message || "",
            summary: state.lastSnapshot?.summary || null,
        });

    window.advanceTime = () => {};

    renderFeedback([]);
    restoreGameState();
});
