"""Офлайн-проверки предохранителей real-provider workflow evaluator."""

from types import SimpleNamespace

from live_workflow_eval import MAX_PROVIDER_CALLS, RecordingCompletions, require_boundary


class FakeCompletions:
    def __init__(self):
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(
            id="fake",
            model="deepseek/deepseek-v4-flash-0731",
            provider="OpenInference",
            choices=[SimpleNamespace(
                message=SimpleNamespace(content="текст"),
                finish_reason="stop",
            )],
            usage=SimpleNamespace(
                prompt_tokens=10,
                completion_tokens=2,
                cost=0.000001,
            ),
        )


def test_provider_pin_and_reasoning_preserved():
    target = FakeCompletions()
    traces = []
    wrapped = RecordingCompletions(target, traces, "secret")
    wrapped.create(
        model="model",
        messages=[],
        max_tokens=1600,
        extra_body={"reasoning": {"effort": "none"}},
    )
    extra = target.requests[0]["extra_body"]
    assert extra["reasoning"] == {"effort": "none"}
    assert extra["usage"] == {"include": True}
    assert extra["provider"] == {
        "only": ["open-inference"],
        "allow_fallbacks": False,
        "require_parameters": True,
    }
    print("ok  provider pinned, fallback disabled, reasoning preserved")


def test_call_limit_and_fail_fast_boundary():
    target = FakeCompletions()
    traces = []
    wrapped = RecordingCompletions(target, traces, "secret")
    for _ in range(MAX_PROVIDER_CALLS):
        wrapped.create(model="model", messages=[])
    try:
        wrapped.create(model="model", messages=[])
    except RuntimeError as error:
        assert "трёх provider calls" in str(error)
    else:
        raise AssertionError("четвёртый provider call должен быть запрещён")

    try:
        require_boundary(False, "planning", "model_error")
    except RuntimeError as error:
        assert str(error) == "planning boundary failed: model_error"
    else:
        raise AssertionError("нарушенная boundary должна остановить evaluator")
    print("ok  call limit and fail-fast boundary enforced")


def main():
    test_provider_pin_and_reasoning_preserved()
    test_call_limit_and_fail_fast_boundary()


if __name__ == "__main__":
    main()
