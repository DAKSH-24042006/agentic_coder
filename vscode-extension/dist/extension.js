"use strict";
var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

// src/extension.ts
var extension_exports = {};
__export(extension_exports, {
  activate: () => activate,
  deactivate: () => deactivate
});
module.exports = __toCommonJS(extension_exports);
var vscode4 = __toESM(require("vscode"));

// src/sidebarProvider.ts
var vscode3 = __toESM(require("vscode"));
var path = __toESM(require("path"));
var fs = __toESM(require("fs"));

// src/apiClient.ts
var vscode = __toESM(require("vscode"));
var APIClient = class {
  getApiUrl() {
    const config = vscode.workspace.getConfiguration("enterpriseCoder");
    return config.get("apiUrl", "http://localhost:8000");
  }
  getApiToken() {
    const config = vscode.workspace.getConfiguration("enterpriseCoder");
    return config.get("apiToken", "");
  }
  getUsePeft() {
    const config = vscode.workspace.getConfiguration("enterpriseCoder");
    return config.get("usePeft", true);
  }
  async login(password) {
    const url = `${this.getApiUrl()}/api/v1/auth/login`;
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: "enterprise_dev",
          password
        })
      });
      if (!response.ok) {
        return null;
      }
      const data = await response.json();
      const config = vscode.workspace.getConfiguration("enterpriseCoder");
      await config.update("apiToken", data.access_token, vscode.ConfigurationTarget.Global);
      return data.access_token;
    } catch (e) {
      console.error("Login error:", e);
      return null;
    }
  }
  async indexRepository(repoPath, projectName) {
    const url = `${this.getApiUrl()}/api/v1/repository/index`;
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${this.getApiToken()}`
        },
        body: JSON.stringify({
          project_name: projectName,
          repo_path: repoPath,
          tags: ["enterprise-import"]
        })
      });
      return response.ok;
    } catch (e) {
      console.error("Indexing request error:", e);
      return false;
    }
  }
  async generateCompletionStream(prompt, context, projectFilter, onEvent, onError) {
    const url = `${this.getApiUrl()}/api/v1/chat/generate`;
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${this.getApiToken()}`
        },
        body: JSON.stringify({
          prompt,
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
        onError("No response body returned from backend.");
        return;
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith("data: ")) {
            const jsonStr = trimmed.substring(6);
            try {
              const event = JSON.parse(jsonStr);
              onEvent(event);
            } catch (e) {
              console.error("Error parsing SSE event:", e);
            }
          }
        }
      }
    } catch (e) {
      onError(`Network request exception: ${e.message || e}`);
    }
  }
};
var apiClient = new APIClient();

// src/contextEngine.ts
var vscode2 = __toESM(require("vscode"));
var VSCodeContextEngine = class {
  static async getContext() {
    const context = {
      open_tabs: [],
      workspace_files: []
    };
    const activeEditor = vscode2.window.activeTextEditor;
    if (activeEditor) {
      const activeDoc = activeEditor.document;
      context.active_file_path = activeDoc.fileName;
      const selection = activeEditor.selection;
      if (!selection.isEmpty) {
        context.selected_code = activeDoc.getText(selection);
      }
    }
    const openDocs = vscode2.workspace.textDocuments;
    const openFilePaths = /* @__PURE__ */ new Set();
    for (const doc of openDocs) {
      if (doc.uri.scheme !== "file") {
        continue;
      }
      openFilePaths.add(doc.fileName);
      context.open_tabs.push(doc.fileName);
      const isActive = activeEditor ? doc.fileName === activeEditor.document.fileName : false;
      const content = this.getLimittedContent(doc);
      context.workspace_files.push({
        path: doc.fileName,
        content,
        is_active: isActive,
        is_open: true,
        language_id: doc.languageId
      });
    }
    const workspaceFolders = vscode2.workspace.workspaceFolders;
    if (workspaceFolders) {
      for (const folder of workspaceFolders) {
        const uris = await vscode2.workspace.findFiles(
          new vscode2.RelativePattern(folder, "**/*.{py,ts,js,go}"),
          "**/node_modules/**",
          15
        );
        for (const uri of uris) {
          if (openFilePaths.has(uri.fsPath)) {
            continue;
          }
          try {
            const doc = await vscode2.workspace.openTextDocument(uri);
            context.workspace_files.push({
              path: doc.fileName,
              content: this.getLimittedContent(doc),
              is_active: false,
              is_open: false,
              language_id: doc.languageId
            });
          } catch (e) {
          }
        }
      }
    }
    return context;
  }
  static getLimittedContent(doc) {
    if (doc.lineCount <= 250) {
      return doc.getText();
    }
    const lines = [];
    for (let i = 0; i < 250; i++) {
      lines.push(doc.lineAt(i).text);
    }
    lines.push("// ... [Rest of file truncated by VSCode Context Engine] ...");
    return lines.join("\n");
  }
};

