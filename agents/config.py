"""Shared agent config.

`gemini-flash-latest` is used deliberately: the `gemini-2.0-flash` aliases returned 429
RESOURCE_EXHAUSTED on the free-tier Developer API key, while `gemini-flash-latest` serves.
Swap here in one place if the account moves to a billed project with different quota.
"""

MODEL = "gemini-flash-latest"

# The second reader runs a DIFFERENT model on purpose, so corroboration is genuinely
# cross-model: two independent extractors agreeing is real signal, not one model agreeing
# with itself. If both point at the same model the corroboration degrades to a self-check.
REDERIVE_MODEL = "gemini-2.5-flash-lite"
