# Testing Guidelines

## Core Principles
- Test user behavior, not implementation details
- Test one behavior per test
- Name tests: `test_<function>_<scenario>`

## Critical Mocking Rules

**Only mock at system boundaries:**
- External APIs, network calls
- Database connections
- File system operations
- Third-party services

**Never mock:**
- Your own functions or classes
- Business logic
- Internal module interactions

**If a test needs more than 2 mocks, stop and ask the user to reconsider the approach.**

## What to Test
- Real user workflows
- Failure modes and edge cases (null, empty, invalid types, boundaries)
- Integration points between components
- Performance characteristics (memory, startup time, responsiveness)

## What NOT to Test
- Framework internals
- Language features or standard library
- Third-party library behavior
- Implementation details that could change

## Test Types
**Unit tests:** Pure functions, calculations, validators  
**Integration tests:** API endpoints, component interactions, real database operations  
**E2E tests:** Critical user journeys only (core features)

## Regression Tests
- Always write failing test first, then fix code
- Name: `test_regression_<issue>_<description>`
- Keep forever as documentation