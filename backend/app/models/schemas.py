from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# Authentication
class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

# Workspace Context Elements
class WorkspaceFile(BaseModel):
    path: str
    content: str
    is_active: bool = False
    is_open: bool = False
    language_id: Optional[str] = None

class WorkspaceContext(BaseModel):
    active_file_path: Optional[str] = None
    selected_code: Optional[str] = None
    open_tabs: List[str] = Field(default_factory=list)
    workspace_files: List[WorkspaceFile] = Field(default_factory=list)

# Context Engine API Contracts
class ContextRequest(BaseModel):
    context: WorkspaceContext
    max_tokens: int = 3000

class ContextResponse(BaseModel):
    formatted_context: str
    tokens_used: int
    included_files: List[str]

# RAG & Indexer API Contracts
class IndexRequest(BaseModel):
    project_name: str
    repo_path: str
    framework: Optional[str] = None
    language: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

class IndexResponse(BaseModel):
    status: str
    chunks_indexed: int
    project_name: str

class SearchResult(BaseModel):
    filepath: str
    code_content: str
    project_name: str
    score: float
    language: str
    framework: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)

# Completion & Agent Generation Contracts
class QueryRequest(BaseModel):
    prompt: str
    workspace_context: Optional[WorkspaceContext] = None
    project_filter: Optional[str] = None
    use_peft: bool = True
    stream: bool = True

class QueryResponse(BaseModel):
    response: str
    sources: List[SearchResult] = Field(default_factory=list)

# Sandbox Execution API Contracts
class SandboxExecutionRequest(BaseModel):
    command: str
    files: Dict[str, str] = Field(default_factory=dict, description="Filename to content mapping to create before run")
    timeout_seconds: Optional[int] = None

class SandboxExecutionResponse(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    execution_time_seconds: float
