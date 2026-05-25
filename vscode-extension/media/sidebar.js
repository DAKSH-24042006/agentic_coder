(function () {
    const vscode = acquireVsCodeApi();

    // DOM Elements
    const authPanel = document.getElementById('auth-panel');
    const authPassword = document.getElementById('auth-password');
    const btnLogin = document.getElementById('btn-login');
    const authStatus = document.getElementById('auth-status');

    const agentPanel = document.getElementById('agent-panel');
    const projectFilter = document.getElementById('project-filter');
    const promptInput = document.getElementById('prompt-input');
    const btnGenerate = document.getElementById('btn-generate');
    const btnClear = document.getElementById('btn-clear');
    const chatMessages = document.getElementById('chat-messages');

    // Pipeline steps
    const steps = {
        planner: document.getElementById('step-planner'),
        retrieval: document.getElementById('step-retrieval'),
        coding: document.getElementById('step-coding'),
        sandbox: document.getElementById('step-sandbox'),
        reviewer: document.getElementById('step-reviewer')
    };

    let activeAgentMessageElement = null;

    // Login Handler
    btnLogin.addEventListener('click', () => {
        const password = authPassword.value;
        if (!password) {
            authStatus.innerText = 'Password cannot be empty.';
            return;
        }
        authStatus.innerText = 'Authenticating...';
        vscode.postMessage({
            command: 'login',
            password: password
        });
    });

    // Generate Handler
    btnGenerate.addEventListener('click', () => {
        const prompt = promptInput.value.trim();
        if (!prompt) { return; }

        // Append user prompt to messages
        appendMessage('user', prompt);
        promptInput.value = '';
        resetPipeline();

        // Send to backend via extension context
        vscode.postMessage({
            command: 'generate',
            prompt: prompt,
            projectFilter: projectFilter.value.trim()
        });

        // Setup waiting agent text area
        activeAgentMessageElement = appendMessage('agent', 'Connecting to backend agents...');
    });

    // Clear Chat
    btnClear.addEventListener('click', () => {
        chatMessages.innerHTML = '';
        resetPipeline();
    });

    // Listen to messages from the Extension Host
    window.addEventListener('message', event => {
        const message = event.data;
        switch (message.type) {
            case 'authStatus':
                if (message.authenticated) {
                    authPanel.classList.add('hidden');
                    agentPanel.classList.remove('hidden');
                } else {
                    authStatus.innerText = message.message || 'Authentication failed.';
                }
                break;
                
            case 'stepUpdate':
                updatePipeline(message.node);
                if (activeAgentMessageElement) {
                    if (message.node === 'planner') {
                        activeAgentMessageElement.innerHTML = `<em>Planning implementation...</em><br/><pre>${message.data}</pre>`;
                    } else if (message.node === 'retrieval') {
                        const files = message.data.map(d => `${d.project}/${d.file}`).join('<br/>');
                        activeAgentMessageElement.innerHTML = `<em>Searching codebase index. Found context in:</em><br/><div style="font-size:10px; color:#aaa; margin-top:5px;">${files}</div>`;
                    } else if (message.node === 'coding') {
                        activeAgentMessageElement.innerHTML = `<em>Generating code solution...</em>`;
                    } else if (message.node === 'tool_execution') {
                        const exitCode = message.data.exit_code;
                        const statusColor = exitCode === 0 ? '#00ff66' : '#ff6666';
                        activeAgentMessageElement.innerHTML = `<em>Running Docker Sandbox Tests:</em><br/>` + 
                            `<span style="color:${statusColor}">Exit Code: ${exitCode}</span><br/>` + 
                            `<pre>${message.data.stdout || message.data.stderr}</pre>`;
                    } else if (message.node === 'reviewer') {
                        activeAgentMessageElement.innerHTML += `<br/><em>Reviewing architectural structure:</em><pre>${message.data}</pre>`;
                    } else if (message.node === 'final_output') {
                        // Complete output received. Write markdown-formatted code
                        const code = message.data.code;
                        activeAgentMessageElement.innerHTML = `<h3>Generated Solution</h3>` + 
                            `<pre><code>${escapeHtml(code)}</code></pre>`;
                        activeAgentMessageElement = null; // Reset pointer
                    }
                }
                break;

            case 'error':
                if (activeAgentMessageElement) {
                    activeAgentMessageElement.innerHTML = `<span style="color:#ff6666">Error: ${message.message}</span>`;
                    activeAgentMessageElement = null;
                } else {
                    appendMessage('system-msg', `Error: ${message.message}`);
                }
                break;
        }
    });

    // Helper functions
    function appendMessage(sender, text) {
        const div = document.createElement('div');
        div.className = `message ${sender}-msg`;
        div.innerHTML = text.replace(/\n/g, '<br/>');
        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return div;
    }

    function resetPipeline() {
        for (const key in steps) {
            steps[key].className = 'pipeline-step';
        }
    }

    function updatePipeline(node) {
        // Map LangGraph nodes to pipeline UI steps
        let currentStepKey = '';
        if (node === 'planner') { currentStepKey = 'planner'; }
        else if (node === 'retrieval') { currentStepKey = 'retrieval'; }
        else if (node === 'coding') { currentStepKey = 'coding'; }
        else if (node === 'tool_execution') { currentStepKey = 'sandbox'; }
        else if (node === 'reviewer') { currentStepKey = 'reviewer'; }

        if (!currentStepKey) { return; }

        // Set previous steps completed, current active
        const stepKeys = ['planner', 'retrieval', 'coding', 'sandbox', 'reviewer'];
        const targetIdx = stepKeys.indexOf(currentStepKey);

        stepKeys.forEach((key, idx) => {
            const stepEl = steps[key];
            if (idx < targetIdx) {
                stepEl.className = 'pipeline-step completed';
            } else if (idx === targetIdx) {
                stepEl.className = 'pipeline-step active';
            } else {
                stepEl.className = 'pipeline-step';
            }
        });
    }

    function escapeHtml(unsafe) {
        return unsafe
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }
})();
