"""Ollama-compatible web backend; credentials stay on the API server."""
import json
import os
import urllib.error
import urllib.request


def reply(messages):
    endpoint = os.environ.get("FLUX_OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
    if not endpoint.startswith("https://") and not endpoint.startswith("http://127.0.0.1:"):
        raise ValueError("FLUX_OLLAMA_URL must use HTTPS or local loopback HTTP.")
    messages = [dict(m) for m in messages]
    messages[0]["content"] = messages[0]["content"].replace("running locally on Windows", "accessed through a web interface")
    headers = {"Content-Type": "application/json"}
    key = os.environ.get("FLUX_OLLAMA_KEY")
    if key:
        headers["Authorization"] = "Bearer " + key
    payload = json.dumps({"model": os.environ.get("FLUX_MODEL", "qwen3:4b"),
                          "messages": messages, "stream": False, "think": False}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(endpoint, data=payload, headers=headers), timeout=180) as response:
            result = json.load(response)
        answer = result["message"]["content"].split("</think>")[-1].strip()
        if not answer or answer.startswith("<think>") or result.get("done_reason") == "length":
            raise ValueError("The model did not finish a reply. Please retry.")
        return answer
    except (urllib.error.URLError, TimeoutError, KeyError) as exc:
        raise RuntimeError("The AI server is unavailable. Check the server's model and connection settings.") from exc
