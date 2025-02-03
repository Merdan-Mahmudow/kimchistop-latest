from fastapi import HTTPException, status

class SBISException(HTTPException):
    """Base exception for SBIS errors."""
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

class SBISAuthError(SBISException):
    """Authentication error."""
    def __init__(self):
        super().__init__("SBIS authentication failed:")

class SBISRequestError(SBISException):
    """Request error."""
    def __init__(self, detail: str):
        super().__init__(f"SBIS request failed: {detail}")
