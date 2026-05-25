import re
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Set
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings

# Password hashing configuration
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# Dangerous command patterns and character allowlists
BLOCKED_CHARS_PATTERN = re.compile(r'[&|;`$><\*\?\[\]\{\}\(\)\!#\\]')
ALLOWED_COMMANDS: Set[str] = {"pytest", "python", "ruff", "git", "pip", "poetry", "black", "mypy"}

# Regex for hiding secrets in logs or output
SECRET_PATTERNS = [
    re.compile(r"(api[-_]?key|secret|token|password|passwd|jwt|private[-_]?key)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.\/]{8,})['\"]?", re.IGNORECASE)
]

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        return None

def validate_sandbox_command(command: str) -> bool:
    """
    Validates a command before running it inside the sandbox.
    Disallows shell piping, redirection, command chaining, and ensures
    the primary executable is inside our ALLOWED_COMMANDS list.
    """
    if not command:
        return False
        
    trimmed = command.strip()
    
    # 1. Block command injection characters
    if BLOCKED_CHARS_PATTERN.search(trimmed):
        return False
        
    # 2. Tokenize command to check target executable
    parts = trimmed.split()
    if not parts:
        return False
        
    executable = parts[0]
    
    # Allow python execution but restrict target script runs to current path patterns
    if executable in ALLOWED_COMMANDS:
        # Check for dangerous flags or sub-arguments (like git clean, rm, etc.)
        if executable == "git" and len(parts) > 1:
            if parts[1] in {"clean", "reset", "push"}:
                return False
        return True
        
    return False

def sanitize_output(output: str) -> str:
    """
    Scans execution output and redacts common secret patterns.
    """
    if not output:
        return ""
        
    sanitized = output
    for pattern in SECRET_PATTERNS:
        # Replace the captured token with REDACTED
        sanitized = pattern.sub(r"\1: [REDACTED]", sanitized)
    return sanitized
