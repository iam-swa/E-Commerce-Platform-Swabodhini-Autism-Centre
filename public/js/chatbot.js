document.addEventListener('DOMContentLoaded', () => {
    // Inject HTML
    const chatbotHTML = `
        <div id="chatbot-container">
            <div id="chat-window" class="chat-window hidden">
                <div class="chat-header">
                    <h4>Customer Support</h4>
                    <button id="close-chat" class="close-btn">&times;</button>
                </div>
                <div id="chat-messages" class="chat-messages">
                    <div class="message bot-message">Hi there! How can I help you today?</div>
                </div>
                <div class="chat-input-area">
                    <input type="text" id="chat-input" placeholder="Type your message..." autocomplete="off">
                    <button id="send-btn">Send</button>
                </div>
            </div>
            <button id="chatbot-toggle" class="chatbot-btn">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M21 11.5C21 16.1944 16.9706 20 12 20C10.7412 20 9.54228 19.761 8.46083 19.3308C8.22558 19.2373 7.96288 19.2452 7.73356 19.3533L4.35905 20.9427C3.96696 21.1274 3.51888 20.8066 3.58525 20.373L4.03264 17.4526C4.07221 17.1943 3.98776 16.9329 3.81188 16.7417C2.67389 15.313 2 13.4862 2 11.5C2 6.80558 6.47715 3 12 3C17.5228 3 21 6.80558 21 11.5Z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </button>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', chatbotHTML);
    
    const chatWindow = document.getElementById('chat-window');
    const chatbotToggle = document.getElementById('chatbot-toggle');
    const closeChat = document.getElementById('close-chat');
    const sendBtn = document.getElementById('send-btn');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');

    let currentUserId = null;
    try {
        const userStr = sessionStorage.getItem('user');
        if (userStr) {
            const user = JSON.parse(userStr);
            currentUserId = user.id || user._id;
        }
    } catch(e) {}

    const storageKey = currentUserId ? `chat_history_${currentUserId}` : null;

    if (storageKey) {
        const chatHistory = JSON.parse(localStorage.getItem(storageKey)) || [];
        if (chatHistory.length > 0) {
            chatMessages.innerHTML = '';
            chatHistory.forEach(msg => {
                appendMessage(msg.sender, msg.text, false);
            });
        }
    } else {
        // Safe fallback: reset chat state completely if no identity
        sessionStorage.removeItem('chatHistory');
        chatMessages.innerHTML = '<div class="message bot-message">Hi there! How can I help you today?</div>';
    }

    chatbotToggle.addEventListener('click', () => {
        chatWindow.classList.toggle('hidden');
        if (!chatWindow.classList.contains('hidden')) {
            chatInput.focus();
            scrollToBottom();
        }
    });

    closeChat.addEventListener('click', () => {
        chatWindow.classList.add('hidden');
    });

    sendBtn.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    let isRequesting = false;

    async function sendMessage() {
        if (isRequesting) return;
        const text = chatInput.value.trim();
        if (!text) return;

        // Prevent rapid clicking and spam
        isRequesting = true;
        chatInput.disabled = true;
        sendBtn.disabled = true;
        const originalBtnText = sendBtn.textContent;
        sendBtn.textContent = '...';

        appendMessage('user', text);
        chatInput.value = '';
        
        // Show subtle typing indicator
        const typingId = showTypingIndicator();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });
            
            if (!response.ok) throw new Error('Network response was not ok');
            
            const data = await response.json();
            
            removeTypingIndicator(typingId);
            appendMessage('bot', data.reply || "I'm here to help! How else can I assist you?");
        } catch (error) {
            console.error('Chat error:', error);
            removeTypingIndicator(typingId);
            appendMessage('bot', "Hi! I'm having a bit of trouble connecting, but I can help you with shipping, payments, and returns. What can I do for you?");
        } finally {
            // Cleanly re-enable after a short natural delay
            setTimeout(() => {
                isRequesting = false;
                chatInput.disabled = false;
                sendBtn.disabled = false;
                sendBtn.textContent = originalBtnText;
                if (!chatWindow.classList.contains('hidden')) {
                    chatInput.focus();
                }
                scrollToBottom();
            }, 600);
        }
    }

    function appendMessage(sender, text, saveToHistory = true) {
        const msgDiv = document.createElement('div');
        msgDiv.classList.add('message', sender === 'user' ? 'user-message' : 'bot-message');
        msgDiv.textContent = text;
        chatMessages.appendChild(msgDiv);
        scrollToBottom();
        
        if (saveToHistory && storageKey) {
            const chatHistory = JSON.parse(localStorage.getItem(storageKey)) || [];
            // If empty, add default greeting first
            if (chatHistory.length === 0) {
                chatHistory.push({ sender: 'bot', text: 'Hi there! How can I help you today?' });
            }
            chatHistory.push({ sender, text });
            localStorage.setItem(storageKey, JSON.stringify(chatHistory));
        }
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function showTypingIndicator() {
        const id = 'typing-' + Date.now();
        const msgDiv = document.createElement('div');
        msgDiv.id = id;
        msgDiv.classList.add('message', 'bot-message', 'typing-indicator');
        msgDiv.innerHTML = '<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>';
        chatMessages.appendChild(msgDiv);
        scrollToBottom();
        return id;
    }

    function removeTypingIndicator(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }
});
