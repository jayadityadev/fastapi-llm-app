# Project AI Agent Instructions

## Overview
This is a FastAPI backend for AI / LLM workflows, managed with `uv`.

## Architecture & Code Principles
- **Keep it Simple (Ponytail / YAGNI)**: Implement the smallest, cleanest change that completely solves the problem. Do not add speculative layers, premature abstractions, or unused factory patterns.
- **Async First**: Use asynchronous FastAPI route handlers and async client calls where applicable.
- **Typed Everywhere**: Use strict Pydantic v2 schemas for all requests, responses, and environment variables.

## Package & Environment Management (`uv`)
- Run commands: `uv run <command>` (e.g. `uv run fastapi dev`, `uv run pytest`)
- Add dependencies: `uv add <package>`
- Add dev dependencies: `uv add --dev <package>`
- Reconcile library skills: `uvx library-skills install --all --copy -y`

## Available Skills & Tools
- Skills are versioned in `.agents/skills/` (and tracked via `skills-lock.json`).
- If you need to inspect codebase relationships, run `graphify query "<question>"`.
- When implementing a feature, use `/plan` or `/grill-me` before editing code.
- Run tests with `uv run pytest` before declaring a task complete.
