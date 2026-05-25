import * as vscode from 'vscode';

export interface WorkspaceFile {
    path: string;
    content: string;
    is_active: boolean;
    is_open: boolean;
    language_id?: string;
}

export interface WorkspaceContext {
    active_file_path?: string;
    selected_code?: string;
    open_tabs: string[];
    workspace_files: WorkspaceFile[];
}

export class VSCodeContextEngine {
    public static async getContext(): Promise<WorkspaceContext> {
        const context: WorkspaceContext = {
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
        const openFilePaths = new Set<string>();

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
                const uris = await vscode.workspace.findFiles(
                    new vscode.RelativePattern(folder, '**/*.{py,ts,js,go}'),
                    '**/node_modules/**',
                    15
                );
                
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
                    } catch (e) {
                        // Safe ignore unreadable files
                    }
                }
            }
        }

        return context;
    }

    private static getLimittedContent(doc: vscode.TextDocument): string {
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
