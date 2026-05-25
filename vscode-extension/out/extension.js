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
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const sidebarProvider_1 = require("./sidebarProvider");
const apiClient_1 = require("./apiClient");
const contextEngine_1 = require("./contextEngine");
function activate(context) {
    console.log('Enterprise AI Coding Agent extension activated.');
    // 1. Register Sidebar Webview Panel
    const sidebarProvider = new sidebarProvider_1.SidebarProvider(context.extensionUri);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider(sidebarProvider_1.SidebarProvider.viewType, sidebarProvider));
    // 2. Register Explain Code Command
    const explainCommand = vscode.commands.registerCommand('enterprise-coder.explainCode', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('No active code editor found.');
            return;
        }
        const selectionText = editor.document.getText(editor.selection);
        if (!selectionText) {
            vscode.window.showInformationMessage('Please select some code to explain.');
            return;
        }
        // Focus sidebar panel and prompt explain
        await vscode.commands.executeCommand('workbench.view.extension.enterprise-coder-container');
        vscode.window.showInformationMessage('Explaining selection using Enterprise AI Planner...');
        // We can communicate with the sidebar to trigger explanations automatically
    });
    context.subscriptions.push(explainCommand);
    // 3. Register Inline Completion Generator Command
    const inlineCommand = vscode.commands.registerCommand('enterprise-coder.generateInline', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('No active code editor found.');
            return;
        }
        const document = editor.document;
        const selection = editor.selection;
        const prompt = await vscode.window.showInputBox({
            prompt: 'Explain what code you want to generate at the cursor position',
            placeHolder: 'e.g., implement a thread-safe singleton connection pool'
        });
        if (!prompt) {
            return;
        }
        vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: 'Enterprise AI: Generating code snippet...',
            cancellable: false
        }, async (progress) => {
            try {
                const workspaceContext = await contextEngine_1.VSCodeContextEngine.getContext();
                let fullSnippet = '';
                await apiClient_1.apiClient.generateCompletionStream(prompt, workspaceContext, undefined, (event) => {
                    if (event.node === 'final_output') {
                        fullSnippet = event.data.code;
                    }
                }, (err) => {
                    vscode.window.showErrorMessage(`Generation failed: ${err}`);
                });
                if (fullSnippet) {
                    // Insert at current cursor selection
                    await editor.edit(editBuilder => {
                        editBuilder.replace(selection, fullSnippet);
                    });
                    vscode.window.showInformationMessage('Solution inserted successfully.');
                }
            }
            catch (err) {
                vscode.window.showErrorMessage(`Error inserting snippet: ${err.message || err}`);
            }
        });
    });
    context.subscriptions.push(inlineCommand);
    // 4. Register Indexing Command (Workspace RAG ingestion)
    const indexCommand = vscode.commands.registerCommand('enterprise-coder.indexWorkspace', async () => {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
            vscode.window.showWarningMessage('No workspace folders open to index.');
            return;
        }
        const defaultPath = workspaceFolders[0].uri.fsPath;
        const projectName = await vscode.window.showInputBox({
            prompt: 'Enter Project Name for Vector DB Index',
            placeHolder: 'e.g., core-billing-engine'
        });
        if (!projectName) {
            return;
        }
        vscode.window.showInformationMessage(`Queued index request for project: ${projectName}...`);
        const success = await apiClient_1.apiClient.indexRepository(defaultPath, projectName);
        if (success) {
            vscode.window.showInformationMessage(`RAG pipeline successfully scheduled indexing for ${projectName}.`);
        }
        else {
            vscode.window.showErrorMessage(`Failed to connect to RAG indexer endpoint.`);
        }
    });
    context.subscriptions.push(indexCommand);
}
function deactivate() {
    console.log('Enterprise AI Coding Agent extension deactivated.');
}
//# sourceMappingURL=extension.js.map