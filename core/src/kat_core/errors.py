"""Provider-independent, sanitized failures suitable for UI and audit records."""

from enum import StrEnum


class ProviderErrorCode(StrEnum):
    NOT_CONFIGURED = "provider_not_configured"
    AUTHENTICATION = "provider_authentication"
    QUOTA = "provider_quota"
    MODEL_UNAVAILABLE = "provider_model_unavailable"
    LOCAL_REQUIRED = "provider_local_model_required"
    RATE_LIMITED = "provider_rate_limited"
    TIMEOUT = "provider_timeout"
    NETWORK = "provider_network"
    MALFORMED_RESPONSE = "provider_malformed_response"
    FAILED = "provider_failed"


_MESSAGES: dict[ProviderErrorCode, tuple[int, str]] = {
    ProviderErrorCode.LOCAL_REQUIRED: (
        503,
        "This Ollama model is cloud-backed. Select installed local weights and disable "
        "Ollama cloud features to keep local conversations on this computer.",
    ),
    ProviderErrorCode.NOT_CONFIGURED: (
        503,
        "Open Settings to configure a provider. For OpenAI, save an API key in Windows "
        "Credential Manager, or configure KAT_OPENAI_API_KEY / OPENAI_API_KEY for development.",
    ),
    ProviderErrorCode.AUTHENTICATION: (
        503,
        "The provider rejected the API key. Replace it in Settings and retry.",
    ),
    ProviderErrorCode.QUOTA: (
        503,
        "Your provider account has insufficient credit or exhausted quota. "
        "Check billing and usage limits, or select another provider.",
    ),
    ProviderErrorCode.MODEL_UNAVAILABLE: (
        503,
        "The selected model is unavailable or access was denied. "
        "Choose a model available to your provider account.",
    ),
    ProviderErrorCode.RATE_LIMITED: (
        429,
        "The provider is temporarily rate limiting requests. Wait briefly and retry.",
    ),
    ProviderErrorCode.TIMEOUT: (
        504,
        "The model request timed out. Check provider status, then retry.",
    ),
    ProviderErrorCode.NETWORK: (
        503,
        "The model provider could not be reached. "
        "Check connectivity and provider status, then retry.",
    ),
    ProviderErrorCode.MALFORMED_RESPONSE: (
        502,
        "The provider returned an unusable response. Retry or select another model.",
    ),
    ProviderErrorCode.FAILED: (
        503,
        "The model request failed. Check provider status or select another model, then retry.",
    ),
}


class ProviderFailure(RuntimeError):
    """Accept only a fixed category, never raw provider exception text or payloads."""

    def __init__(self, code: ProviderErrorCode = ProviderErrorCode.FAILED) -> None:
        self.code = code
        self.status_code, message = _MESSAGES[code]
        super().__init__(message)
