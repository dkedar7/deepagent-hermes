<p align="center">
  <img src="./assets/header.svg" alt="deepagent-hermes — closed-loop reflection &amp; skill creation on LangGraph + deepagents" />
</p>

# deepagent-hermes

[![PyPI](https://img.shields.io/pypi/v/deepagent-hermes.svg)](https://pypi.org/project/deepagent-hermes/)
[![Python](https://img.shields.io/pypi/pyversions/deepagent-hermes.svg)](https://pypi.org/project/deepagent-hermes/)
[![License](https://img.shields.io/pypi/l/deepagent-hermes.svg)](./LICENSE)

A faithful reproduction of [Nous Research's Hermes Agent](https://github.com/nousresearch/hermes-agent) on top of LangGraph + [`deepagents`](https://github.com/langchain-ai/deepagents) + [`langgraph-stream-parser`](https://github.com/dkedar7/langgraph-stream-parser).

**Status: v0.1.0 live on PyPI.** Spec at [SPEC.md](./SPEC.md). Release notes in [CHANGELOG.md](./CHANGELOG.md). The runtime is verified end-to-end against a real Anthropic model — both the memory loop and the skill-creation loop close autonomously; see [`examples/dogfood.py`](./examples/dogfood.py) and [`examples/dogfood_procedural.py`](./examples/dogfood_procedural.py) for the traces.

## What it is

A `deepagents`-built agent with a **closed reflection→skill-creation loop**:

- After ~10 tool-using iterations, a review subagent runs in the background, writes/patches a `SKILL.md` capturing the pattern it just exercised, and ships it to a skill library.
- Next session, the agent reads the library at startup, sees the new skill's description in its system prompt, and can `skill_view(name)` to load the full body on demand (progressive disclosure per the [agentskills.io spec](https://agentskills.io/specification.md)).
- A weekly **curator** consolidates skills into umbrellas and archives stale ones.
- A **frozen-snapshot memory** (`MEMORY.md` + `USER.md`) preserves prefix-cache hits for the entire session.
- **FTS5 session search** indexes every past conversation in a local SQLite DB.
- Bundled **MarkdownProvider** that keyword-searches `<HERMES_HOME>/memories/notes/*.md` — drop hand-authored long-form context there and the agent surfaces relevant sections on demand. Zero external dependencies.

Designed to be loaded into the existing `deepagent-*` host family without UI changes — set `DEEPAGENT_AGENT_SPEC=deepagent_hermes.agent:graph` in any of them.

## One agent, every surface

deepagent-hermes is the reference agent of the **deep-agent family**: write your agent once — any LangGraph `CompiledGraph` — and run it on every surface with the same spec string (`module:attr` or `path/to/file.py:attr`), the same `deepagents.toml` config file, and the same `DEEPAGENT_*` environment variables.

| Surface | Package | Try it |
|---|---|---|
| Web app | [cowork-dash](https://github.com/dkedar7/cowork-dash) | `cowork-dash run --agent deepagent_hermes.agent:graph` |
| JupyterLab | [deepagent-lab](https://github.com/dkedar7/deepagent-lab) | `pip install deepagent-lab`, then the chat sidebar in `jupyter lab` |
| Terminal | [deepagent-code](https://github.com/dkedar7/deepagent-code) | `deepagent-code -a deepagent_hermes.agent:graph` |
| VS Code | [deepagent-vscode](https://github.com/dkedar7/deepagent-vscode) | chat participant + stdio sidecar |
| Reference agent | deepagent-hermes | **you are here** |
| Shared core | [langgraph-stream-parser](https://github.com/dkedar7/langgraph-stream-parser) | typed events + config resolver behind every surface |

## Installation

```bash
pip install deepagent-hermes
```

Or with `uv` (recommended):

```bash
uv venv .venv
. .venv/Scripts/activate      # Windows
. .venv/bin/activate          # macOS / Linux
uv pip install deepagent-hermes
```

### Optional extras

```bash
pip install "deepagent-hermes[openai]"     # OpenAI / OpenRouter / any OpenAI-wire provider
pip install "deepagent-hermes[daytona]"    # Daytona sandbox terminal backend
pip install "deepagent-hermes[modal]"      # Modal sandbox terminal backend
pip install "deepagent-hermes[ssh]"        # paramiko-backed SSH terminal backend
pip install "deepagent-hermes[dev]"        # tests + lint (contributors only)
```

## Picking a model

By default the agent uses `anthropic:claude-sonnet-4-5-20250929` and needs `ANTHROPIC_API_KEY` set. Swap the model via `--model` on the CLI or `model.default` in `deepagent-hermes.toml` — any [`init_chat_model`](https://python.langchain.com/api_reference/langchain/chat_models/langchain.chat_models.base.init_chat_model.html) string works.

### OpenAI / OpenRouter

```bash
pip install "deepagent-hermes[openai]"
export OPENAI_API_KEY=sk-…                   # or: OPENROUTER_API_KEY=sk-or-v1-…
export OPENAI_BASE_URL=https://openrouter.ai/api/v1   # only for OpenRouter
deepagent-hermes chat --model openai:openai/gpt-4o-mini
```

For OpenRouter specifically you usually also want:

```bash
export DEEPAGENT_HERMES_MODEL_DEFAULT="openai:openai/gpt-4o-mini"
export DEEPAGENT_HERMES_MODEL_AUX="openai:openai/gpt-4o-mini"
```

so the reflection subagent uses the same cheap model.

### Verify your setup

```bash
deepagent-hermes verify
```

does one live round-trip against the configured model and confirms the prompts, bundled skills, and FTS5 store all wire up correctly. Run this first on any fresh install — if it passes, `chat` will work.

## Quick start

```bash
# show resolved config + sources
deepagent-hermes --show-config

# interactive chat
deepagent-hermes chat

# chat against a different agent (same spec format as every deep-agent
# surface; overrides DEEPAGENT_AGENT_SPEC)
deepagent-hermes chat -a my_agent.py:graph

# from inside chat:
#   /skills            list available skills
#   /model anthropic:claude-haiku-4-5-20251001    switch models
#   /memory            dump current memory snapshot
#   /compress          force context compression
#   /quit
```

## Load into an existing host

Any `deepagent-*` host with `langgraph-stream-parser>=0.2` host conventions can run this agent:

```bash
# deepagent-code
DEEPAGENT_AGENT_SPEC="deepagent_hermes.agent:graph" deepagent-code

# deepagent-lab — set the same in deepagents.toml under [agent]
echo 'spec = "deepagent_hermes.agent:graph"' >> deepagents.toml
deepagent-lab
```

## Configuration

`deepagent-hermes.toml` (project) or `~/.deepagent-hermes/config.toml` (global). Layered resolution: `defaults < TOML < DEEPAGENT_HERMES_* env < CLI overrides`. See [SPEC §2](./SPEC.md#2-configuration) for every field; `deepagent-hermes --show-config` prints the resolved value + source of each.

## Architecture

See [SPEC.md](./SPEC.md) for the full 21-section requirements doc. Top-level layout:

- `src/deepagent_hermes/agent.py` — the compiled graph (entry point for hosts)
- `src/deepagent_hermes/config.py` — `HermesConfig(HostConfig)` resolver
- `src/deepagent_hermes/state.py` — `HermesState` (extends `AgentState`)
- `src/deepagent_hermes/reflection.py` — closed-loop middleware + review subagent
- `src/deepagent_hermes/skills/` — SkillLibrary, loader, tools
- `src/deepagent_hermes/memory/` — frozen-snapshot memory + provider ABC
- `src/deepagent_hermes/store/sqlite_fts.py` — `BaseStore` with FTS5
- `src/deepagent_hermes/search/session_search.py` — `session_search` tool
- `src/deepagent_hermes/compression.py` — `HermesCompressionMiddleware`
- `src/deepagent_hermes/caching.py` — `AnthropicCachingS3Middleware`
- `src/deepagent_hermes/budget.py` — `IterationBudgetMiddleware`
- `src/deepagent_hermes/tools/` — registry + 33 toolsets + 6 terminal envs
- `src/deepagent_hermes/cron/` — daemon + `cronjob` tool
- `src/deepagent_hermes/plugins/` — discovery + lifecycle hooks
- `src/deepagent_hermes/cli.py` — `deepagent-hermes` entry point
- `prompts/` — verbatim/paraphrased system-prompt building blocks

## Status by subsystem

| Subsystem | Status |
|---|---|
| Config + state + agent factory | ✅ working |
| Reflection loop (10-iter / 10-turn triggers, subagent review) | ✅ working — verified live |
| Skill library + agentskills.io validator | ✅ working |
| Skill loader (system-prompt injection + progressive disclosure) | ✅ working |
| `skill_view` / `skill_manage` / `skills_list` tools | ✅ working |
| Frozen-snapshot memory (MEMORY.md / USER.md) | ✅ working — verified live (702 bytes written autonomously) |
| SQLite FTS5 store + `session_search` (3 modes) | ✅ working |
| `MarkdownProvider` (bundled, default) | ✅ keyword search over `<HERMES_HOME>/memories/notes/*.md` — zero deps |
| Iteration budget middleware | ✅ working |
| Compression middleware (13-section template) | ✅ working |
| Anthropic `system_and_3` caching strategy | ✅ working |
| Tool registry + 33-toolset enum | ✅ working |
| `LocalEnvironment` terminal backend | ✅ working (Git Bash on Windows) |
| `DockerEnvironment` | ✅ working (gated on `docker info` reachability) |
| `SshEnvironment` | ✅ working (paramiko-backed, behind `[ssh]` extra) |
| `SingularityEnvironment` | ✅ working (auto-detects `singularity` / `apptainer`) |
| `DaytonaEnvironment` / `ModalEnvironment` | ✅ lazy SDK with defensive attribute probing (extras-gated) |
| Cron daemon + `cronjob` tool | ✅ working (deliverers: `local`, `stdout`, `agentmail`) |
| Plugin loader (4 discovery sources) | ✅ working (13 of 17 lifecycle hooks wired) |
| CLI + v1-essentials slash commands | ✅ working |
| Curator (skill lifecycle) | ✅ basic |
| Bundled skills | ✅ 26 from `nousresearch/hermes-agent` (MIT, attributed) |
| Self-evolution integration | 📄 docs only (separate offline repo) |

## License

MIT. See [LICENSE](./LICENSE). This project is a faithful reproduction of the design ideas in Nous Research's Hermes Agent — see [NOTICE](./NOTICE) for attribution.
