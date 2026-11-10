# Project Context

## Purpose

`agents-projects` is the local project in `D:/wzy/Python/agents-projects`. Its root metadata does not provide a maintained business description; establish business behavior from approved requirements and the existing project documents.

## Operating Model

- Package identity and dependency configuration are owned by `pyproject.toml`; package name: `agents-projects`.
- The declared Python requirement is `>=3.11`.
- Retain the existing `uv.lock` and configured package workflow.
- Preserve existing source organization and public contracts; the type instructions do not authorize reorganizing this project or inventing a business-module inventory.

## Important Routes

| Need | Existing owner |
|---|---|
| DDD Python project-type instructions | [AGENTS.md](AGENTS.md) |
| Project-specific instructions, constraints and task triggers | This CONTEXT |
| Package setup and usage | `README.md` |
| Package metadata, dependencies and tool configuration | `pyproject.toml` |
| Implementation packages | `src/` |
| Behavioral verification | `tests/` |
| Project-owned requirements and knowledge | `docs/` |

## Project Agent Rules

This CONTEXT owns this project's specific instructions, constraints and task
triggers. The global AGENTS owns user-wide operating/safety rules; this project's
AGENTS owns the shared DDD Python workflow. Update the appropriate owner and any
affected routes together. This user-requested ownership model takes precedence
over earlier template descriptions of where project instructions belong.

- Keep package/project-specific behavior and resource paths in the existing project owners. Record newly verified operating constraints here; select checks from the actual project configuration and tests.
