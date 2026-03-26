// frontend/script.js
document.addEventListener('DOMContentLoaded', () => {
    const userIdInput = document.getElementById('userIdInput');
    const loadSessionsBtn = document.getElementById('loadSessionsBtn');
    const newChatBtn = document.getElementById('newChatBtn');
    const sessionList = document.getElementById('sessionList');
    const currentSessionNameSpan = document.getElementById('currentSessionId');
    const chatMessagesDiv = document.getElementById('chatMessages');
    const messageInput = document.getElementById('messageInput');
    const sendMessageBtn = document.getElementById('sendMessageBtn');
    const recordBtn = document.getElementById('recordBtn');

    // Session name editing elements
    const sessionNameEditInput = document.getElementById('sessionNameEditInput');
    const sessionNameEditBtn = document.getElementById('sessionNameEditBtn');
    const sessionNameDisplay = document.getElementById('sessionNameDisplay');
    const sessionNameContainer = document.getElementById('sessionNameContainer');

    const API_BASE_URL = 'http://127.0.0.1:8000';

    let currentUserId = '';
    let currentSessionId = '';
    let currentSessionDisplayName = "No Session Selected";

    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;

    /** Prefer snake_case from FastAPI; tolerate other shapes if API changes. */
    function pickVoiceTranscription(data) {
        if (!data || typeof data !== 'object') return '';
        const raw =
            data.transcription ??
            data.transcript ??
            data.user_message ??
            data.user_message_text;
        if (raw == null) return '';
        const s = String(raw).trim();
        return s;
    }

    // ===== UTILITY FUNCTIONS =====

    function generateUuid() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0,
                v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    function base64ToBlob(base64, mimeType) {
        try {
            console.log(`🎵 Converting base64 to blob, length: ${base64.length}, type: ${mimeType}`);
            
            // Remove any whitespace or newlines
            base64 = base64.replace(/\s/g, '');
            
            const byteCharacters = atob(base64);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], { type: mimeType });
            
            console.log(`🎵 Blob created successfully, size: ${blob.size} bytes`);
            return blob;
        } catch (error) {
            console.error('❌ Error converting base64 to blob:', error);
            throw error;
        }
    }

    function displayMessage(displayRole, content, timestamp, isAudio = false, audioBase64 = null, transcription = null, moderationBlocked = false, moderationFlagged = false) {
        console.log('📨 displayMessage called with:', {
            displayRole,
            contentLength: content.length,
            hasAudio: !!audioBase64,
            audioLength: audioBase64 ? audioBase64.length : 0,
            isAudio,
            transcription
        });

        const messageBubble = document.createElement('div');
        messageBubble.classList.add('message-bubble', displayRole === "You" ? 'user' : 'assistant');

        const roleSpan = document.createElement('div');
        roleSpan.classList.add('message-role');
        roleSpan.textContent = displayRole;
        
        // Add moderation warning if flagged
        if (moderationBlocked) {
            const warningBadge = document.createElement('span');
            warningBadge.classList.add('moderation-warning', 'moderation-blocked');
            warningBadge.textContent = '🛡️ Blocked';
            roleSpan.appendChild(warningBadge);
        } else if (moderationFlagged) {
            const warningBadge = document.createElement('span');
            warningBadge.classList.add('moderation-warning');
            warningBadge.textContent = '⚠️ Flagged';
            roleSpan.appendChild(warningBadge);
        }
        
        messageBubble.appendChild(roleSpan);

        const contentDiv = document.createElement('div');
        contentDiv.classList.add('message-content');
        console.log('📦 Created contentDiv:', contentDiv);
        
        // User voice: label + prominent STT text (what you said)
        if (isAudio && displayRole === "You") {
            const labelEl = document.createElement('div');
            labelEl.className = 'voice-message-label';
            labelEl.textContent = 'Audio message';
            contentDiv.appendChild(labelEl);
            const tx = transcription != null ? String(transcription).trim() : '';
            const transcriptEl = document.createElement('div');
            transcriptEl.classList.add('user-voice-transcript');
            transcriptEl.textContent = tx || '(No transcription)';
            contentDiv.appendChild(transcriptEl);
        } else {
            const textSpan = document.createElement('span');
            textSpan.innerHTML = content.replace(/\n/g, '<br>');
            contentDiv.appendChild(textSpan);
        }
        console.log('📦 After adding text, contentDiv children:', contentDiv.children.length);

        // CRITICAL FIX: Check for audio for assistant messages
        console.log('🔍 Checking audio conditions:', {
            'displayRole': displayRole,
            'displayRole !== "You"': displayRole !== "You",
            'audioBase64 exists': !!audioBase64,
            'audioBase64 type': typeof audioBase64,
            'audioBase64 length': audioBase64 ? audioBase64.length : 0,
            'audioBase64 first 50 chars': audioBase64 ? audioBase64.substring(0, 50) : 'N/A'
        });

        // Create audio player for any non-user message with audio data
        if (displayRole !== "You" && audioBase64 && audioBase64.length > 0) {
            console.log(`✅ CREATING AUDIO PLAYER - base64 length: ${audioBase64.length}`);
            
            const audioControls = document.createElement('div');
            audioControls.className = 'audio-controls-container';

            try {
                const audioBlob = base64ToBlob(audioBase64, 'audio/mpeg');
                
                if (audioBlob.size === 0) {
                    throw new Error('Audio blob is empty');
                }
                
                const audioUrl = URL.createObjectURL(audioBlob);
                console.log(`🎵 Audio URL created: ${audioUrl}`);
                
                const audio = new Audio(audioUrl);
                
                const playBtn = document.createElement('button');
                playBtn.textContent = '▶ Play';
                
                const pauseBtn = document.createElement('button');
                pauseBtn.disabled = true;
                pauseBtn.textContent = '⏸ Pause';
                
                const replayBtn = document.createElement('button');
                replayBtn.textContent = '↻ Replay';
                
                const statusSpan = document.createElement('span');
                statusSpan.textContent = 'Ready';
                
                playBtn.addEventListener('click', () => {
                    console.log('🎵 Play button clicked');
                    audio.play().then(() => {
                        console.log('🎵 Audio playing');
                        playBtn.disabled = true;
                        pauseBtn.disabled = false;
                        statusSpan.textContent = '🔊 Playing';
                    }).catch(err => {
                        console.error('❌ Audio play error:', err);
                        statusSpan.textContent = 'Error: ' + err.message;
                    });
                });
                
                pauseBtn.addEventListener('click', () => {
                    console.log('🎵 Pause button clicked');
                    audio.pause();
                    playBtn.disabled = false;
                    pauseBtn.disabled = true;
                    statusSpan.textContent = 'Paused';
                });
                
                replayBtn.addEventListener('click', () => {
                    console.log('🎵 Replay button clicked');
                    audio.currentTime = 0;
                    audio.play().then(() => {
                        playBtn.disabled = true;
                        pauseBtn.disabled = false;
                        statusSpan.textContent = '🔊 Playing';
                    }).catch(err => {
                        console.error('❌ Audio replay error:', err);
                    });
                });
                
                audio.addEventListener('ended', () => {
                    console.log('🎵 Audio playback ended');
                    playBtn.disabled = false;
                    pauseBtn.disabled = true;
                    statusSpan.textContent = 'Finished';
                });
                
                audio.addEventListener('error', (e) => {
                    console.error('❌ Audio playback error:', e);
                    console.error('Audio error details:', audio.error);
                    statusSpan.textContent = 'Error loading audio';
                    playBtn.disabled = true;
                    pauseBtn.disabled = true;
                    replayBtn.disabled = true;
                });
                
                audio.addEventListener('canplay', () => {
                    console.log('🎵 Audio can play - ready!');
                });
                
                audioControls.appendChild(playBtn);
                audioControls.appendChild(pauseBtn);
                audioControls.appendChild(replayBtn);
                audioControls.appendChild(statusSpan);
                
                console.log('🎯 About to append audio controls to contentDiv');
                console.log('🎯 contentDiv:', contentDiv);
                console.log('🎯 audioControls:', audioControls);
                console.log('🎯 contentDiv.children before append:', contentDiv.children.length);
                
                try {
                    contentDiv.appendChild(audioControls);
                    console.log('🎯 contentDiv.children after append:', contentDiv.children.length);
                    console.log('✅ Audio controls successfully added to DOM!');
                    
                    // Verify it's actually in the DOM
                    setTimeout(() => {
                        const found = document.querySelectorAll('.audio-controls-container').length;
                        console.log('🔍 Audio controls found in DOM after 100ms:', found);
                    }, 100);
                } catch (err) {
                    console.error('❌ Error appending audio controls:', err);
                }
            } catch (error) {
                console.error('❌ Error creating audio player:', error);
                const errorDiv = document.createElement('div');
                errorDiv.style.color = '#ef4444';
                errorDiv.style.padding = '10px';
                errorDiv.style.marginTop = '10px';
                errorDiv.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
                errorDiv.style.borderRadius = '6px';
                errorDiv.textContent = '⚠️ Audio unavailable: ' + error.message;
                contentDiv.appendChild(errorDiv);
            }
        } else {
        console.log('❌ Audio player NOT created. Conditions not met.');
        console.log('❌ Condition check details:', {
            'displayRole !== "You"': displayRole !== "You",
            'audioBase64 truthy': !!audioBase64,
            'audioBase64.length > 0': audioBase64 ? audioBase64.length > 0 : 'N/A'
        });
        }

        console.log('📦 Final contentDiv children before appending to bubble:', contentDiv.children.length);
        messageBubble.appendChild(contentDiv);

        const timestampSpan = document.createElement('div');
        timestampSpan.classList.add('message-timestamp');
        const date = new Date(timestamp);
        timestampSpan.textContent = date.toLocaleString();
        messageBubble.appendChild(timestampSpan);

        chatMessagesDiv.appendChild(messageBubble);
        chatMessagesDiv.scrollTop = chatMessagesDiv.scrollHeight;
    }

    function clearChat() {
        chatMessagesDiv.innerHTML = '';
    }

    function setActiveSession(sessionId) {
        const currentActive = sessionList.querySelector('.active');
        if (currentActive) {
            currentActive.classList.remove('active');
        }
        const newActive = document.getElementById(`session-${sessionId}`);
        if (newActive) {
            newActive.classList.add('active');
        }
    }

    async function selectAndLoadSession(userId, sessionId, sessionName = null) {
        if (!userId || !sessionId) {
            console.warn("Attempted to select and load session with missing userId or sessionId.");
            return;
        }
        currentUserId = userId;
        currentSessionId = sessionId;
        currentSessionDisplayName = sessionName || sessionId;

        currentSessionNameSpan.textContent = `Current Session: ${currentSessionDisplayName}`;
        sessionNameDisplay.textContent = currentSessionDisplayName;
        sessionNameEditInput.value = currentSessionDisplayName;

        setActiveSession(sessionId);
        await loadHistory(userId, sessionId);
    }

    // ===== API CALLS =====

    async function loadSessions(userId) {
        if (!userId) {
            sessionList.innerHTML = '<li style="color: #94a3b8; text-align: center; padding: 20px;">Please enter a User ID.</li>';
            currentSessionNameSpan.textContent = 'Current Session: No User ID/Session';
            sessionNameDisplay.textContent = 'No Session Selected';
            sessionNameEditInput.value = '';
            clearChat();
            currentSessionId = '';
            return;
        }

        currentUserId = userId;
        sessionList.innerHTML = '<li style="color: #94a3b8; text-align: center; padding: 20px;">Loading...</li>';
        let fetchedSessions = [];

        try {
            const response = await fetch(`${API_BASE_URL}/sessions/${userId}`);
            if (!response.ok) {
                if (response.status === 404) {
                    console.log(`No sessions found for user: ${userId}`);
                } else {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
            } else {
                fetchedSessions = await response.json();
            }

            sessionList.innerHTML = '';

            if (!fetchedSessions || fetchedSessions.length === 0) {
                sessionList.innerHTML = '<li style="color: #94a3b8; text-align: center; padding: 20px;">No sessions found. Start a new chat!</li>';
                if (currentSessionId && !fetchedSessions.some(s => s.session_id === currentSessionId)) {
                    currentSessionNameSpan.textContent = 'Current Session: No Session Selected';
                    sessionNameDisplay.textContent = 'No Session Selected';
                    sessionNameEditInput.value = '';
                    clearChat();
                    currentSessionId = '';
                }
                return;
            }

            let sessionFoundInList = false;
            fetchedSessions.forEach(session => {
                const li = document.createElement('li');
                li.classList.add('session-item');
                li.id = `session-${session.session_id}`;
                
                const display = session.session_name || session.session_id;
                li.innerHTML = `
                    <div class="session-name">${display}</div>
                    <div class="session-preview">${session.last_message_preview}</div>
                `;
                
                li.addEventListener('click', async () => {
                    await selectAndLoadSession(currentUserId, session.session_id, session.session_name);
                });
                
                sessionList.appendChild(li);

                if (currentSessionId === session.session_id) {
                    sessionFoundInList = true;
                }
            });

            if (currentSessionId && sessionFoundInList) {
                const selectedSession = fetchedSessions.find(s => s.session_id === currentSessionId);
                await selectAndLoadSession(currentUserId, currentSessionId, selectedSession ? selectedSession.session_name : null);
            } else if (fetchedSessions.length > 0) {
                await selectAndLoadSession(currentUserId, fetchedSessions[0].session_id, fetchedSessions[0].session_name);
            }

        } catch (error) {
            console.error('Error loading sessions:', error);
            sessionList.innerHTML = '<li style="color: #ef4444; text-align: center; padding: 20px;">Failed to load sessions.</li>';
        }
    }

    async function loadHistory(userId, sessionId) {
        if (!userId || !sessionId) {
            clearChat();
            return;
        }
        clearChat();

        try {
            const response = await fetch(`${API_BASE_URL}/sessions/${userId}/${sessionId}/history`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const history = await response.json();

            // Just load history without any welcome message
            history.forEach(msg => {
                const isAudioMsg = msg.content.includes('_(Audio message)_') || msg.content.includes('(Transcribed from audio)');
                let voiceTranscription = null;
                if (isAudioMsg && msg.display_role === 'You') {
                    voiceTranscription = msg.content
                        .replace(/\s*_\s*\(Audio message\)\s*_\s*/gi, '')
                        .replace(/\(Transcribed from audio\)/gi, '')
                        .trim();
                }
                displayMessage(
                    msg.display_role,
                    msg.content,
                    msg.timestamp,
                    isAudioMsg,
                    null,  // audio_base64 - not stored in DB
                    voiceTranscription,
                    false, // moderation_blocked
                    false  // moderation_flagged
                );
            });
        } catch (error) {
            console.error('Error loading chat history:', error);
            displayMessage('Assistant', 'Error loading chat history. Please try refreshing.', new Date().toISOString());
        }
    }

    async function sendTextMessage() {
        const message = messageInput.value.trim();
        if (!message) return;

        if (!currentUserId || !currentSessionId) {
            alert('Please select or create a session first.');
            return;
        }

        displayMessage('You', message, new Date().toISOString());
        messageInput.value = '';

        try {
            sendMessageBtn.disabled = true;
            recordBtn.disabled = true;
            messageInput.disabled = true;
            messageInput.placeholder = 'Thinking...';

            const response = await fetch(`${API_BASE_URL}/chat/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_id: currentUserId,
                    session_id: currentSessionId,
                    message: message,
                    session_name: null
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('🔥 Backend response received:', data);
            console.log('🔥 Audio base64 in response:', {
                exists: !!data.audio_base64,
                type: typeof data.audio_base64,
                length: data.audio_base64 ? data.audio_base64.length : 0,
                first50chars: data.audio_base64 ? data.audio_base64.substring(0, 50) : 'N/A',
                isString: typeof data.audio_base64 === 'string'
            });
            
            // CRITICAL: Ensure audio_base64 is passed correctly (not undefined/null)
            const audioData = data.audio_base64 && data.audio_base64.length > 0 ? data.audio_base64 : null;
            console.log('🎵 Final audio data being passed to displayMessage:', {
                'audioData exists': !!audioData,
                'audioData length': audioData ? audioData.length : 0,
                'audioData type': typeof audioData
            });
            
            displayMessage(
                data.display_role, 
                data.response, 
                new Date().toISOString(), 
                false, 
                audioData,  // Pass the validated audio data
                null,
                data.moderation_blocked || false,
                data.moderation_flagged || false
            );

            // Don't reload sessions immediately - it clears and rebuilds the chat
            // loadSessions(currentUserId);

        } catch (error) {
            console.error('Error sending message:', error);
            displayMessage('Assistant', 'Error: Could not get a response. Please try again.', new Date().toISOString());
        } finally {
            sendMessageBtn.disabled = false;
            recordBtn.disabled = false;
            messageInput.disabled = false;
            messageInput.placeholder = 'Type your message or record audio...';
            messageInput.focus();
        }
    }

    async function sendAudioMessage(audioBlob) {
    if (!currentUserId || typeof currentUserId !== 'string' || currentUserId.trim() === '') {
        alert('User ID is missing or invalid. Please enter one and click "Load Sessions" or "New Chat".');
        userIdInput.focus();
        return;
    }
    if (!currentSessionId || typeof currentSessionId !== 'string' || currentSessionId.trim() === '') {
        alert('No session selected or started. Please click "New Chat" or select an existing session.');
        newChatBtn.focus();
        return;
    }

    let initialSessionName = null;
    if (chatMessagesDiv.innerHTML === '' && currentSessionDisplayName !== currentSessionId) {
        initialSessionName = currentSessionDisplayName;
    }

    const formData = new FormData();
    formData.append('audio_file', audioBlob, 'audio.webm');
    formData.append('user_id', currentUserId);
    formData.append('session_id', currentSessionId);
    if (initialSessionName) {
        formData.append('session_name', initialSessionName);
    }

    try {
        sendMessageBtn.disabled = true;
        recordBtn.disabled = true;
        messageInput.disabled = true;
        messageInput.placeholder = 'Transcribing and thinking...';

        const response = await fetch(`${API_BASE_URL}/chat_audio/`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const userTranscript = pickVoiceTranscription(data);
        console.log('📥 Audio chat response keys:', data && typeof data === 'object' ? Object.keys(data) : []);
        console.log('📥 Voice transcription length:', userTranscript.length);

        const audioData = data.audio_base64 && data.audio_base64.length > 0 ? data.audio_base64 : null;

        const userTs = new Date().toISOString();
        displayMessage(
            'You',
            '_(Audio message)_',
            userTs,
            true,
            null,
            userTranscript
        );

        messageInput.value = userTranscript;

        displayMessage(
            data.display_role,
            data.response,
            new Date().toISOString(),
            false,
            audioData,
            null,
            data.moderation_blocked || false,
            data.moderation_flagged || false
        );

    } catch (error) {
        console.error('Error sending audio message:', error);
        displayMessage('Assistant', 'Error: Could not process audio message. Please try again.', new Date().toISOString());
    } finally {
        sendMessageBtn.disabled = false;
        recordBtn.disabled = false;
        messageInput.disabled = false;
        messageInput.placeholder = 'Type your message or record audio...';
        messageInput.focus();
    }
}

    async function updateSessionName() {
        if (!currentUserId || !currentSessionId) {
            alert('No session selected to rename.');
            return;
        }
        const newName = sessionNameEditInput.value.trim();
        if (!newName) {
            alert('Session name cannot be empty.');
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/sessions/${currentUserId}/${currentSessionId}/name`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ new_name: newName }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(`HTTP error! status: ${response.status} - ${errorData.detail}`);
            }

            currentSessionDisplayName = newName;
            currentSessionNameSpan.textContent = `Current Session: ${newName}`;
            sessionNameDisplay.textContent = newName;
            sessionNameContainer.classList.remove('editing');

            await loadSessions(currentUserId);

        } catch (error) {
            console.error('Error updating session name:', error);
            alert(`Failed to update session name: ${error.message}`);
        }
    }

    // ===== EVENT LISTENERS =====

    loadSessionsBtn.addEventListener('click', () => {
        loadSessions(userIdInput.value.trim());
    });

    newChatBtn.addEventListener('click', async () => {
        const newUserId = userIdInput.value.trim();
        if (!newUserId) {
            alert('Please enter a User ID to start a new chat.');
            userIdInput.focus();
            return;
        }
        
        currentUserId = newUserId;
        const newSessionId = generateUuid();
        const defaultSessionName = `New Chat - ${new Date().toLocaleDateString()}`;
        
        await selectAndLoadSession(currentUserId, newSessionId, defaultSessionName);
        messageInput.focus();
    });

    sendMessageBtn.addEventListener('click', sendTextMessage);
    
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendTextMessage();
        }
    });

    // Auto-resize textarea
    messageInput.addEventListener('input', () => {
        messageInput.style.height = 'auto';
        messageInput.style.height = (messageInput.scrollHeight) + 'px';
    });

    // Session name editing
    sessionNameDisplay.addEventListener('click', () => {
        if (currentSessionId && currentUserId) {
            sessionNameContainer.classList.add('editing');
            sessionNameEditInput.focus();
            sessionNameEditInput.select();
        }
    });

    sessionNameEditBtn.addEventListener('click', updateSessionName);
    
    sessionNameEditInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            updateSessionName();
        }
    });

    sessionNameEditInput.addEventListener('blur', () => {
        setTimeout(() => {
            sessionNameContainer.classList.remove('editing');
        }, 150);
    });

    // Audio Recording
    recordBtn.addEventListener('click', async () => {
        if (!isRecording) {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];

                mediaRecorder.ondataavailable = event => {
                    audioChunks.push(event.data);
                };

                mediaRecorder.onstop = () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    sendAudioMessage(audioBlob);
                    stream.getTracks().forEach(track => track.stop());
                };

                mediaRecorder.start();
                recordBtn.classList.add('recording');
                isRecording = true;
                messageInput.placeholder = 'Recording audio...';
                messageInput.disabled = true;
                sendMessageBtn.disabled = true;
            } catch (err) {
                console.error('Error accessing microphone:', err);
                alert('Could not access microphone. Please ensure it is connected and permissions are granted.');
            }
        } else {
            if (mediaRecorder && mediaRecorder.state === 'recording') {
                mediaRecorder.stop();
            }
            recordBtn.classList.remove('recording');
            isRecording = false;
            messageInput.placeholder = 'Type your message or record audio...';
            messageInput.disabled = false;
            sendMessageBtn.disabled = false;
        }
    });

    // Voice Clone Modal
    const voiceCloneBtn = document.getElementById('voiceCloneBtn');
    const voiceCloneModal = document.getElementById('voiceCloneModal');
    const closeModalBtn = document.getElementById('closeModalBtn');

    voiceCloneBtn.addEventListener('click', () => {
        voiceCloneModal.classList.add('active');
    });

    closeModalBtn.addEventListener('click', () => {
        voiceCloneModal.classList.remove('active');
    });

    voiceCloneModal.addEventListener('click', (e) => {
        if (e.target === voiceCloneModal) {
            voiceCloneModal.classList.remove('active');
        }
    });

    // Plan buttons
    const planButtons = document.querySelectorAll('.plan-btn');
    planButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            alert('Thank you for your interest! This feature is coming soon.');
        });
    });


    // Initial state
    sessionList.innerHTML = '<li style="color: #94a3b8; text-align: center; padding: 20px;">Enter User ID and click "Load Sessions" or "New Chat".</li>';
    currentSessionNameSpan.textContent = 'Current Session: No User ID/Session';
    sessionNameDisplay.textContent = 'No Session Selected';
    sessionNameEditInput.value = '';
    clearChat();
});