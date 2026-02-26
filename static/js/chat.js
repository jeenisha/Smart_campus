function sendMessage() {
    let input = document.getElementById("user-input");
    let message = input.value.trim();

    if (message === "") return;

    appendMessage(message, "user");
    input.value = "";

    fetch("/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ message: message })
    })
    .then(response => response.json())
    .then(data => {
        appendMessage(data.response, "bot");
    });
}

function appendMessage(text, sender) {
    let chatMessages = document.getElementById("chat-messages");
    let messageDiv = document.createElement("div");

    messageDiv.classList.add("message", sender);
    messageDiv.innerText = text;

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

document.getElementById("user-input").addEventListener("keypress", function(event) {
    if (event.key === "Enter") {
        sendMessage();
    }
});