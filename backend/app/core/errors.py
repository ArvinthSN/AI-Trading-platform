class ProviderUnavailable(Exception):
    def __init__(self, provider: str, message: str = "Provider is unavailable.") -> None:
        super().__init__(message)
        self.provider = provider


class ProviderRateLimited(ProviderUnavailable):
    def __init__(self, provider: str, retry_after: str | None = None) -> None:
        super().__init__(provider, "Provider rate limit reached.")
        self.retry_after = retry_after
