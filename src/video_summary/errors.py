class VideoSummaryError(Exception):
    """Base class for user-readable pipeline errors."""


class UnsupportedInputError(VideoSummaryError):
    """Raised when the input is outside the current prototype scope."""


class SubtitleFetchError(VideoSummaryError):
    """Raised when subtitles cannot be fetched."""


class AudioExtractionError(VideoSummaryError):
    """Raised when audio cannot be extracted or downloaded."""


class ASRError(VideoSummaryError):
    """Raised when local speech recognition fails."""


class LLMError(VideoSummaryError):
    """Raised when the LLM request fails."""
