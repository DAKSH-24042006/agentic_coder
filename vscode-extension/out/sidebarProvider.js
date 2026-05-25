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
exports.SidebarProvider = void 0;
const vscode = __importStar(require("vscode"));
const path = __importStar(require("path"));
const fs = __importStar(require("fs"));
const apiClient_1 = require("./apiClient");
const contextEngine_1 = require("./contextEngine");
class SidebarProvider {
    constructor(_extensionUri) {
        this._extensionUri = _extensionUri;
    }
    resolveWebviewView(webviewView, context, _token) {
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
                    const token = await apiClient_1.apiClient.login(data.password);
                    if (token) {
                        webviewView.webview.postMessage({ type: 'authStatus', authenticated: true });
                        vscode.window.showInformationMessage('Successfully connected to Enterprise Coding Backend.');
                    }
                    else {
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
                        const workspaceContext = await contextEngine_1.VSCodeContextEngine.getContext();
                        await apiClient_1.apiClient.generateCompletionStream(data.prompt, workspaceContext, data.projectFilter, (event) => {
                            // Send LangGraph status updates back to webview
                            webviewView.webview.postMessage({
                                type: 'stepUpdate',
                                node: event.node,
                                data: event.data
                            });
                        }, (errMsg) => {
                            webviewView.webview.postMessage({ type: 'error', message: errMsg });
                        });
                    }
                    catch (err) {
                        webviewView.webview.postMessage({ type: 'error', message: err.message || err });
                    }
                    break;
                }
            }
        });
    }
    _getHtmlForWebview(webview) {
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
exports.SidebarProvider = SidebarProvider;
SidebarProvider.viewType = 'enterprise-coder-chat-view';
//# sourceMappingURL=sidebarProvider.js.map