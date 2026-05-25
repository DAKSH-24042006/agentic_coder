import re
from typing import List, Dict, Tuple, Optional
from app.models.schemas import WorkspaceContext, WorkspaceFile

class ContextEngineService:
    def __init__(self):
        # A simple estimation of tokens: 4 characters per token
        self.char_per_token = 4

    def estimate_tokens(self, text: str) -> int:
        return len(text) // self.char_per_token

    def _extract_imports(self, code: str) -> List[str]:
        """
        Parses common import statements to extract modules and symbols.
        """
        imports = []
        # Pattern for: import module_name
        import_pat = re.compile(r"^\s*import\s+([a-zA-Z0-9_\.]+)", re.MULTILINE)
        # Pattern for: from module_name import symbol_name
        from_pat = re.compile(r"^\s*from\s+([a-zA-Z0-9_\.]+)\s+import", re.MULTILINE)
        
        imports.extend(import_pat.findall(code))
        imports.extend(from_pat.findall(code))
        return [imp.split('.')[-1] for imp in imports]

    def _extract_outline(self, code: str, language_id: str = "python") -> str:
        """
        Extracts structural outlines (classes and functions) to compress context.
        """
        outline_lines = []
        lines = code.splitlines()
        
        # Simple extraction rules based on language
        if language_id in {"python", "py"}:
            for line in lines:
                if line.strip().startswith(("def ", "class ")):
                    outline_lines.append(line)
        elif language_id in {"typescript", "javascript", "ts", "js"}:
            for line in lines:
                if line.strip().startswith(("class ", "interface ", "function ", "export class ", "export function ", "export interface ")):
                    outline_lines.append(line)
        else:
            # Fallback compression: take first 20 lines
            return "\n".join(lines[:20]) + "\n... [Code truncated for token compression] ..."
            
        if not outline_lines:
            return "// [Empty file or no structure found]"
            
        return "\n".join(outline_lines)

    def _score_file(self, file: WorkspaceFile, active_file: Optional[WorkspaceFile], imports: List[str]) -> float:
        """
        Calculates a relevance score for a workspace file.
        """
        score = 0.0
        
        if file.is_active:
            return 1000.0  # Active file always max priority
            
        if file.is_open:
            score += 500.0
            
        # Match imports
        filename_no_ext = file.path.split('/')[-1].split('\\')[-1].split('.')[0]
        if filename_no_ext in imports:
            score += 300.0
            
        # Path similarity (structural proximity)
        if active_file:
            active_parts = active_file.path.replace('\\', '/').split('/')
            file_parts = file.path.replace('\\', '/').split('/')
            common_parts = 0
            for ap, fp in zip(active_parts, file_parts):
                if ap == fp:
                    common_parts += 1
                else:
                    break
            score += common_parts * 20.0
            
        return score

    def build_prioritized_context(self, context: WorkspaceContext, max_tokens: int = 3000) -> Tuple[str, int, List[str]]:
        """
        Prioritizes, compresses, and builds the optimal prompt context block from workspace elements.
        """
        active_file = next((f for f in context.workspace_files if f.is_active), None)
        active_imports = self._extract_imports(active_file.content) if active_file else []
        
        # Score each file
        scored_files: List[Tuple[WorkspaceFile, float]] = []
        for f in context.workspace_files:
            score = self._score_file(f, active_file, active_imports)
            scored_files.append((f, score))
            
        # Sort files by descending score
        scored_files.sort(key=lambda x: x[1], reverse=True)
        
        formatted_blocks = []
        current_token_estimate = 0
        included_files = []
        
        # First pass: Include active file and selected code
        if context.selected_code:
            block = f"--- ACTIVE SELECTION ---\n{context.selected_code}\n------------------------\n"
            current_token_estimate += self.estimate_tokens(block)
            formatted_blocks.append(block)
            
        # Second pass: Process workspace files based on ranking
        for file, score in scored_files:
            file_tokens = self.estimate_tokens(file.content)
            
            # If we have space, add full content
            if current_token_estimate + file_tokens < max_tokens:
                block = f"--- FILE: {file.path} (Relevance: {score:.1f}) ---\n{file.content}\n------------------------\n"
                current_token_estimate += self.estimate_tokens(block)
                formatted_blocks.append(block)
                included_files.append(file.path)
            else:
                # Compression mode: extract outline/signatures of the remaining relevant files
                outline = self._extract_outline(file.content, file.language_id or "python")
                outline_block = f"--- FILE OUTLINE (Compressed): {file.path} ---\n{outline}\n------------------------\n"
                outline_tokens = self.estimate_tokens(outline_block)
                
                if current_token_estimate + outline_tokens < max_tokens:
                    current_token_estimate += outline_tokens
                    formatted_blocks.append(outline_block)
                    included_files.append(f"{file.path} (compressed)")
                else:
                    # Token limit fully reached
                    break
                    
        return "\n".join(formatted_blocks), current_token_estimate, included_files

context_engine = ContextEngineService()
