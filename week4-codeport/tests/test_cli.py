import week4_codeport.__main__ as cli
from week4_codeport.benchmarks import BENCHMARKS


def test_no_compiler_gives_install_instructions(monkeypatch, capsys):
    monkeypatch.setattr(cli, "find_compiler", lambda: None)
    assert cli.main(["--cpp", "x.cpp"]) == 2
    assert "No C++ compiler found" in capsys.readouterr().err


def test_checking_a_file_needs_no_model_or_key(monkeypatch, tmp_path, capsys, compiler):
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(BENCHMARKS["pi"].timing_args, "quick", ("1000", "4", "1"))
    good = tmp_path / "pi.cpp"
    good.write_text((cli.Path(__file__).parent / "ports" / "pi_good.cpp").read_text())

    code = cli.main(
        [
            "--benchmark",
            "pi",
            "--cpp",
            str(good),
            "--runs",
            "1",
            "--out",
            str(tmp_path / "board.md"),
        ]
    )

    out = capsys.readouterr()
    assert code == 0
    assert "| 1 | `pi.cpp` | correct |" in out.out
    assert "no full sandbox" in out.err
    assert (tmp_path / "board.md").read_text().startswith("## pi (quick size)")


def test_asking_models_without_a_key_explains_what_to_set(monkeypatch, tmp_path, capsys, compiler):
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "CODEPORT_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(BENCHMARKS["pi"].timing_args, "quick", ("1000", "4", "1"))
    assert cli.main(["--benchmark", "pi"]) == 2
    assert "GEMINI_API_KEY or GOOGLE_API_KEY" in capsys.readouterr().err
