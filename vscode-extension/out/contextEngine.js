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
exports.VSCodeContextEngine = void 0;
const vscode = __importStar(require("vscode"));
class VSCodeContextEngine {
    static async getContext() {
        const context = {
            open_tabs: [],
            workspace_files: []
        };
        const activeEditor = vscode.window.activeTextEditor;
        if (activeEditor) {
            const activeDoc = activeEditor.document;
            context.active_file_path = activeDoc.fileName;
            // Extract active code selection
            const selection = activeEditor.selection;
            if (!selection.isEmpty) {
                context.selected_code = activeDoc.getText(selection);
            }
        }
        // Get all open text documents in memory
        const openDocs = vscode.workspace.textDocuments;
        const openFilePaths = new Set();
        for (const doc of openDocs) {
            // Ignore system outputs or webview schemas
            if (doc.uri.scheme !== 'file') {
                continue;
            }
            openFilePaths.add(doc.fileName);
            context.open_tabs.push(doc.fileName);
            const isActive = activeEditor ? doc.fileName === activeEditor.document.fileName : false;
            // Limit content size to prevent overflowing workspace payloads (e.g. read first 500 lines)
            const content = this.getLimittedContent(doc);
            context.workspace_files.push({
                path: doc.fileName,
                content: content,
                is_active: isActive,
                is_open: true,
                language_id: doc.languageId
            });
        }
        // Fetch other files in the workspace directory (limited directory walk for context references)
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (workspaceFolders) {
            for (const folder of workspaceFolders) {
                // Find up to 15 relevant files in workspace that are not already open
                const uris = await vscode.workspace.findFiles(new vscode.RelativePattern(folder, '**/*.{py,ts,js,go}'), '**/node_modules/**', 15);
                for (const uri of uris) {
                    if (openFilePaths.has(uri.fsPath)) {
                        continue;
                    }
                    try {
                        const doc = await vscode.workspace.openTextDocument(uri);
                        context.workspace_files.push({
                            path: doc.fileName,
                            content: this.getLimittedContent(doc),
                            is_active: false,
                            is_open: false,
                            language_id: doc.languageId
                        });
                    }
                    catch (e) {
                        // Safe ignore unreadable files
                    }
                }
            }
        }
        return context;
    }
    static getLimittedContent(doc) {
        // Read up to 250 lines to prevent token bloating
        if (doc.lineCount <= 250) {
            return doc.getText();
        }
        const lines = [];
        for (let i = 0; i < 250; i++) {
            lines.push(doc.lineAt(i).text);
        }
        lines.push('// ... [Rest of file truncated by VSCode Context Engine] ...');
        return lines.join('\n');
    }
}
exports.VSCodeContextEngine = VSCodeContextEngine;
//# sourceMappingURL=contextEngine.js.map