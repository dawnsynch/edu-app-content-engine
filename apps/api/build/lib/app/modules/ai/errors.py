class AIServiceError(Exception):
    code = "ai_service_error"


class TransientAIError(AIServiceError):
    code = "transient_ai_error"


class PermanentAIError(AIServiceError):
    code = "permanent_ai_error"
