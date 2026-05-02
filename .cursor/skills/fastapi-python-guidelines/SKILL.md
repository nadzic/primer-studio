---
name: fastapi-python-guidelines
description: Applies project FastAPI and Python coding conventions for scalable API work. Use when implementing or reviewing FastAPI endpoints, schemas, async data access, validation, middleware, or API performance concerns.
---

# FastAPI Python Guidelines

## Core principles

- Write concise, technical responses and code.
- Prefer functional, declarative patterns over classes when practical.
- Use clear snake_case names and descriptive boolean/auxiliary variable names.
- Reduce duplication via small reusable functions.
- Use RORO style where it improves consistency (`receive object, return object`).

## FastAPI and typing

- Use `def` for pure sync code and `async def` for I/O-bound operations.
- Add type hints on all public function signatures.
- Prefer Pydantic models (v2) over raw dictionaries for request/response validation.
- Keep route modules structured with router exports, sub-routes, utilities, and schemas.

## Error handling

- Handle invalid states early with guard clauses.
- Prefer early returns over deep nesting.
- Keep the happy path clear and late.
- Raise `HTTPException` for expected request errors.
- Provide user-readable error messages and keep logging structured.

## Performance guidance

- Avoid blocking I/O in request paths.
- Use async DB/API calls (`asyncpg`, `aiomysql`, or SQLAlchemy 2 async patterns).
- Add caching for frequently requested stable data.
- Keep payload validation/serialization efficient with Pydantic models.

## FastAPI-specific conventions

- Prefer lifespan context managers over startup/shutdown event handlers where feasible.
- Use middleware for logging, monitoring, and unexpected error capture.
- Keep dependency injection explicit for shared state/resources.
- Model responses with typed schemas and explicit return shapes.
