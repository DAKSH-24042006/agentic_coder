import os
import time
import subprocess
import logging
from typing import Dict, Optional, Tuple
from app.core.config import settings
from app.core.security import validate_sandbox_command, sanitize_output

logger = logging.getLogger(__name__)

class SandboxService:
    def __init__(self):
        self.docker_available = False
        self.client = None
        self._initialize_docker()

    def _initialize_docker(self):
        try:
            import docker
            self.client = docker.from_env()
            self.client.ping()
            self.docker_available = True
            logger.info("Docker SDK initialized and running successfully.")
        except Exception as e:
            logger.warning(
                f"Docker not available or socket connection failed: {e}. "
                "Sandbox service will fall back to local subprocess sandboxing."
            )
            self.docker_available = False

    def run_in_sandbox(self, command: str, files: Dict[str, str], timeout_seconds: Optional[int] = None) -> Tuple[int, str, str, float]:
        """
        Executes a command either in a sandboxed Docker container or local subprocess wrapper.
        """
        if not validate_sandbox_command(command):
            return (
                -1,
                "",
                "Security Exception: Command failed validation allowlist check.",
                0.0
            )

        timeout = timeout_seconds or settings.SANDBOX_TIMEOUT_SECONDS
        start_time = time.time()

        if self.docker_available and self.client:
            return self._run_docker(command, files, timeout, start_time)
        else:
            return self._run_local_fallback(command, files, timeout, start_time)

    def _run_docker(self, command: str, files: Dict[str, str], timeout: int, start_time: float) -> Tuple[int, str, str, float]:
        import docker
        container = None
        try:
            # 1. Create a temporary volume/mapping for the workspace files
            # Instead of physical volume mounts, we write files directly into the container using exec or build tarballs.
            # To simplify, we spin up the container with sleep, write files, exec command, and destroy.
            container = self.client.containers.run(
                image=settings.SANDBOX_DOCKER_IMAGE,
                command="sleep 300",  # Keep alive while we execute
                detach=True,
                network_mode="none",  # Security: Disable network inside sandbox
                mem_limit="512m",     # Security: Resource limits
                nano_cpus=1000000000, # Security: Max 1 CPU core
                user="nobody"         # Security: Run as non-privileged
            )

            # 2. Write files to container
            # We construct a command to dump files to disk inside container
            for filepath, content in files.items():
                # Escape single quotes in contents
                escaped_content = content.replace("'", "'\\''")
                # Create directories
                dirname = os.path.dirname(filepath)
                if dirname:
                    container.exec_run(f"mkdir -p {dirname}")
                # Write file content
                container.exec_run(f"sh -c \"cat << 'EOF' > {filepath}\n{escaped_content}\nEOF\"")

            # 3. Execute target command
            exec_res = container.exec_run(
                cmd=command,
                workdir="/",
                demux=True
            )
            
            exit_code = exec_res.exit_code
            stdout_bytes, stderr_bytes = exec_res.output or (b"", b"")
            
            stdout = sanitize_output((stdout_bytes or b"").decode("utf-8", errors="ignore"))
            stderr = sanitize_output((stderr_bytes or b"").decode("utf-8", errors="ignore"))
            
            duration = time.time() - start_time
            return exit_code, stdout, stderr, duration

        except Exception as e:
            logger.error(f"Error running in Docker sandbox: {e}")
            return -1, "", f"Sandbox Runtime Exception: {str(e)}", time.time() - start_time
        finally:
            # Clean up container
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

    def _run_local_fallback(self, command: str, files: Dict[str, str], timeout: int, start_time: float) -> Tuple[int, str, str, float]:
        """
        Subprocess fallback run within a temporary local directory structure.
        """
        import tempfile
        import shutil
        from pathlib import Path

        temp_dir = tempfile.mkdtemp(prefix="enterprise_sandbox_")
        temp_path = Path(temp_dir)

        try:
            # 1. Write the files
            for filepath, content in files.items():
                target_file = temp_path / filepath
                target_file.parent.mkdir(parents=True, exist_ok=True)
                with open(target_file, "w", encoding="utf-8") as f:
                    f.write(content)

            # 2. Execute process in safe context
            # We run with shell=False for security
            cmd_parts = command.split()
            if cmd_parts and cmd_parts[0] == "python":
                import sys
                cmd_parts[0] = sys.executable
            
            # Run
            process = subprocess.run(
                cmd_parts,
                cwd=temp_dir,
                capture_output=True,
                timeout=timeout,
                text=True
            )
            
            stdout = sanitize_output(process.stdout)
            stderr = sanitize_output(process.stderr)
            exit_code = process.returncode
            
            duration = time.time() - start_time
            return exit_code, stdout, stderr, duration

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return -1, "", "Execution Timeout: Sandbox run exceeded duration limit.", duration
        except Exception as e:
            logger.error(f"Error running local fallback subprocess: {e}")
            return -1, "", f"Local Subprocess Execution Exception: {str(e)}", time.time() - start_time
        finally:
            # Clean up local directory files
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass

sandbox_service = SandboxService()
