import pytest
import os
from functions.run_python_file import run_python_file

@pytest.fixture
def create_script(tmp_path):
    def _create_script(filename, content):
        path = tmp_path / filename
        path.write_text(content)
        return path
    return _create_script

@pytest.fixture
def create_nested_script(tmp_path):
    def _create_nested_script(dirname, filename, content):
        dir_path = tmp_path / dirname
        dir_path.mkdir()
        file_path = dir_path / filename
        file_path.write_text(content)
        return file_path
    return _create_nested_script

def test_successful_execution_and_stdout_capture(tmp_path, create_script):
    script_content = "print('Hello from script')"
    script_path = create_script("hello.py", script_content)
    result = run_python_file(str(tmp_path), script_path.name)
    assert "STDOUT:\nHello from script" in result

def test_stderr_capture(tmp_path, create_script):
    script_content = "import sys; sys.stderr.write('Error message')"
    script_path = create_script("error_script.py", script_content)
    result = run_python_file(str(tmp_path), script_path.name)
    assert "STDERR:\nError message" in result

def test_non_zero_exit(tmp_path, create_script):
    script_content = "import sys; sys.exit(1)"
    script_path = create_script("exit_script.py", script_content)
    result = run_python_file(str(tmp_path), script_path.name)
    assert "Process exited with code 1" in result

def test_missing_file(tmp_path):
    result = run_python_file(str(tmp_path), "nonexistent_script.py")
    assert "Error: \"nonexistent_script.py\" does not exist or is not a regular file" in result

def test_nested_file_execution(tmp_path, create_nested_script):
    script_content = "print('Hello from nested script')"
    nested_script_path = create_nested_script("subdir", "nested_hello.py", script_content)
    
    # Run from the parent directory, providing relative path to script
    result = run_python_file(str(tmp_path), os.path.join("subdir", "nested_hello.py"))
    assert "STDOUT:\nHello from nested script" in result

    # Run from the nested directory
    result = run_python_file(str(nested_script_path.parent), nested_script_path.name)
    assert "STDOUT:\nHello from nested script" in result


def test_working_directory_path_boundary_violation(tmp_path, create_script):
    # Create a script outside the intended working directory for the test
    # We will pass tmp_path as the working directory, and try to access a file in its parent
    malicious_script_content = "print('This should not run')"
    malicious_script_path = tmp_path.parent / "malicious.py"
    malicious_script_path.write_text("print('This should not run')")

    # Attempt to run a script by escaping the working directory
    # The run_python_file function should prevent this
    result = run_python_file(str(tmp_path), "../malicious.py")
    assert "Error: Cannot execute \"../malicious.py\" as it is outside the permitted working directory" in result
