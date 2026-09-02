"""Contract tests for the public LLM type signatures and documentation."""

from __future__ import annotations

import inspect

from ceia_aisdk.llm import LLM


def test_llm_constructor_signature() -> None:
    signature = inspect.signature(LLM.__init__)
    parameters = signature.parameters
    assert "alias" in parameters
    assert parameters["alias"].default is None
    assert parameters["alias"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    for name in ("config", "device", "context_length", "tools"):
        assert name in parameters
        assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        assert parameters[name].default is None


def test_llm_chat_signature() -> None:
    signature = inspect.signature(LLM.chat)
    parameters = signature.parameters
    assert "prompt" in parameters
    assert parameters["max_tokens"].default == 512
    assert parameters["temperature"].default == 0.8
    assert parameters["seed"].default is None
    for name in ("max_tokens", "temperature", "seed"):
        assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY


def test_llm_docstring_states_not_thread_safe() -> None:
    class_doc = inspect.getdoc(LLM) or ""
    init_doc = inspect.getdoc(LLM.__init__) or ""
    blob = f"{class_doc}\n{init_doc}".lower()
    assert "not thread-safe" in blob or "not thread safe" in blob


def test_llm_properties_exist() -> None:
    assert isinstance(LLM.alias, property)
    assert isinstance(LLM.device, property)


def test_llm_stream_and_session_signatures() -> None:
    stream = inspect.signature(LLM.stream)
    assert stream.parameters["max_tokens"].default == 512
    assert stream.parameters["temperature"].default == 0.8
    session = inspect.signature(LLM.session)
    assert "system" in session.parameters
    from ceia_aisdk.llm import Session

    send = inspect.signature(Session.send)
    assert send.parameters["max_tokens"].default == 512
    stream_send = inspect.signature(Session.stream)
    assert stream_send.parameters["max_tokens"].default == 512
    session_doc = inspect.getdoc(Session) or ""
    assert "not thread-safe" in session_doc.lower() or "not thread safe" in session_doc.lower()


def test_async_llm_signature_and_docstring() -> None:
    from ceia_aisdk.llm import AsyncLLM

    signature = inspect.signature(AsyncLLM.__init__)
    assert "alias" in signature.parameters
    doc = inspect.getdoc(AsyncLLM) or ""
    init_doc = inspect.getdoc(AsyncLLM.__init__) or ""
    blob = f"{doc}\n{init_doc}".lower()
    assert "not thread-safe" in blob or "not thread safe" in blob
    assert "to_thread" in blob or "blocking" in blob
    chat = inspect.signature(AsyncLLM.chat)
    assert chat.parameters["max_tokens"].default == 512
