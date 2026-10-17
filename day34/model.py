"""OpenRouter без повторов; бюджет предоставляется внешним общим адаптером."""
import json
import math
import os
import time
import multiprocessing
import urllib.request


class ModelResponseError(ValueError):
    def __init__(self, reason, metadata, usage):
        super().__init__(reason)
        self.reason = reason
        self.metadata = metadata
        self.usage = usage


def read_body(response, deadline):
    """read1 возвращает доступный chunk; timeout уменьшается до общего дедлайна."""
    chunks = []
    size = 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("network_deadline")
        # AICODE-NOTE: urllib timeout ограничивает idle, поэтому каждый read1
        # получает остаток абсолютного бюджета, а не исходный timeout.
        sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
        if sock is not None:
            sock.settimeout(remaining)
        chunk = response.read1(min(65536, 1_000_001 - size))
        if time.monotonic() >= deadline:
            raise TimeoutError("network_deadline")
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        size += len(chunk)
        if size > 1_000_000:
            raise ValueError("Ответ модели слишком велик")


def _transport_worker(connection, url, encoded, headers, timeout):
    try:
        request = urllib.request.Request(url, encoded, headers)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = read_body(response, time.monotonic() + timeout)
        connection.send((True, raw))
    except Exception as exc:
        connection.send((False, type(exc).__name__))
    finally:
        connection.close()


def request_with_deadline(url, encoded, headers, timeout):
    """Родитель прерывает весь transport: DNS/connect/TLS/headers/body."""
    if timeout <= 0:
        raise TimeoutError("network_deadline")
    context = multiprocessing.get_context("spawn")
    receive, send = context.Pipe(duplex=False)
    process = context.Process(target=_transport_worker, args=(send, url, encoded, headers, timeout), daemon=True)
    deadline = time.monotonic() + timeout
    try:
        process.start()
        send.close()
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not receive.poll(remaining):
            raise TimeoutError("network_deadline")
        success, value = receive.recv()
        if time.monotonic() >= deadline:
            raise TimeoutError("network_deadline")
        if not success:
            raise RuntimeError("network_transport:" + value)
        return value
    finally:
        receive.close()
        send.close()
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=0.2)
            if process.is_alive():
                process.kill()
                process.join()


class OpenRouterModel:
    name = "qwen/qwen3.8-max-0902"
    provider = "alibaba/us-east-1"

    def __init__(self, budget, api_key=None, transport=None):
        if budget is None:
            raise ValueError("Нужен общий budget adapter")
        self.transport = transport or request_with_deadline
        self.budget = budget
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY не задан")

    def complete(self, messages, tools, *, run_id, timeout):
        deadline = time.monotonic() + timeout
        payload = {"model": self.name, "messages": messages, "tools": tools, "tool_choice": "auto", "max_tokens": 4096, "reasoning": {"effort": "low", "exclude": True}, "temperature": 0,
                   "provider": {"only": [self.provider], "allow_fallbacks": False}}
        encoded = json.dumps(payload, ensure_ascii=False).encode()
        if len(encoded) > 100000:
            raise ValueError("Лимит контекста 100000 байт")
        reserve = self.budget.reserve(run_id, (len(encoded) + 4096) * 2 / 1_000_000 + 4096 * 6 / 1_000_000)
        actual = None
        try:
            raw = self.transport("https://openrouter.ai/api/v1/chat/completions", encoded,
                                 {"Authorization": "Bearer " + self.api_key, "Content-Type": "application/json"},
                                 deadline - time.monotonic())
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ModelResponseError("invalid_response_envelope", {"actual_model": None, "actual_provider": None}, None)
            usage = data.get("usage")
            if isinstance(usage, dict):
                cost = usage.get("cost")
                if type(cost) in (float, int) and math.isfinite(cost) and cost >= 0:
                    actual = cost
            metadata = {"actual_model": data.get("model"), "actual_provider": data.get("provider")}
            if metadata["actual_model"] is None or metadata["actual_provider"] is None:
                raise ModelResponseError("response_identity_missing", metadata, usage)
            if metadata["actual_model"] not in (None, self.name) or metadata["actual_provider"] not in (None, "Alibaba", self.provider):
                raise ModelResponseError("response_identity_mismatch", metadata, usage)
            choices = data.get("choices")
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                raise ModelResponseError("invalid_choices", metadata, usage)
            choice = choices[0]
            if not isinstance(choice.get("message"), dict):
                raise ModelResponseError("invalid_message", metadata, usage)
            if choice.get("finish_reason") not in {"stop", "tool_calls"}:
                raise ModelResponseError("finish_reason:" + str(choice.get("finish_reason")), metadata, usage)
            return {"message": choice["message"], "usage": usage, "metadata": metadata}
        finally:
            self.budget.settle(reserve, actual)
