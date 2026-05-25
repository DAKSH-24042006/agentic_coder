import os
import json
import argparse
from typing import List, Dict, Any

class PEFTDatasetGenerator:
    def __init__(self, repo_path: str, output_path: str):
        self.repo_path = repo_path
        self.output_path = output_path
        self.extensions = (".py", ".ts", ".go")

    def _extract_docstring_and_body(self, code: str, ext: str) -> List[Dict[str, str]]:
        """
        Parses functions or modules to create natural pairs of docstrings (instruction)
        and complete, clean implementation (response).
        """
        examples = []
        
        if ext == ".py":
            # Simple Python function regex to find name, docstring, and code block
            # Match def function_name(...): \n\s+"""docstring"""\nbody
            pattern = re_python_fn = r"def\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)\s*->?\s*[^:]*:\n\s+r?\"\"\"([\s\S]*?)\"\"\"([\s\S]*?)(?=\ndef |\nclass |\Z)"
            import re
            matches = re.finditer(pattern, code)
            for match in matches:
                name = match.group(1)
                args = match.group(2)
                docstring = match.group(3).strip()
                body = match.group(4)
                
                # Create example demonstrating type annotation and docstring compliance
                instruction = f"Implement the function '{name}' with arguments ({args}) based on this docstring: {docstring}"
                response = f"def {name}({args}):\n    \"\"\"{docstring}\"\"\"{body}"
                examples.append({
                    "instruction": instruction,
                    "input": f"Language: python\nFunction name: {name}",
                    "output": response
                })
        return examples

    def generate(self):
        dataset: List[Dict[str, Any]] = []
        
        if not os.path.exists(self.repo_path):
            print(f"Error: Path '{self.repo_path}' does not exist.")
            return

        for root, _, files in os.walk(self.repo_path):
            for file in files:
                if not file.endswith(self.extensions):
                    continue
                ext = os.path.splitext(file)[1]
                full_path = os.path.join(root, file)
                
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception:
                    continue
                    
                file_examples = self._extract_docstring_and_body(content, ext)
                dataset.extend(file_examples)

        # Write to JSONL
        with open(self.output_path, "w", encoding="utf-8") as out:
            for item in dataset:
                out.write(json.dumps(item) + "\n")
                
        print(f"Dataset generation complete. Wrote {len(dataset)} examples to {self.output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate PEFT tuning dataset from codebases.")
    parser.add_argument("--repo_path", type=str, required=True, help="Repository root path to scan")
    parser.add_argument("--output_path", type=str, default="peft_dataset.jsonl", help="Output path for JSONL dataset")
    args = parser.parse_args()
    
    generator = PEFTDatasetGenerator(args.repo_path, args.output_path)
    generator.generate()
