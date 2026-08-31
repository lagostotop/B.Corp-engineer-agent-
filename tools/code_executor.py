# tools/code_executor.py
import subprocess
import tempfile
import os
import json
import ast
from typing import Dict, Any, Optional

class CodeExecutor:
    def __init__(self):
        self.supported_languages = {
            "python": self._execute_python,
            "javascript": self._execute_javascript,
            "typescript": self._execute_typescript,
            "bash": self._execute_bash
        }
        
    def execute(self, code: str, language: str = "python", timeout: int = 30) -> Dict[str, Any]:
        """Execute code safely"""
        if language not in self.supported_languages:
            return {
                "success": False,
                "error": f"Unsupported language: {language}"
            }
            
        # Validate code for safety
        if not self._is_safe_code(code, language):
            return {
                "success": False,
                "error": "Code rejected for security reasons"
            }
            
        try:
            result = self.supported_languages[language](code, timeout)
            return result
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Execution timed out after {timeout} seconds"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Execution error: {str(e)}"
            }
            
    def _is_safe_code(self, code: str, language: str) -> bool:
        """Check for dangerous operations"""
        dangerous_patterns = [
            "subprocess",
            "os.system",
            "eval",
            "exec",
            "open",
            "file",
            "importlib",
            "__import__",
            "shutil",
            "rmtree",
            "chmod",
            "chown",
            "setuid",
            "setgid",
            "socket",
            "requests",
            "urllib"
        ]
        
        # For Python, use AST to detect dangerous imports
        if language == "python":
            try:
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name in dangerous_patterns:
                                return False
                    elif isinstance(node, ast.ImportFrom):
                        if node.module in dangerous_patterns:
                            return False
            except:
                return False
                
        # Simple pattern matching for other languages
        for pattern in dangerous_patterns:
            if pattern in code.lower():
                return False
                
        return True
        
    def _execute_python(self, code: str, timeout: int) -> Dict[str, Any]:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.write("\n\n# Capture output\nimport sys\nsys.stdout.write(str(locals()))")
            temp_path = f.name
            
        try:
            # Run with timeout
            result = subprocess.run(
                ["python3", temp_path],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }
        finally:
            os.unlink(temp_path)
            
    def _execute_javascript(self, code: str, timeout: int) -> Dict[str, Any]:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(code)
            temp_path = f.name
            
        try:
            result = subprocess.run(
                ["node", temp_path],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }
        finally:
            os.unlink(temp_path)
