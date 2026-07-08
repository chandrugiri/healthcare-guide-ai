import pytest

from app.services.generation_service import (
    GenerationAuthenticationError,
    GenerationRequestError,
    GenerationTransientError,
    GeminiGenerationService,
    SYSTEM_INSTRUCTION,
)


class FakeCandidate:
    def __init__(self, finish_reason: str = "STOP") -> None:
        self.finish_reason = finish_reason


class FakeUsage:
    prompt_token_count = 10
    candidates_token_count = 20
    total_token_count = 30


class FakeResponse:
    def __init__(
        self,
        text: str,
        candidates: list[FakeCandidate] | None = None,
    ) -> None:
        self.text = text
        self.candidates = candidates if candidates is not None else [FakeCandidate()]
        self.usage_metadata = FakeUsage()


class FakeError(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(f"fake error {code}")
        self.code = code


class FakeModels:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeClient:
    def __init__(self, responses: list[object]) -> None:
        self.models = FakeModels(responses)


def _service(
    client: FakeClient,
    sleep_calls: list[float] | None = None,
    model: str = "gemini-3.5-flash",
) -> GeminiGenerationService:
    sleeps = sleep_calls if sleep_calls is not None else []
    return GeminiGenerationService(
        api_key="test-key",
        model=model,
        max_output_tokens=1200,
        thinking_budget=0,
        max_retries=3,
        client=client,  # type: ignore[arg-type]
        sleep_seconds=0,
        sleep_func=sleeps.append,
    )


def test_generate_content_uses_system_instruction_and_no_sampling_config() -> None:
    client = FakeClient([FakeResponse("Answer [1]")])
    service = _service(client)

    assert service.generate_answer("prompt") == "Answer [1]"
    call = client.models.calls[0]
    config = call["config"]
    assert call["model"] == "gemini-3.5-flash"
    assert call["contents"] == "prompt"
    assert config.system_instruction == SYSTEM_INSTRUCTION
    assert config.max_output_tokens == 1200
    assert config.temperature is None
    assert config.top_p is None
    assert config.top_k is None


def test_retryable_generation_failure() -> None:
    client = FakeClient([FakeError(503), FakeResponse("Recovered [1]")])
    sleep_calls: list[float] = []
    service = _service(client, sleep_calls)

    assert service.generate_answer("prompt") == "Recovered [1]"
    assert len(client.models.calls) == 2
    assert sleep_calls == [0]


def test_non_retryable_authentication_failure() -> None:
    client = FakeClient([FakeError(401)])
    service = _service(client)

    with pytest.raises(GenerationAuthenticationError):
        service.generate_answer("prompt")
    assert len(client.models.calls) == 1


def test_repeated_retryable_failure_raises_transient_error() -> None:
    client = FakeClient([FakeError(503), FakeError(503), FakeError(503)])
    service = _service(client)

    with pytest.raises(GenerationTransientError):
        service.generate_answer("prompt")


def test_gemini_25_receives_thinking_budget_zero() -> None:
    client = FakeClient([FakeResponse("Answer [1]")])
    service = _service(client, model="gemini-2.5-flash")

    service.generate_answer("prompt")

    config = client.models.calls[0]["config"]
    assert config.thinking_config is not None
    assert config.thinking_config.thinking_budget == 0


def test_gemini_3_does_not_receive_thinking_budget() -> None:
    client = FakeClient([FakeResponse("Answer [1]")])
    service = _service(client, model="gemini-3.5-flash")

    service.generate_answer("prompt")

    config = client.models.calls[0]["config"]
    assert config.thinking_config is None


def test_empty_response_raises_generation_request_error() -> None:
    client = FakeClient([FakeResponse("", candidates=[])])
    service = _service(client)

    with pytest.raises(GenerationRequestError):
        service.generate_answer("prompt")


def test_token_limit_response_retries_once_with_larger_output_allowance() -> None:
    client = FakeClient(
        [
            FakeResponse("Incomplete", candidates=[FakeCandidate("MAX_TOKENS")]),
            FakeResponse("Complete answer [1]", candidates=[FakeCandidate("STOP")]),
        ]
    )
    service = _service(client)

    assert service.generate_answer("prompt") == "Complete answer [1]"
    first_config = client.models.calls[0]["config"]
    second_config = client.models.calls[1]["config"]
    assert first_config.max_output_tokens == 1200
    assert second_config.max_output_tokens == 2400


def test_normal_complete_response_is_returned_unchanged() -> None:
    client = FakeClient([FakeResponse("Complete answer [1]")])
    service = _service(client)

    assert service.generate_answer("prompt") == "Complete answer [1]"
    assert len(client.models.calls) == 1
