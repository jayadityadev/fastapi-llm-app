import asyncio
import json
import os
from collections.abc import AsyncIterable
from typing import Annotated

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field

# Load local .env variables if present
load_dotenv()

# Application metadata & configuration
app = FastAPI(
    title="FastAPI Cloud LLM Service",
    version="1.0.0",
    description="Production-ready authenticated LLM backend with native frontend colocation and SSE streaming",
)

# 1. Colocate Native Frontend (FastAPI 0.162+ app.frontend)
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "dist")
if os.path.exists(FRONTEND_DIR):
    app.frontend("/", directory=FRONTEND_DIR)


# 2. Strict Pydantic Schemas
class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10000, description="User prompt")
    system_prompt: str | None = Field(
        default=None, max_length=2000, description="Optional system guidance"
    )


class GenerateResponse(BaseModel):
    response: str
    model: str
    provider: str


# 3. Authentication Dependency (X-API-Key header)
def get_auth_token() -> str:
    return os.getenv("APP_AUTH_KEY", "demo-key-123")


async def verify_auth(
    x_api_key: Annotated[
        str | None,
        Header(
            description="API authentication key",
            examples=["demo-key-123"],
        ),
    ] = None,
) -> str:
    expected_token = get_auth_token()
    if not x_api_key or x_api_key != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key in X-API-Key header",
        )
    return x_api_key


# 4. Asynchronous Streaming LLM Engine
async def stream_llm(
    prompt: str, system_prompt: str | None = None
) -> AsyncIterable[dict]:
    groq_key = os.getenv("GROQ_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    nvidia_key = os.getenv("NVIDIA_API_KEY")

    # Priority A: Groq API (High rate limits, ultra-fast streaming)
    if groq_key:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            async with (
                httpx.AsyncClient(timeout=45.0) as client,
                client.stream(
                    "POST",
                    url,
                    headers={"Authorization": f"Bearer {groq_key}"},
                    json={
                        "model": "qwen/qwen3.8-27b",
                        "messages": messages,
                        "stream": True,
                    },
                ) as resp,
            ):
                if resp.status_code == 200:
                    async for line in resp.aiter_lines():
                        if line.startswith("data: ") and line.strip() != "data: [DONE]":
                            data = json.loads(line[6:])
                            delta = data["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield {
                                    "chunk": delta,
                                    "model": "qwen/qwen3.8-27b",
                                    "provider": "groq",
                                }
                    return
        except (httpx.HTTPError, json.JSONDecodeError, KeyError):
            pass  # Fall through to secondary provider if Groq encounters an issue

    # Priority B: Google Gemini API (StreamGenerateContent)
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:streamGenerateContent?alt=sse&key={gemini_key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            if system_prompt:
                payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

            async with (
                httpx.AsyncClient(timeout=45.0) as client,
                client.stream("POST", url, json=payload) as resp,
            ):
                if resp.status_code == 200:
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            data = json.loads(line[6:])
                            candidates = data.get("candidates", [])
                            if candidates and "content" in candidates[0]:
                                parts = candidates[0]["content"].get("parts", [])
                                if parts and "text" in parts[0]:
                                    yield {
                                        "chunk": parts[0]["text"],
                                        "model": "gemini-2.5-flash",
                                        "provider": "google-gemini",
                                    }
                    return
        except (httpx.HTTPError, json.JSONDecodeError, KeyError):
            pass

    # Priority C: NVIDIA NIM API
    if nvidia_key:
        try:
            url = "https://integrate.api.nvidia.com/v1/chat/completions"
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            async with (
                httpx.AsyncClient(timeout=45.0) as client,
                client.stream(
                    "POST",
                    url,
                    headers={"Authorization": f"Bearer {nvidia_key}"},
                    json={
                        "model": "meta/llama-3.1-8b-instruct",
                        "messages": messages,
                        "stream": True,
                    },
                ) as resp,
            ):
                if resp.status_code == 200:
                    async for line in resp.aiter_lines():
                        if line.startswith("data: ") and line.strip() != "data: [DONE]":
                            data = json.loads(line[6:])
                            delta = data["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield {
                                    "chunk": delta,
                                    "model": "meta/llama-3.1-8b-instruct",
                                    "provider": "nvidia-nim",
                                }
                    return
        except (httpx.HTTPError, json.JSONDecodeError, KeyError):
            pass

    # Development Fallback Stream
    words = [
        "FastAPI ", "Cloud ", "simulated ", "streaming ", "response ", "for: ", f"'{prompt}'.\n\n",
        "Both ", "SSE ", "streaming ", "and ", "Markdown ", "tables ", "are ", "fully ", "functional!\n\n",
        "To ", "switch ", "to ", "real ", "inference, ", "ensure ", "your ", "API ", "keys ", "are ", "configured."
    ]
    for w in words:
        await asyncio.sleep(0.04)
        yield {"chunk": w, "model": "simulation-engine", "provider": "fastapi-cloud-mock"}


# 5. Non-streaming fallback query
async def query_llm(
    prompt: str, system_prompt: str | None = None
) -> tuple[str, str, str]:
    accumulated = []
    final_model = "simulation-engine"
    final_provider = "fastapi-cloud-mock"
    async for item in stream_llm(prompt, system_prompt):
        accumulated.append(item["chunk"])
        final_model = item.get("model", final_model)
        final_provider = item.get("provider", final_provider)
    return "".join(accumulated), final_model, final_provider


# 6. Route Operations
@app.get("/api/healthz", response_model=HealthResponse, tags=["Operations"])
async def health_check() -> HealthResponse:
    """Readiness and liveness probe for FastAPI Cloud replicas."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        environment=os.getenv("FASTAPI_ENV", "production"),
    )


@app.post("/api/generate", response_model=GenerateResponse, tags=["LLM"])
async def generate(
    request: GenerateRequest,
    _: Annotated[str, Depends(verify_auth)],
) -> GenerateResponse:
    """Non-streaming authenticated endpoint returning complete LLM completion."""
    reply_text, model_name, provider_name = await query_llm(
        prompt=request.prompt, system_prompt=request.system_prompt
    )
    return GenerateResponse(
        response=reply_text,
        model=model_name,
        provider=provider_name,
    )


@app.post("/api/generate/stream", response_class=EventSourceResponse, tags=["LLM"])
async def generate_stream(
    request: GenerateRequest,
    _: Annotated[str, Depends(verify_auth)],
) -> AsyncIterable[ServerSentEvent]:
    """Server-Sent Events (SSE) streaming endpoint for real-time progressive output."""
    async for item in stream_llm(
        prompt=request.prompt, system_prompt=request.system_prompt
    ):
        yield ServerSentEvent(data=item)
    yield ServerSentEvent(data={"done": True})
