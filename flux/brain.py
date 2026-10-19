"""Only loopback networking; no model output is executed."""
import json
import logging
import urllib.error
import urllib.request

from .config import MODEL, OLLAMA_URL, SYSTEM


def build_context(history, memories, question):
    # Keep complete recent turns; the database retains the full transcript.
    recent = []
    budget = 12000
    for index in range(len(history) - 2, -1, -2):
        pair = history[index:index + 2]
        size = sum(len(m["content"]) for m in pair)
        if size > budget:
            break
        recent[0:0] = pair
        budget -= size
    facts = json.dumps([fact for _, fact in memories], ensure_ascii=False)
    logging.getLogger(__name__).info("Memory injected into prompt; ids=%s", [i for i, _ in memories])
    return [{"role": "system", "content": SYSTEM + "\nSaved user facts (JSON): " + facts}, *recent, {"role": "user", "content": question}]


def reply(messages):
    messages = [dict(message) for message in messages]
    if MODEL.lower().split(":")[0] == "qwen3":
        # Some installed templates unconditionally open <think>. Qwen's soft
        # switch closes that block without modifying the stored user message.
        for message in reversed(messages):
            if message["role"] == "user":
                message["content"] += "\n/no_think"
                break
        # Continue the assistant after an empty thinking block. The installed
        # Qwen3 template supports an assistant prefix and otherwise forces
        # an open <think>, even when think=False. This is request-only data.
        messages.append({"role": "assistant", "content": "<think>\n\n</think>\n\n"})
    payload = json.dumps({"model": MODEL, "messages": messages, "stream": False,
                          "think": False, "options": {"num_ctx": 8192, "num_predict": 768}}).encode("utf-8")
    request = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
    # Ignore system proxies so local conversations never go to an HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=180) as response:
            result = json.load(response)
        if result.get("done_reason") == "length":
            raise ValueError("The model reached its output limit before finishing. Try a shorter question or ask for a concise answer.")
        answer = result["message"]["content"].strip()
        # Older Qwen/Ollama templates can put a reasoning prefix in content even
        # with think=False, sometimes without its opening tag.
        if "</think>" in answer:
            answer = answer.split("</think>", 1)[1].strip()
        elif answer.startswith("<think>"):
            raise ValueError("The model returned reasoning without a final answer. Please retry.")
        if not answer:
            raise ValueError("Ollama returned an empty answer. Try a shorter question.")
        return answer
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise RuntimeError(f"Model not found. Run: ollama pull {MODEL}") from exc
        raise RuntimeError(f"Ollama returned HTTP {exc.code}. Check Ollama and the selected model.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("Cannot reach Ollama, or the response timed out. Open Ollama and try again. First model loading can be slow.") from exc