// src/sidebarProvider.ts
var SidebarProvider = class {
  constructor(_extensionUri) {
    this._extensionUri = _extensionUri;
  }
  static {
    this.viewType = "enterprise-coder-chat-view";
  }
  resolveWebviewView(webviewView, context, _token) {
    this._view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri]
    };
    webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);
    webviewView.webview.onDidReceiveMessage(async (data) => {
      switch (data.command) {
        case "login": {
          const token = await apiClient.login(data.password);
          if (token) {
            webviewView.webview.postMessage({ type: "authStatus", authenticated: true });
            vscode3.window.showInformationMessage("Successfully connected to Enterprise Coding Backend.");
          } else {
            webviewView.webview.postMessage({
              type: "authStatus",
              authenticated: false,
              message: "Invalid access code or backend unreachable."
            });
          }
          break;
        }
        case "generate": {
          try {
            const workspaceContext = await VSCodeContextEngine.getContext();
            await apiClient.generateCompletionStream(
              data.prompt,
              workspaceContext,
              data.projectFilter,
              (event) => {
                webviewView.webview.postMessage({
                  type: "stepUpdate",
                  node: event.node,
                  data: event.data
                });
              },
              (errMsg) => {
                webviewView.webview.postMessage({ type: "error", message: errMsg });
              }
            );
          } catch (err) {
            webviewView.webview.postMessage({ type: "error", message: err.message || err });
          }
          break;
        }
      }
    });
  }
  _getHtmlForWebview(webview) {
    const mediaPath = path.join(this._extensionUri.fsPath, "media");
    const htmlPath = path.join(mediaPath, "sidebar.html");
    let html = fs.readFileSync(htmlPath, "utf8");
    const cssUri = webview.asWebviewUri(vscode3.Uri.file(path.join(mediaPath, "sidebar.css")));
    const jsUri = webview.asWebviewUri(vscode3.Uri.file(path.join(mediaPath, "sidebar.js")));
    html = html.replace("[CSS_URI]", cssUri.toString());
    html = html.replace("[JS_URI]", jsUri.toString());
    return html;
  }
};

// src/extension.ts
function activate(context) {
  console.log("Enterprise AI Coding Agent extension activated.");
  const sidebarProvider = new SidebarProvider(context.extensionUri);
  context.subscriptions.push(
    vscode4.window.registerWebviewViewProvider(
      SidebarProvider.viewType,
      sidebarProvider
    )
  );
  const explainCommand = vscode4.commands.registerCommand("enterprise-coder.explainCode", async () => {
    const editor = vscode4.window.activeTextEditor;
    if (!editor) {
      vscode4.window.showWarningMessage("No active code editor found.");
      return;
    }
    const selectionText = editor.document.getText(editor.selection);
    if (!selectionText) {
      vscode4.window.showInformationMessage("Please select some code to explain.");
      return;
    }
    await vscode4.commands.executeCommand("workbench.view.extension.enterprise-coder-container");
    vscode4.window.showInformationMessage("Explaining selection using Enterprise AI Planner...");
  });
  context.subscriptions.push(explainCommand);
  const inlineCommand = vscode4.commands.registerCommand("enterprise-coder.generateInline", async () => {
    const editor = vscode4.window.activeTextEditor;
    if (!editor) {
      vscode4.window.showWarningMessage("No active code editor found.");
      return;
    }
    const document = editor.document;
    const selection = editor.selection;
    const prompt = await vscode4.window.showInputBox({
      prompt: "Explain what code you want to generate at the cursor position",
      placeHolder: "e.g., implement a thread-safe singleton connection pool"
    });
    if (!prompt) {
      return;
    }
    vscode4.window.withProgress({
      location: vscode4.ProgressLocation.Notification,
      title: "Enterprise AI: Generating code snippet...",
      cancellable: false
    }, async (progress) => {
      try {
        const workspaceContext = await VSCodeContextEngine.getContext();
        let fullSnippet = "";
        await apiClient.generateCompletionStream(
          prompt,
          workspaceContext,
          void 0,
          (event) => {
            if (event.node === "final_output") {
              fullSnippet = event.data.code;
            }
          },
          (err) => {
            vscode4.window.showErrorMessage(`Generation failed: ${err}`);
          }
        );
        if (fullSnippet) {
          await editor.edit((editBuilder) => {
            editBuilder.replace(selection, fullSnippet);
          });
          vscode4.window.showInformationMessage("Solution inserted successfully.");
        }
      } catch (err) {
        vscode4.window.showErrorMessage(`Error inserting snippet: ${err.message || err}`);
      }
    });
  });
  context.subscriptions.push(inlineCommand);
  const indexCommand = vscode4.commands.registerCommand("enterprise-coder.indexWorkspace", async () => {
    const workspaceFolders = vscode4.workspace.workspaceFolders;
    if (!workspaceFolders || workspaceFolders.length === 0) {
      vscode4.window.showWarningMessage("No workspace folders open to index.");
      return;
    }
    const defaultPath = workspaceFolders[0].uri.fsPath;
    const projectName = await vscode4.window.showInputBox({
      prompt: "Enter Project Name for Vector DB Index",
      placeHolder: "e.g., core-billing-engine"
    });
    if (!projectName) {
      return;
    }
    vscode4.window.showInformationMessage(`Queued index request for project: ${projectName}...`);
    const success = await apiClient.indexRepository(defaultPath, projectName);
    if (success) {
      vscode4.window.showInformationMessage(`RAG pipeline successfully scheduled indexing for ${projectName}.`);
    } else {
      vscode4.window.showErrorMessage(`Failed to connect to RAG indexer endpoint.`);
    }
  });
  context.subscriptions.push(indexCommand);
}
function deactivate() {
  console.log("Enterprise AI Coding Agent extension deactivated.");
}
// Annotate the CommonJS export names for ESM import in node:
0 && (module.exports = {
  activate,
  deactivate
});
//# sourceMappingURL=extension.js.map
