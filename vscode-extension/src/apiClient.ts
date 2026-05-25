import * as vscode from 'vscode';
import { WorkspaceContext } from './contextEngine';

export interface StreamEvent {
    node: string;
    data: any;
}

export class APIClient {
    private getApiUrl(): string {
        const config = vscode.workspace.getConfiguration('enterpriseCoder');
        return config.get<string>('apiUrl', 'http://localhost:8000');
    }

    private getApiToken(): string {
        const config = vscode.workspace.getConfiguration('enterpriseCoder');
        return config.get<string>('apiToken', '');
    }

    private getUsePeft(): boolean {
        const config = vscode.workspace.getConfiguration('enterpriseCoder');
        return config.get<boolean>('usePeft', true);
    }

    public async login(password: string): Promise<string | null> {
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

            const data = await response.json() as { access_token: string };
            // Save token in configuration
            const config = vscode.workspace.getConfiguration('enterpriseCoder');
            await config.update('apiToken', data.access_token, vscode.ConfigurationTarget.Global);
            return data.access_token;
        } catch (e) {
            console.error('Login error:', e);
            return null;
        }
    }

    public async indexRepository(repoPath: string, projectName: string): Promise<boolean> {
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
        } catch (e) {
            console.error('Indexing request error:', e);
            return false;
        }
    }

    public async generateCompletionStream(
        prompt: string,
        context: WorkspaceContext,
        projectFilter: string | undefined,
        onEvent: (event: StreamEvent) => void,
        onError: (err: string) => void
    ): Promise<void> {
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
                if (done) { break; }
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                
                // Keep the last incomplete line in the buffer
                buffer = lines.pop() || '';

                for (const line of lines) {
                    const trimmed = line.trim();
                    if (trimmed.startsWith('data: ')) {
                        const jsonStr = trimmed.substring(6);
                        try {
                            const event = JSON.parse(jsonStr) as StreamEvent;
                            onEvent(event);
                        } catch (e) {
                            console.error('Error parsing SSE event:', e);
                        }
                    }
                }
            }
        } catch (e: any) {
            onError(`Network request exception: ${e.message || e}`);
        }
    }
}
export const apiClient = new APIClient();
