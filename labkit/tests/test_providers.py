import pytest

from labkit.providers import DEFAULT_MAX_RETRIES, PROVIDERS, client_for, get_provider


def test_gemini_accepts_the_course_key_name_as_a_fallback():
    gemini = PROVIDERS["gemini"]
    assert gemini.api_key({"GOOGLE_API_KEY": "g"}) == "g"
    assert gemini.api_key({"GEMINI_API_KEY": "a", "GOOGLE_API_KEY": "g"}) == "a"
    assert gemini.api_key({}) is None


def test_local_providers_work_without_a_key():
    assert PROVIDERS["ollama"].api_key({}) == "local"
    assert PROVIDERS["huggingface"].api_key({}) is None


def test_unknown_provider_lists_the_choices():
    with pytest.raises(ValueError, match="gemini, openai, huggingface, ollama"):
        get_provider("gemni")


def test_clients_point_at_the_provider_and_retry_long_enough():
    client = client_for(PROVIDERS["huggingface"], "hf_x")
    assert str(client.base_url) == "https://router.huggingface.co/v1/"
    assert client.max_retries == DEFAULT_MAX_RETRIES
    assert client_for(PROVIDERS["gemini"], "k", max_retries=0).max_retries == 0
