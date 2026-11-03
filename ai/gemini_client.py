"""Gemini client with REST transport, direct-HTTPS fallback, and graceful degradation.

Why this module looks the way it does
-------------------------------------
The legacy ``google-generativeai`` SDK talks gRPC by default. On Windows
networks that channel sometimes stalls and surfaces ``DeadlineExceeded: 504``
even when the API itself is healthy. This client therefore escalates through
three transports, cheapest and most reliable first:

1. **Modern SDK** — ``google-genai`` (``from google import genai``), which is
   REST/HTTPS by default.
2. **Legacy SDK over REST** — ``google.generativeai`` configured with
   ``transport="rest"``, bypassing the hanging gRPC channel.
3. **Direct HTTPS** — a plain ``urllib.request`` POST to the public
   ``v1beta`` ``generateContent`` endpoint with a strict timeout, used when the
   SDKs fail or time out.

Every layer is best-effort. The client never raises during construction and
returns ``None`` plus a human-readable ``last_error`` when the key is invalid,
the quota is exhausted, or the network is offline. The dashboard's 180-second
circuit breaker (``dashboard/ai_dashboard.py``) sits on top of this.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

from .ai_logger import setup_logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

logger = setup_logger("GeminiClient")

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# Retired model ids are kept in the rotation on purpose: the account-specific
# availability of a model id changes over time, so the client probes instead of
# hardcoding a single winner. ``gemini-3.6-flash`` and friends are current
# workhorses that keep generation alive when a newer id is demand-limited.
FALLBACK_MODELS: Tuple[str, ...] = tuple(
    model
    for model in (
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-flash-lite-latest",
        "gemini-flash-latest",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    )
    if model != DEFAULT_MODEL
)

REQUEST_TIMEOUT_SECONDS = int(os.getenv("GEMINI_TIMEOUT", "30"))
# The direct HTTPS fallback must fail fast: a stalled socket should not make the
# UI wait for the full SDK budget.
HTTPS_TIMEOUT_SECONDS = int(os.getenv("GEMINI_HTTPS_TIMEOUT", "12"))
MAX_CACHE_ENTRIES = 128
API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"

_MODEL_ERROR_MARKERS = (
    "404",
    "not found",
    "not supported",
    "does not exist",
    "unsupported model",
    "no longer available",
    "is not found",
)
# Answers produced by the Gemini service itself. Repeating the exact same call
# over the direct HTTPS path cannot change them, so the client moves straight to
# the next model instead of paying for a second identical round trip.
_SERVICE_ERROR_MARKERS = (
    "429",
    "503",
    "high demand",
    "quota",
    "overloaded",
    "resource_exhausted",
    "unavailable",
)
_TIMEOUT_MARKERS = ("deadline", "timed out", "timeout", "504")
_AUTH_MARKERS = (
    "401",
    "403",
    "api key not valid",
    "api_key_invalid",
    "invalid api key",
    "permission denied",
    "unauthenticated",
    "api key expired",
)


# --------------------------------------------------------------------------- #
# SDK discovery
# --------------------------------------------------------------------------- #


def _load_sdks() -> Tuple[Optional[Any], Optional[Any]]:
    """Return ``(modern_genai, legacy_genai)`` without importing the legacy SDK
    when the modern one is present (importing it emits a deprecation warning)."""

    modern = None
    try:  # google-genai, the actively maintained package
        from google import genai as modern  # type: ignore
    except Exception:  # pragma: no cover - depends on the environment
        modern = None

    legacy = None
    if modern is None:
        try:  # google-generativeai, deprecated but still widely installed
            import google.generativeai as legacy  # type: ignore
        except Exception:  # pragma: no cover - depends on the environment
            legacy = None

    return modern, legacy


_MODERN_GENAI, _LEGACY_GENAI = _load_sdks()


def _is_model_availability_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _MODEL_ERROR_MARKERS)


def _is_timeout_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _TIMEOUT_MARKERS)


def _is_service_error(exc: Exception) -> bool:
    """True for model/service rejections that HTTPS would reproduce verbatim."""

    message = str(exc).lower()
    if _is_timeout_error(exc):
        return False
    return any(marker in message for marker in _SERVICE_ERROR_MARKERS)


def _is_auth_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _AUTH_MARKERS)


def _extract_rest_text(payload: Dict[str, Any]) -> str:
    """Pull the first text part out of a ``generateContent`` REST payload."""

    candidates = payload.get("candidates") or []
    for candidate in candidates:
        parts = (candidate.get("content") or {}).get("parts") or []
        text = "".join(str(part.get("text") or "") for part in parts)
        if text.strip():
            return text

    feedback = payload.get("promptFeedback") or {}
    reason = feedback.get("blockReason")
    if reason:
        raise RuntimeError(f"Gemini blocked the prompt ({reason}).")
    return ""


class GeminiClient:
    """Best-effort Gemini wrapper with a three-layer transport ladder."""

    def __init__(self, model_name: Optional[str] = None):
        self.api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
        self.is_configured = bool(self.api_key)
        self.model_name = model_name or DEFAULT_MODEL
        self.preferred_model: Optional[str] = None
        self.last_error: Optional[str] = None
        self.cache: Dict[str, str] = {}

        # ``model`` is kept for backwards compatibility with older call sites.
        self.model: Optional[Any] = None

        self._sdk_kind: Optional[str] = None
        self._modern_client: Optional[Any] = None
        self._legacy_ready = False
        self._legacy_models: Dict[str, Any] = {}
        self._https_only = False
        self._auth_failed = False
        self.last_transport: Optional[str] = None

        if not self.is_configured:
            logger.warning(
                "GEMINI_API_KEY is not configured. AI features are disabled "
                "until the key is added to .env."
            )
            return

        self._initialise_sdk()

    # ------------------------------------------------------------------ #
    # Setup
    # ------------------------------------------------------------------ #

    def _initialise_sdk(self) -> None:
        """Prepare whichever SDK is installed, preferring REST transport."""

        if _MODERN_GENAI is not None:
            try:
                http_options = None
                types = getattr(_MODERN_GENAI, "types", None)
                if types is not None and hasattr(types, "HttpOptions"):
                    kwargs: Dict[str, Any] = {
                        "timeout": REQUEST_TIMEOUT_SECONDS * 1000
                    }
                    try:
                        kwargs["retryOptions"] = types.HttpRetryOptions(attempts=1)
                    except Exception:  # pragma: no cover - older google-genai
                        pass
                    try:
                        http_options = types.HttpOptions(**kwargs)
                    except Exception:  # pragma: no cover - option mismatch
                        http_options = None

                self._modern_client = _MODERN_GENAI.Client(
                    api_key=self.api_key,
                    http_options=http_options,
                )
                self._sdk_kind = "modern"
                self.model = self._modern_client
                logger.info(
                    "Gemini client initialised with google-genai (REST) "
                    "for model %s.",
                    self.model_name,
                )
                return
            except Exception as exc:  # pragma: no cover - defensive
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "google-genai initialisation failed (%s); trying the "
                    "legacy SDK over REST.",
                    self.last_error,
                )

        if _LEGACY_GENAI is not None:
            try:
                _LEGACY_GENAI.configure(api_key=self.api_key, transport="rest")
                self._legacy_ready = True
                self._sdk_kind = "legacy-rest"
                self.model = True  # truthy sentinel for legacy call sites
                logger.info(
                    "Gemini client initialised with google-generativeai "
                    "(transport=rest) for model %s.",
                    self.model_name,
                )
                return
            except Exception as exc:  # pragma: no cover - defensive
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "Legacy Gemini SDK initialisation failed (%s); falling "
                    "back to direct HTTPS.",
                    self.last_error,
                )

        self._https_only = True
        self.model = True
        logger.warning(
            "No Gemini SDK is usable; using the direct HTTPS transport only."
        )

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #

    @property
    def transport(self) -> str:
        """Human-readable label for the transport that is currently active."""

        if self._https_only:
            return "https"
        if self._sdk_kind == "modern":
            return "google-genai (REST)"
        if self._sdk_kind == "legacy-rest":
            return "google-generativeai (REST)"
        return "https"

    @property
    def is_ready(self) -> bool:
        """``True`` when the client may still attempt a network call."""

        return bool(self.is_configured and not self._auth_failed)

    def status(self) -> Dict[str, Any]:
        """Structured status for the UI or logging."""

        return {
            "configured": self.is_configured,
            "ready": self.is_ready,
            "model": self.model_name,
            "preferred_model": self.preferred_model,
            "fallback_models": list(FALLBACK_MODELS),
            "transport": self.transport,
            "https_fallback": not self._https_only,
            "last_error": self.last_error,
        }

    def unavailable_message(self, feature: str) -> str:
        """Human-readable message for a failed/disabled AI request."""

        if not self.is_configured:
            return (
                f"AI {feature} unavailable: GEMINI_API_KEY is not configured. "
                "Add it to the project .env file and restart the app."
            )
        return (
            f"AI {feature} unavailable: "
            f"{self.last_error or 'Gemini returned no content.'}"
        )

    # ------------------------------------------------------------------ #
    # Transports
    # ------------------------------------------------------------------ #

    def _call_modern(self, model_name: str, prompt: str) -> str:
        response = self._modern_client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        text = getattr(response, "text", None)
        if not text or not str(text).strip():
            raise RuntimeError("Gemini returned an empty response.")
        return str(text)

    def _call_legacy(self, model_name: str, prompt: str) -> str:
        model = self._legacy_models.get(model_name)
        if model is None:
            model = _LEGACY_GENAI.GenerativeModel(model_name)
            self._legacy_models[model_name] = model

        response = model.generate_content(
            prompt,
            request_options={"timeout": REQUEST_TIMEOUT_SECONDS},
        )
        text = getattr(response, "text", None)
        if not text or not str(text).strip():
            raise RuntimeError("Gemini returned an empty response.")
        return str(text)

    def _call_https(self, model_name: str, prompt: str) -> str:
        """Direct REST call that bypasses both SDK transports entirely."""

        key = urllib.parse.quote(self.api_key, safe="")
        url = f"{API_ROOT}/{model_name}:generateContent?key={key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}]
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=HTTPS_TIMEOUT_SECONDS
            ) as response:
                body = json.loads(response.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            # Surface Google's own message: it is what tells an invalid key
            # (400 + "API key not valid") apart from a busy model (503).
            detail = ""
            try:
                payload_error = json.loads(exc.read().decode("utf-8", "replace"))
                detail = (payload_error.get("error") or {}).get("message", "")
            except Exception:  # pragma: no cover - non-JSON error page
                detail = ""
            raise RuntimeError(
                f"HTTP {exc.code}: {detail or exc.reason}"
            ) from exc

        text = _extract_rest_text(body)
        if not text.strip():
            raise RuntimeError("Gemini REST returned an empty response.")
        return text

    def _call(self, transport: str, model_name: str, prompt: str) -> str:
        if transport == "modern":
            return self._call_modern(model_name, prompt)
        if transport == "legacy-rest":
            return self._call_legacy(model_name, prompt)
        return self._call_https(model_name, prompt)

    # ------------------------------------------------------------------ #
    # Response generation
    # ------------------------------------------------------------------ #

    def _remember(self, prompt: str, text: str) -> None:
        if len(self.cache) >= MAX_CACHE_ENTRIES:
            oldest = next(iter(self.cache))
            self.cache.pop(oldest, None)
        self.cache[prompt] = text

    def _candidates(self) -> List[str]:
        """Ordered, de-duplicated model rotation for this request."""

        ordered: List[str] = []
        for model in (self.preferred_model, self.model_name) + FALLBACK_MODELS:
            if model and model not in ordered:
                ordered.append(model)
        return ordered

    def _transports(self) -> Tuple[str, ...]:
        if self._https_only or self._sdk_kind is None:
            return ("https",)
        return (self._sdk_kind, "https")

    def _note_failure(
        self, model_name: str, transport: str, exc: Exception
    ) -> None:
        self.last_error = f"{type(exc).__name__}: {exc}"
        logger.error(
            "Gemini %s transport failed for %s: %s",
            transport,
            model_name,
            self.last_error,
        )

    def generate_response(self, prompt: str, use_cache: bool = True) -> Optional[str]:
        if not prompt or not str(prompt).strip():
            self.last_error = "Prompt is empty."
            raise ValueError("Prompt must not be empty.")

        if not self.is_ready:
            self.last_error = self.last_error or "GEMINI_API_KEY is not configured."
            logger.warning("Gemini request skipped: %s", self.last_error)
            return None

        if use_cache and prompt in self.cache:
            logger.info("Returning cached response for prompt.")
            return self.cache[prompt]

        for model_name in self._candidates():
            for transport in self._transports():
                logger.info(
                    "Sending request to Gemini model %s via %s...",
                    model_name,
                    transport,
                )
                try:
                    text = self._call(transport, model_name, prompt)
                except Exception as exc:
                    self._note_failure(model_name, transport, exc)

                    if _is_auth_error(exc):
                        # A bad key will not be fixed by another model.
                        self._auth_failed = True
                        return None

                    if transport in ("modern", "legacy-rest"):
                        if _is_model_availability_error(exc) or _is_service_error(exc):
                            # The service itself answered: HTTPS would return
                            # the same status, so probe the next model instead.
                            break
                        if _is_timeout_error(exc):
                            # gRPC/REST stall: drop the SDK for this session and
                            # let the direct HTTPS path take over.
                            self._https_only = True
                    continue

                if text:
                    if use_cache:
                        self._remember(prompt, text)
                    self.model_name = model_name
                    self.preferred_model = model_name
                    self.last_transport = transport
                    self.last_error = None
                    logger.info(
                        "Gemini responded via %s using %s.", transport, model_name
                    )
                    return text

        return None
