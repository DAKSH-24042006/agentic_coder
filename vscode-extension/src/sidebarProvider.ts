import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { apiClient } from './apiClient';
import { VSCodeContextEngine } from './contextEngine';

export class SidebarProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'enterprise-coder-chat-view';
    private _view?: vscode.WebviewView;

    constructor(private readonly _extensionUri: vscode.Uri) {}

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri]
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        // Listen for messages from Webview
        webviewView.webview.onDidReceiveMessage(async (data) => {
            switch (data.command) {
                case 'login': {
                    const token = await apiClient.login(data.password);
                    if (token) {
                        webviewView.webview.postMessage({ type: 'authStatus', authenticated: true });
                        vscode.window.showInformationMessage('Successfully connected to Enterprise Coding Backend.');
                    } else {
                        webviewView.webview.postMessage({ 
                            type: 'authStatus', 
                            authenticated: false, 
                            message: 'Invalid access code or backend unreachable.' 
                        });
                    }
                    break;
                }
                case 'generate': {
                    try {
                        const workspaceContext = await VSCodeContextEngine.getContext();
                        
                        await apiClient.generateCompletionStream(
                            data.prompt,
                            workspaceContext,
                            data.projectFilter,
                            (event) => {
                                // Send LangGraph status updates back to webview
                                webviewView.webview.postMessage({
                                    type: 'stepUpdate',
                                    node: event.node,
                                    data: event.data
                                });
                            },
                            (errMsg) => {
                                webviewView.webview.postMessage({ type: 'error', message: errMsg });
                            }
                        );
                    } catch (err: any) {
                        webviewView.webview.postMessage({ type: 'error', message: err.message || err });
                    }
                    break;
                }
            }
        });
    }

    private _getHtmlForWebview(webview: vscode.Webview): string {
        const mediaPath = path.join(this._extensionUri.fsPath, 'media');
        
        const htmlPath = path.join(mediaPath, 'sidebar.html');
        let html = fs.readFileSync(htmlPath, 'utf8');

        // Resolve Webview URIs
        const cssUri = webview.asWebviewUri(vscode.Uri.file(path.join(mediaPath, 'sidebar.css')));
        const jsUri = webview.asWebviewUri(vscode.Uri.file(path.join(mediaPath, 'sidebar.js')));

        html = html.replace('[CSS_URI]', cssUri.toString());
        html = html.replace('[JS_URI]', jsUri.toString());

        return html;
    }
}
