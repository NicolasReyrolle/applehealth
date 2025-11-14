<!-- Auto-generated starter Copilot instructions. Edit as the project grows. -->
# Copilot / AI Agent Instructions

Purpose: Help an AI coding agent become productive in this repository by
explaining where to look, what to ask, and which project-specific patterns
matter. This file is intentionally short and action-oriented.

1) Quick repo-status checks
- If the repo has no code files, ask the human: "Where are the source files?"
- Run a file search for these markers: `package.json`, `pyproject.toml`, `requirements.txt`,
  `setup.py`, `Pipfile`, `pom.xml`, `build.gradle`, `*.sln`, `*.csproj`, `Podfile`, `pubspec.yaml`,
  `android/`, `ios/`, `apps/`, `src/`, `app/`, `README.md`.

2) High-level goals for the agent
- Identify the project type (web API, mobile app, library, CLI, native app).
- Find the build and test commands and verify them with the user if unclear.
- Locate the main entrypoints and integration points: API controllers, background workers,
  platform-specific folders (`android/`, `ios/`, `Net/`, `src/`), and CI config (`.github/workflows`).

3) Concrete discovery steps (in order)
- Search for `README.md` or docs; if present, extract build/test/run commands.
- If `package.json` found: open `scripts` to get commands like `start`, `test`, `build`.
- If Python found (`pyproject.toml`, `requirements.txt`): look for `tests/`, `tox.ini`, `pytest` config.
- If .NET found (`*.sln`, `*.csproj`): identify solution projects and `dotnet build` entrypoint.
- If iOS/Android: locate Xcode/Gradle files and ask which platforms to target locally.

4) Project-specific conventions (what to record here)
- Note any non-standard build/test commands discovered (example: `pwsh ./scripts/ci.ps1`).
- Record any custom lint or formatting steps (e.g., `npm run format`, `dotnet format`).
- Document branching/CI expectations if found under `.github/workflows` or `azure-pipelines.yml`.

5) How to modify code safely
- Create small, focused changes; run the project's tests/linters before proposing a PR.
- When in doubt about runtime environment (OS, SDK versions), ask the user rather than guessing.

6) Examples and patterns to look for (copy snippets into PR descriptions)
- API route example: `src/controllers/*.js` or `Controllers/*Controller.cs` — mention file and method names.
- Background worker example: `workers/`, `tasks/`, or a hosted service in `.NET` (`IHostedService`).
- Config example: `config/*.json`, `.env`, `appsettings.json` — include keys used for integration.

7) If you can't discover required info
- Ask these exact questions:
  - "What command builds this project locally (exact shell command for Windows PowerShell)?"
  - "What command runs the full test suite?"
  - "Which files are the primary entrypoints or services I should inspect?"

8) Merge guidance
- If `.github/copilot-instructions.md` already exists, merge by preserving any concrete
  build/test commands and examples; prefer discovered commands over generic templates.

9) Where to update this file
- Keep short actionable notes here as you discover conventions (example: "Use `pwsh -File build.ps1` on Windows").

---
If you want, I can: run a glob search for the files listed above, open any that exist, and replace
this starter with a merged, concrete instruction file that cites real commands and filenames from the repo.
