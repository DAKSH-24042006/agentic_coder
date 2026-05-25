import os
import re
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from app.core.config import settings

class RagService:
    def __init__(self):
        self.client = None
        self.embedding_model = None
        self._initialized = False

    def initialize(self):
        """
        Lazily initialize connections and models to prevent blocking backend startup.
        """
        if self._initialized:
            return
            
        try:
            self.client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                api_key=settings.QDRANT_API_KEY
            )
            
            # Setup collection
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if settings.QDRANT_COLLECTION not in collection_names:
                self.client.create_collection(
                    collection_name=settings.QDRANT_COLLECTION,
                    vectors_config=VectorParams(
                        size=settings.EMBEDDING_DIMENSION,
                        distance=Distance.COSINE
                    )
                )
        except Exception as e:
            print(f"Error initializing Qdrant client: {e}. Running in fallback/mock mode.")
            self.client = None
            
        try:
            # Import sentence_transformers inside initialization
            from sentence_transformers import SentenceTransformer
            self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        except Exception as e:
            print(f"Error initializing embedding model: {e}. Running with mock embeddings.")
            self.embedding_model = None
            
        self._initialized = True

    def get_embedding(self, text: str) -> List[float]:
        self.initialize()
        if self.embedding_model:
            return self.embedding_model.encode(text).tolist()
        # Fallback dummy embedding (zero vector)
        return [0.0] * settings.EMBEDDING_DIMENSION

    def chunk_code(self, code: str, filepath: str, max_lines: int = 50, overlap: int = 10) -> List[Dict[str, Any]]:
        """
        Chunks code intelligently by scanning for logical boundaries (functions and classes).
        """
        lines = code.splitlines()
        chunks = []
        
        # Scan for function/class declaration line numbers
        declaration_indices = []
        for i, line in enumerate(lines):
            # Matches python def/class, TS/JS class/function, and C++/Java public/private methods
            if re.match(r"^\s*(def |class |function |export |public |private |async def )", line):
                declaration_indices.append(i)
                
        # If no logical blocks found, fall back to sliding window of line counts
        if not declaration_indices:
            i = 0
            while i < len(lines):
                chunk_lines = lines[i : i + max_lines]
                content = "\n".join(chunk_lines)
                chunks.append({
                    "content": content,
                    "start_line": i + 1,
                    "end_line": min(i + max_lines, len(lines)),
                    "type": "block"
                })
                i += max_lines - overlap
            return chunks

        # Otherwise, chunk based on declarations
        declaration_indices.append(len(lines))  # Add boundary element
        for idx in range(len(declaration_indices) - 1):
            start = declaration_indices[idx]
            # Group declarations together if they are very short, otherwise take up to next declaration
            end = declaration_indices[idx + 1]
            
            # Bound the chunk size to avoid extremely large files in a single chunk
            if end - start > max_lines:
                end = start + max_lines
                
            chunk_lines = lines[start:end]
            content = "\n".join(chunk_lines)
            
            # Simple heuristic to determine if it's a class or function
            decl_line = lines[start]
            chunk_type = "function"
            if "class " in decl_line:
                chunk_type = "class"
                
            chunks.append({
                "content": content,
                "start_line": start + 1,
                "end_line": end,
                "type": chunk_type
            })
            
        return chunks

    def index_project_files(self, project_name: str, repo_path: str, framework: Optional[str] = None, language: Optional[str] = None, tags: List[str] = None) -> int:
        self.initialize()
        if not self.client:
            print("Cannot index files: Qdrant client not initialized.")
            return 0
            
        tags = tags or []
        indexed_points = 0
        point_batch = []
        
        for root, _, files in os.walk(repo_path):
            for file in files:
                # Target code extensions
                if not file.endswith((".py", ".ts", ".js", ".tsx", ".jsx", ".java", ".cpp", ".h", ".go", ".rs")):
                    continue
                    
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo_path)
                
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception:
                    continue
                    
                chunks = self.chunk_code(content, rel_path)
                file_lang = language or file.split('.')[-1]
                
                # Simple import extractor for chunk dependencies
                dependencies = list(set(re.findall(r"^\s*(?:import|from)\s+([a-zA-Z0-9_\.]+)", content, re.MULTILINE)))
                
                for chunk in chunks:
                    chunk_text = chunk["content"]
                    # Contextualize chunk header to include file and project info
                    vector_text = f"Project: {project_name}\nFile: {rel_path}\nType: {chunk['type']}\nContent:\n{chunk_text}"
                    embedding = self.get_embedding(vector_text)
                    
                    point_id = hash(f"{project_name}:{rel_path}:{chunk['start_line']}") & 0xFFFFFFFFFFFFFFFF
                    
                    payload = {
                        "project_name": project_name,
                        "filepath": rel_path,
                        "start_line": chunk["start_line"],
                        "end_line": chunk["end_line"],
                        "type": chunk["type"],
                        "code_content": chunk_text,
                        "language": file_lang,
                        "framework": framework,
                        "dependencies": dependencies,
                        "tags": tags
                    }
                    
                    point_batch.append(PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload=payload
                    ))
                    
                    if len(point_batch) >= 50:
                        self.client.upsert(
                            collection_name=settings.QDRANT_COLLECTION,
                            points=point_batch
                        )
                        indexed_points += len(point_batch)
                        point_batch = []
                        
        if point_batch:
            self.client.upsert(
                collection_name=settings.QDRANT_COLLECTION,
                points=point_batch
            )
            indexed_points += len(point_batch)
            
        return indexed_points

    def hybrid_search(self, query: str, top_k: int = 5, project_filter: Optional[str] = None, workspace_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Executes a semantic vector search combined with a hybrid re-ranking algorithm scoring on
        metadata similarity, framework matching, active file dependencies, and project scope.
        """
        self.initialize()
        if not self.client:
            print("Cannot search: Qdrant client not initialized.")
            return []
            
        query_vector = self.get_embedding(query)
        
        # Setup vector search filter if project scope is enforced
        qdrant_filter = None
        if project_filter:
            qdrant_filter = Filter(
                must=[FieldCondition(key="project_name", match=MatchValue(value=project_filter))]
            )
            
        # 1. Fetch Candidates from Qdrant
        search_results = self.client.search(
            collection_name=settings.QDRANT_COLLECTION,
            query_vector=query_vector,
            query_filter=qdrant_filter,
            limit=top_k * 3  # Over-sample to enable hybrid ranking
        )
        
        scored_candidates = []
        
        # 2. Extract Workspace context features for re-ranking
        active_filepath = ""
        workspace_frameworks = set()
        active_dependencies = set()
        
        if workspace_context:
            active_filepath = workspace_context.get("active_file_path", "")
            # Deduce framework from open tab list or paths (e.g. package.json react/next)
            for file in workspace_context.get("workspace_files", []):
                for dep in file.get("dependencies", []):
                    active_dependencies.add(dep)
                if "package.json" in file.get("path", ""):
                    content = file.get("content", "")
                    if "react" in content: workspace_frameworks.add("react")
                    if "next" in content: workspace_frameworks.add("next")
                if "requirements.txt" in file.get("path", ""):
                    content = file.get("content", "")
                    if "fastapi" in content: workspace_frameworks.add("fastapi")
                    if "django" in content: workspace_frameworks.add("django")
                    
        # 3. Apply Re-ranking scores
        for res in search_results:
            payload = res.payload
            semantic_score = res.score
            
            # Hybrid scaling factor
            hybrid_modifier = 0.0
            
            # Workspace relevance boost
            if active_filepath:
                # Boost files sharing the same project or subdirectory structure
                if payload.get("project_name") in active_filepath:
                    hybrid_modifier += 0.15
                    
            # Framework alignment boost
            framework = payload.get("framework")
            if framework and framework.lower() in workspace_frameworks:
                hybrid_modifier += 0.1
                
            # Dependency Graph intersection boost
            candidate_deps = payload.get("dependencies", [])
            overlap = set(candidate_deps).intersection(active_dependencies)
            if overlap:
                hybrid_modifier += min(len(overlap) * 0.03, 0.15)  # Cap boost at 0.15
                
            # Final scoring combination
            final_score = semantic_score + hybrid_modifier
            
            scored_candidates.append({
                "filepath": payload.get("filepath"),
                "code_content": payload.get("code_content"),
                "project_name": payload.get("project_name"),
                "score": final_score,
                "language": payload.get("language"),
                "framework": payload.get("framework"),
                "dependencies": candidate_deps,
                "tags": payload.get("tags", [])
            })
            
        # Re-sort based on the hybrid final score and return top_k
        scored_candidates.sort(key=lambda x: x["score"], reverse=True)
        return scored_candidates[:top_k]

rag_service = RagService()
