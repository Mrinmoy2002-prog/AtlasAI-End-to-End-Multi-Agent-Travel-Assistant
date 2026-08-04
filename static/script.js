// =============================================================================
// 1. GLOBAL STATE & INITIALIZATION
// =============================================================================

// Retrieve the existing conversation thread ID from browser storage, or default to null
let currentThreadId = localStorage.getItem("travel_thread_id") || null;

// Stores the raw Markdown string of the latest AI travel itinerary for exports
let latestAnswerMarkdown = "";


// =============================================================================
// 2. HELPER & UI TOGGLE FUNCTIONS
// =============================================================================

/**
 * Fills the main text input field with a given string (useful for quick prompt buttons).
 */
function setPrompt(text) {
    document.getElementById("userInput").value = text;
}

/**
 * Toggles button states and spinner animations during an API call.
 */
function setLoading(isLoading) {
    const sendBtn = document.getElementById("sendBtn");
    const btnText = document.getElementById("btnText");
    const btnLoader = document.getElementById("btnLoader");

    // Prevent double-clicking while waiting for response
    sendBtn.disabled = isLoading;

    if (isLoading) {
        btnText.classList.add("hidden");
        btnLoader.classList.remove("hidden");
    } else {
        btnText.classList.remove("hidden");
        btnLoader.classList.add("hidden");
    }
}

/**
 * Displays an error banner message to the user.
 */
function showError(message) {
    const errorBox = document.getElementById("errorBox");

    errorBox.textContent = message;
    errorBox.classList.remove("hidden");
}

/**
 * Clears and hides the error banner.
 */
function hideError() {
    const errorBox = document.getElementById("errorBox");

    errorBox.classList.add("hidden");
    errorBox.textContent = "";
}


// =============================================================================
// 3. RESULT RENDERING
// =============================================================================

/**
 * Renders the AI response in the UI, parses Markdown, and scrolls to results.
 */
function showResult(answer, threadId) {
    // Save raw response markdown globally
    latestAnswerMarkdown = answer;

    const resultSection = document.getElementById("resultSection");
    const resultBox = document.getElementById("resultBox");
    const threadInfo = document.getElementById("threadInfo");

    // Convert Markdown into formatted HTML using Marked library (if loaded)
    if (typeof marked !== "undefined") {
        resultBox.innerHTML = marked.parse(answer);
    } else {
        resultBox.innerText = answer;
    }

    // Display active thread ID in the metadata section
    threadInfo.textContent = `Thread ID: ${threadId}`;

    // Reveal result container
    resultSection.classList.remove("hidden");

    // Smoothly scroll down to show the generated itinerary
    resultSection.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}


// =============================================================================
// 4. API COMMUNICATION (SEND MESSAGE)
// =============================================================================

/**
 * Asynchronously sends user prompt to backend API endpoint and handles response.
 */
async function sendMessage() {
    hideError();

    const input = document.getElementById("userInput");
    const message = input.value.trim();

    // Prevent empty requests
    if (!message) {
        showError("Please enter your travel request first.");
        return;
    }

    setLoading(true);

    try {
        // Send request payload to server route
        const response = await fetch("/api/travel", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: message,
                thread_id: currentThreadId // Send session ID to maintain chat context
            })
        });

        const data = await response.json();

        // Throw error if response status is not 200 or API returns success=false
        if (!response.ok || !data.success) {
            throw new Error(data.error || "Something went wrong.");
        }

        // Update session ID in memory and browser local storage
        currentThreadId = data.thread_id;
        localStorage.setItem("travel_thread_id", currentThreadId);

        // Display formatted travel plan
        showResult(data.answer, data.thread_id);

    } catch (error) {
        showError(error.message);
    } finally {
        // Always reset loading state regardless of success or failure
        setLoading(false);
    }
}


// =============================================================================
// 5. EXPORT UTILITIES (COPY & PDF DOWNLOAD)
// =============================================================================

/**
 * Copies plain text of generated response to system clipboard.
 */
function copyResult() {
    const resultBox = document.getElementById("resultBox");
    const text = resultBox.innerText;

    if (!text) {
        return;
    }

    // Write text to clipboard asynchronously
    navigator.clipboard.writeText(text)
        .then(() => {
            const copyBtn = document.querySelector(".copy-btn");
            const oldText = copyBtn.textContent;

            // Give temporary visual confirmation
            copyBtn.textContent = "Copied!";

            setTimeout(() => {
                copyBtn.textContent = oldText;
            }, 1400);
        })
        .catch(() => {
            showError("Could not copy result.");
        });
}

/**
 * Converts result container HTML into a formatted PDF file download using html2pdf.
 */
function downloadPDF() {
    const pdfContent = document.getElementById("pdfContent");

    if (!latestAnswerMarkdown || !pdfContent) {
        showError("No travel plan available to download.");
        return;
    }

    const downloadBtn = document.querySelector(".download-btn");
    const oldText = downloadBtn.textContent;

    downloadBtn.textContent = "Preparing PDF...";
    downloadBtn.disabled = true;

    // PDF styling and rendering settings
    const options = {
        margin: 0.5,
        filename: "ai-travel-plan.pdf",
        image: {
            type: "jpeg",
            quality: 0.98
        },
        html2canvas: {
            scale: 2,
            useCORS: true,
            backgroundColor: "#ffffff"
        },
        jsPDF: {
            unit: "in",
            format: "a4",
            orientation: "portrait"
        },
        pagebreak: {
            mode: ["avoid-all", "css", "legacy"]
        }
    };

    // Generate and download PDF document
    html2pdf()
        .set(options)
        .from(pdfContent)
        .save()
        .then(() => {
            downloadBtn.textContent = oldText;
            downloadBtn.disabled = false;
        })
        .catch(() => {
            downloadBtn.textContent = oldText;
            downloadBtn.disabled = false;
            showError("Could not download PDF.");
        });
}


// =============================================================================
// 6. EVENT LISTENERS
// =============================================================================

// Submit query when user presses Ctrl + Enter in any text field
document.addEventListener("keydown", function(event) {
    if (event.ctrlKey && event.key === "Enter") {
        sendMessage();
    }
});