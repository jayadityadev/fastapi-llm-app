import os
from typing import Annotated

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

# Load local .env variables if present
load_dotenv()

# Application metadata & configuration
app = FastAPI(
    title="FastAPI Cloud LLM Service",
    version="1.0.0",
    description="Production-ready authenticated LLM backend with native frontend colocation",
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


# 4. Asynchronous LLM Client Engine
async def query_llm(
    prompt: str, system_prompt: str | None = None
) -> tuple[str, str, str]:
    gemini_key = os.getenv("GEMINI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")
    nvidia_key = os.getenv("NVIDIA_API_KEY")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # A. Google Gemini API (Free tier)
        if gemini_key:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            if system_prompt:
                payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return text, "gemini-2.5-flash", "google-gemini"
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Gemini API returned status {resp.status_code}: {resp.text}",
            )

        # B. Groq API (Free tier / Ultra-fast OpenAI compatible)
        if groq_key:
            url = "https://api.groq.com/openai/v1/chat/completions"
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {groq_key}"},
                json={"model": "qwen/qwen3.8-27b", "messages": messages},
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                return text, "qwen/qwen3.8-27b", "groq"
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Groq API returned status {resp.status_code}: {resp.text}",
            )

        # C. NVIDIA NIM API
        if nvidia_key:
            url = "https://integrate.api.nvidia.com/v1/chat/completions"
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {nvidia_key}"},
                json={"model": "meta/llama-3.1-8b-instruct", "messages": messages},
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                return text, "meta/llama-3.1-8b-instruct", "nvidia-nim"
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"NVIDIA API returned status {resp.status_code}: {resp.text}",
            )

    # D. Development Fallback Simulation (When no upstream API key is set)
    mock_reply = (
        f"FastAPI Cloud simulated response to: '{prompt}'.\n\n"
        "To enable real LLM inference, configure your API key in FastAPI Cloud:\n"
        "  fastapi cloud env set GEMINI_API_KEY=your_key\n"
        "  (or GROQ_API_KEY / NVIDIA_API_KEY)"
    )
    return mock_reply, "simulation-engine", "fastapi-cloud-mock"


# 5. Route Operations
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
    """Authenticated endpoint that serves real-time LLM inference."""
    reply_text, model_name, provider_name = await query_llm(
        prompt=request.prompt, system_prompt=request.system_prompt
    )
    return GenerateResponse(
        response=reply_text,
        model=model_name,
        provider=provider_name,
    )
