import json

from agent_runtime import build_usage_summary_event, run_agent
from agent_types import ModelTurn, ToolCall, UsageStats, UsageTotals
from permissions import PermissionContext, PermissionMode, PermissionRuleSet
from providers.base import ProviderError
from run_logging import RunLogger
from runtime_events import ListEventSink


class FakeProvider:
    def __init__(self):
        self.user_messages = []
        self.tool_results = []
        self.generate_count = 0
        self.seen_tools = None

    def add_user_message(self, text: str) -> None:
        self.user_messages.append(text)

    def generate(self, system_prompt: str, tools):
        self.generate_count += 1
        self.seen_tools = tools

        if self.generate_count == 1:
            return ModelTurn(
                text_parts=["I will inspect the requested file."],
                tool_calls=[
                    ToolCall(
                        name="get_file_content",
                        args={"file_path": "sample.txt"},
                    )
                ],
            )

        return ModelTurn(
            text_parts=["The file contains hello."],
            tool_calls=[],
        )

    def add_tool_results(self, results) -> None:
        self.tool_results.extend(results)


def make_context(workspace: str) -> PermissionContext:
    return PermissionContext(
        mode=PermissionMode.DEFAULT,
        workspace=workspace,
        rules=PermissionRuleSet(),
    )


def test_run_agent_executes_tool_and_returns_final_text(tmp_path):
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")

    provider = FakeProvider()

    final_text = run_agent(
        provider=provider,
        user_prompt="Read sample.txt",
        workspace=str(tmp_path),
        permission_context=make_context(str(tmp_path)),
        max_iterations=5,
    )

    assert final_text == "The file contains hello."
    assert provider.user_messages == ["Read sample.txt"]
    assert provider.generate_count == 2
    assert provider.seen_tools
    assert len(provider.tool_results) == 1
    assert provider.tool_results[0].name == "get_file_content"
    assert provider.tool_results[0].payload == {"result": "hello"}


def test_run_agent_returns_none_after_max_iterations(tmp_path):
    class LoopingProvider:
        def add_user_message(self, text: str) -> None:
            pass

        def generate(self, system_prompt: str, tools):
            return ModelTurn(
                text_parts=["Still working."],
                tool_calls=[
                    ToolCall(
                        name="get_file_content",
                        args={"file_path": "sample.txt"},
                    )
                ],
            )

        def add_tool_results(self, results) -> None:
            pass

    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")

    final_text = run_agent(
        provider=LoopingProvider(),
        user_prompt="Loop forever",
        workspace=str(tmp_path),
        permission_context=make_context(str(tmp_path)),
        max_iterations=2,
    )

    assert final_text is None


def test_build_usage_summary_event_when_usage_unavailable():
    event = build_usage_summary_event(UsageTotals())

    assert event.type == "usage_summary"
    assert event.prompt_tokens is None
    assert event.response_tokens is None
    assert event.total_tokens is None


def test_build_usage_summary_event_with_totals():
    usage_totals = UsageTotals()
    usage_totals.add(UsageStats(prompt_tokens=10, response_tokens=5))
    usage_totals.add(UsageStats(prompt_tokens=3, response_tokens=2))

    event = build_usage_summary_event(usage_totals)

    assert event.type == "usage_summary"
    assert event.prompt_tokens == 13
    assert event.response_tokens == 7
    assert event.total_tokens == 20


def test_run_agent_returns_none_on_provider_error(tmp_path):
    class FailingProvider:
        def add_user_message(self, text: str) -> None:
            pass

        def generate(self, system_prompt: str, tools):
            raise ProviderError("test provider exploded")

        def add_tool_results(self, results) -> None:
            pass

    final_text = run_agent(
        provider=FailingProvider(),
        user_prompt="hello",
        workspace=str(tmp_path),
        permission_context=make_context(str(tmp_path)),
        max_iterations=5,
    )

    assert final_text is None


def test_run_agent_writes_run_log(tmp_path):
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")

    provider = FakeProvider()
    logger = RunLogger(
        log_dir=tmp_path / "logs",
        metadata={
            "provider": "fake",
            "model": "fake-model",
        },
    )

    final_text = run_agent(
        provider=provider,
        user_prompt="Read sample.txt",
        workspace=str(tmp_path),
        permission_context=make_context(str(tmp_path)),
        max_iterations=5,
        run_logger=logger,
    )

    assert final_text == "The file contains hello."
    assert logger.saved_path is not None
    assert logger.saved_path.exists()

    payload = json.loads(logger.saved_path.read_text(encoding="utf-8"))
    event_types = [event["type"] for event in payload["events"]]

    assert "run_started" in event_types
    assert "model_turn" in event_types
    assert "tool_result" in event_types
    assert "final_response" in event_types
    assert "usage_summary" in event_types


def test_run_agent_emits_runtime_events(tmp_path):
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")

    provider = FakeProvider()
    event_sink = ListEventSink()

    final_text = run_agent(
        provider=provider,
        user_prompt="Read sample.txt",
        workspace=str(tmp_path),
        permission_context=make_context(str(tmp_path)),
        max_iterations=5,
        event_sink=event_sink,
    )

    assert final_text == "The file contains hello."

    event_types = [event.type for event in event_sink.events]

    assert event_types == [
        "run_started",
        "model_turn",
        "tool_result",
        "model_turn",
        "final_response",
        "usage_summary",
    ]
