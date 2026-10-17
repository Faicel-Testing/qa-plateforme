"""Native Python LangChain operations used by all agent entry points."""
import json
from collections import Counter
from langchain_core.messages import convert_to_messages
from langchain_core.output_parsers import JsonOutputParser
from .model import GatewayChatModel


def typed_structured(messages, schema, *, model=None, retries=2):
    """Validate the complete response; retry contract errors, never provider failures."""
    from pydantic import ValidationError
    model = model or GatewayChatModel()
    attempts = max(1, min(int(retries), 3))
    prompt = [*messages, {"role": "user", "content":
              "Return ONLY a complete JSON object matching this JSON Schema: "
              + json.dumps(schema.model_json_schema(), ensure_ascii=False)}]
    for attempt in range(attempts):
        answer = model.invoke(convert_to_messages(prompt), temperature=0, rag=False)
        text = answer.content
        if not isinstance(text, str):
            raise ValueError("Expected a text JSON response")
        if text.strip().startswith("```"):
            text = text.strip().split("\n", 1)[-1].removesuffix("```").strip()
        try:
            return schema.model_validate_json(text)
        except ValidationError:
            if attempt + 1 == attempts:
                raise ValueError("Model response does not satisfy the output contract") from None
            prompt.append({"role": "user", "content":
                           "Your response did not match the schema. Check required fields, enums and ranges. "
                           "Use unknown/insufficient evidence when the supplied facts are insufficient."})


def chat(messages, options=None, *, model=None):
    response = (model or GatewayChatModel()).invoke(convert_to_messages(messages), **(options or {}))
    result = {"role": "assistant", "content": response.content}
    if response.tool_calls:
        result["tool_calls"] = [{"id": call["id"], "type": "function", "function": {
            "name": call["name"], "arguments": json.dumps(call["args"], ensure_ascii=False)
        }} for call in response.tool_calls]
    return {"message": result, "done": True}


def structured(messages, schema, retries=2, temperature=None, *, model=None):
    model = model or GatewayChatModel()
    prompt = [*messages, {"role": "user", "content": "Return ONLY a complete JSON object matching: " + json.dumps(schema, ensure_ascii=False)}]
    # Provider errors propagate immediately. Only a malformed JSON answer is retried.
    for attempt in range(max(1, min(int(retries), 3))):
        answer = model.invoke(convert_to_messages(prompt), temperature=temperature)
        text = answer.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].removesuffix("```").strip()
        try:
            # LangChain's parser accepts partial JSON; require a complete document first.
            json.loads(text)
            return JsonOutputParser().invoke(text)
        except (ValueError, TypeError):
            if attempt + 1 >= max(1, min(int(retries), 3)):
                raise ValueError("LLM output is not complete JSON; no verdict accepted")
            prompt.append({"role": "user", "content": "Previous response was invalid JSON. Return a complete JSON document."})


def dispatch(method, args, agent="quality", model=None):
    model = model or GatewayChatModel(agent=agent)
    messages = args[0]
    if method in {"chat", "chatStream"}:
        return chat(messages, args[1] if len(args) > 1 else {}, model=model)
    if method == "chatStructured":
        return structured(messages, args[1], args[2] if len(args) > 2 else 2,
                          args[3] if len(args) > 3 else None, model=model)
    if method == "chatConfident":
        threshold = args[1] if len(args) > 1 else 0.7
        data = structured(messages, {"result": "string", "confidence": "number [0,1]", "reasoning": "short justification"}, model=model)
        confidence = data.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise ValueError("Invalid model confidence")
        return {**data, "above_threshold": confidence >= threshold}
    if method == "chatCot":
        evidence = chat([*messages, {"role": "user", "content": "Give a concise evidence-based conclusion. Distinguish facts, hypotheses and limitations."}], model=model)["message"]["content"]
        if len(args) < 2 or args[1] is None:
            return evidence
        final = chat([*messages, {"role": "assistant", "content": evidence}, {"role": "user", "content": args[1]}], model=model)
        return {"reasoning": evidence, "structured": final["message"]["content"]}
    if method == "chatAdversarial":
        proposal = chat(messages, model=model)["message"]["content"]
        critique = chat([*messages, {"role": "assistant", "content": proposal}, {"role": "user", "content": "Audit this proposal. Cite only demonstrable defects, and distinguish suggestions and uncertainty."}], model=model)["message"]["content"]
        final = chat([*messages, {"role": "assistant", "content": proposal}, {"role": "user", "content": "Revise the answer using this critique: " + critique}], model=model)["message"]["content"]
        return {"proposal": proposal, "critique": critique, "final": final}
    if method == "chatSelfConsistent":
        count = max(1, min(int(args[2] if len(args) > 2 else 3), 3))
        responses = [structured(messages, args[1], temperature=t, model=model) for t in [0.3, 0.7, 0.9][:count]]
        key = next(iter(responses[0]))
        counts = Counter(str(item.get(key, "")) for item in responses)
        winner = next(item for item in responses if str(item.get(key, "")) == counts.most_common(1)[0][0])
        return {"responses": responses, "winner": winner, "vote_counts": dict(counts), "n_votes": len(responses)}
    raise ValueError("Unsupported LangChain operation")
