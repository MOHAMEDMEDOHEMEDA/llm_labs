from week1_brochure.__main__ import main

KEY_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "BROCHURE_PROVIDER")


def clear_keys(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # no .env here
    for var in KEY_VARS:
        monkeypatch.delenv(var, raising=False)


def test_missing_gemini_key_names_the_variables_to_set(monkeypatch, tmp_path, capsys):
    clear_keys(monkeypatch, tmp_path)

    assert main(["Acme", "https://acme.test"]) == 2
    assert "GEMINI_API_KEY or GOOGLE_API_KEY" in capsys.readouterr().err


def test_openai_provider_asks_for_the_openai_key(monkeypatch, tmp_path, capsys):
    clear_keys(monkeypatch, tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "set-but-irrelevant")

    assert main(["Acme", "https://acme.test", "--provider", "openai"]) == 2
    assert "OPENAI_API_KEY" in capsys.readouterr().err


def test_rejects_urls_without_a_scheme(monkeypatch, tmp_path, capsys):
    clear_keys(monkeypatch, tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    assert main(["Acme", "acme.test"]) == 2
    assert "must start with http" in capsys.readouterr().err
