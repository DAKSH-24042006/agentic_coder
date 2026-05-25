"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.apiClient = exports.APIClient = void 0;
const vscode = __importStar(require("vscode"));
class APIClient {
    getApiUrl() {
        const config = vscode.workspace.getConfiguration('enterpriseCoder');
        return config.get('apiUrl', 'http://localhost:8000');
    }
    getApiToken() {
        const config = vscode.workspace.getConfiguration('enterpriseCoder');
        return config.get('apiToken', '');
    }
    getUsePeft() {
        const config = vscode.workspace.getConfiguration('enterpriseCoder');
        return config.get('usePeft', true);
    }
    async login(password) {
        const url = `${this.getApiUrl()}/api/v1/auth/login`;
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username: 'enterprise_dev',
                    password: password
                })
            });
            if (!response.ok) {
                return null;
            }
            const data = await response.json();
            // Save token in configuration
            const config = vscode.workspace.getConfiguration('enterpriseCoder');
            await config.update('apiToken', data.access_token, vscode.ConfigurationTarget.Global);
            return data.access_token;
        }
        catch (e) {
            console.error('Login error:', e);
            return null;
        }
    }
    async indexRepository(repoPath, projectName) {
        const url = `${this.getApiUrl()}/api/v1/repository/index`;
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.getApiToken()}`
                },
                body: JSON.stringify({
                    project_name: projectName,
                    repo_path: repoPath,
                    tags: ["enterprise-import"]
                })
            });
            return response.ok;
        }
        catch (e) {
            console.error('Indexing request error:', e);
            return false;
        }
    }
    async generateCompletionStream(prompt, context, projectFilter, onEvent, onError) {
        const url = `${this.getApiUrl()}/api/v1/chat/generate`;
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.getApiToken()}`
                },
                body: JSON.stringify({
                    prompt: prompt,
                    workspace_context: context,
                    project_filter: projectFilter || null,
                    use_peft: this.getUsePeft(),
                    stream: true
                })
            });
            if (!response.ok) {
                const text = await response.text();
                onError(`Server error (HTTP ${response.status}): ${text}`);
                return;
            }
            if (!response.body) {
                onError('No response body returned from backend.');
                return;
            }
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            while (true) {
                const { value, done } = await reader.read();
                if (done) {
                    break;
                }
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                // Keep the last incomplete line in the buffer
                buffer = lines.pop() || '';
                for (const line of lines) {
                    const trimmed = line.trim();
                    if (trimmed.startsWith('data: ')) {
                        const jsonStr = trimmed.substring(6);
                        try {
                            const event = JSON.parse(jsonStr);
                            onEvent(event);
                        }
                        catch (e) {
                            console.error('Error parsing SSE event:', e);
                        }
                    }
                }
            }
        }
        catch (e) {
            onError(`Network request exception: ${e.message || e}`);
        }
    }
}
exports.APIClient = APIClient;
exports.apiClient = new APIClient();
//# sourceMappingURL=apiClient.js.map