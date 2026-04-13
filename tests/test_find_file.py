from functions.find_file import find_file


def test_find_file_skips_ignored_dirs(tmp_path):
    visible = tmp_path / "src"
    visible.mkdir()
    (visible / "target.py").write_text("print('ok')", encoding="utf-8")

    hidden_git = tmp_path / ".git"
    hidden_git.mkdir()
    (hidden_git / "target.py").write_text("print('bad')", encoding="utf-8")

    hidden_cache = tmp_path / "__pycache__"
    hidden_cache.mkdir()
    (hidden_cache / "target.py").write_text("print('bad')", encoding="utf-8")

    result = find_file(str(tmp_path), "target.py")

    assert result == "src/target.py"

def test_find_file_is_case_insensitive(tmp_path):
    file_path = tmp_path / "Test_Hello_World.py"
    file_path.write_text("print('hello')", encoding="utf-8")

    result = find_file(str(tmp_path), "test_hello")

    assert result == "Test_Hello_World.py"