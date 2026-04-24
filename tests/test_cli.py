# tests/test_cli.py

import pytest

from cli import build_cli_config, build_parser, parse_args


def test_parser_accepts_one_shot_prompt():
    args = build_parser().parse_args(["List files"])

    assert args.user_prompt == "List files"
    assert args.interactive is False


def test_parser_accepts_interactive_mode_without_prompt():
    args = parse_args(["--interactive"])

    assert args.interactive is True
    assert args.user_prompt is None


def test_parse_args_rejects_missing_prompt_without_interactive_or_show_config():
    with pytest.raises(SystemExit):
        parse_args([])


def test_parse_args_rejects_interactive_with_prompt():
    with pytest.raises(SystemExit):
        parse_args(["--interactive", "List files"])


def test_parse_args_rejects_invalid_max_iterations():
    with pytest.raises(SystemExit):
        parse_args(["--max-iterations", "0", "List files"])


def test_parse_args_accepts_provider_choice():
    args = parse_args(["--provider", "openai", "List files"])

    assert args.provider == "openai"


def test_parse_args_accepts_workspace():
    args = parse_args(["--workspace", "/tmp", "List files"])

    assert args.workspace == "/tmp"


def test_parse_args_accepts_show_config_without_prompt():
    args = parse_args(["--show-config"])

    assert args.show_config is True
    assert args.user_prompt is None


def test_parse_args_accepts_show_config_with_interactive():
    args = parse_args(["--interactive", "--show-config"])

    assert args.interactive is True
    assert args.show_config is True


def test_build_cli_config_resolves_one_shot_mode(tmp_path):
    args = parse_args(["--workspace", str(tmp_path), "List files"])

    config = build_cli_config(args)

    assert config.mode == "one-shot"
    assert config.workspace == str(tmp_path)
    assert config.user_prompt == "List files"


def test_build_cli_config_resolves_interactive_mode(tmp_path):
    args = parse_args(["--workspace", str(tmp_path), "--interactive"])

    config = build_cli_config(args)

    assert config.mode == "interactive"
    assert config.workspace == str(tmp_path)
    assert config.user_prompt is None


def test_build_cli_config_resolves_default_model(tmp_path):
    args = parse_args(["--workspace", str(tmp_path), "--provider", "gemini", "Hello"])

    config = build_cli_config(args)

    assert config.model