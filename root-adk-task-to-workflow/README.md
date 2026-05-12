# root-adk-task-to-workflow

TaskSplitter workflow agent with A2A protocol [experimental].
Agent generated with `agents-cli` version `0.1.3`

## TaskSplitter V0

This agent transforms a complex user goal into a validated executable task graph.
It does not execute real-world actions yet. V0 focuses on producing structured,
verifiable planning data:

- `GoalState`
- `MacroState`
- `CandidateTaskGraph`
- parallel quality reports
- repaired `TaskGraph`
- `ExecutionSchedule`
- human-readable plan
- decomposition trace

The workflow is intentionally classic and controlled:

```text
GoalInterpreter
-> StateAbstractor
-> CandidateTaskPlanner
-> Repair loop
   -> Parallel checkers
      -> CoverageChecker
      -> GranularityChecker
      -> DependencyChecker
      -> ExecutabilityChecker
      -> VerifiabilityChecker
   -> QualityAggregator
   -> RepairAgent
-> ExecutionScheduler
-> TraceLogger
-> FinalEmitter
```

The output treats each task as a state transition with preconditions,
postconditions, executor, verifier, dependencies, acceptance criteria, risk and
expansion metadata.

## Project Structure

```
root-adk-task-to-workflow/
├── app/         # Core agent code
│   ├── agent.py               # TaskSplitter workflow composition
│   ├── agent_runtime_app.py    # Agent Runtime application logic
│   ├── task_splitter/          # Schemas, prompts, scoring, scheduling, emitters
│   └── app_utils/             # App utilities and helpers
├── tests/                     # Unit, integration, and load tests
├── GEMINI.md                  # AI-assisted development guide
└── pyproject.toml             # Project dependencies
```

> 💡 **Tip:** Use [Gemini CLI](https://github.com/google-gemini/gemini-cli) for AI-assisted development - project context is pre-configured in `GEMINI.md`.

## Requirements

Before you begin, ensure you have:
- **uv**: Python package manager (used for all dependency management in this project) - [Install](https://docs.astral.sh/uv/getting-started/installation/) ([add packages](https://docs.astral.sh/uv/concepts/dependencies/) with `uv add <package>`)
- **agents-cli**: Agents CLI - Install with `uv tool install google-agents-cli`
- **Google Cloud SDK**: For GCP services - [Install](https://cloud.google.com/sdk/docs/install)


## Quick Start

Install required packages:

```bash
agents-cli install
```

Test the agent with a local web server:

```bash
agents-cli playground
```

You can also use features from the [ADK](https://adk.dev/) CLI with `uv run adk`.

## Commands

| Command              | Description                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------------- |
| `agents-cli install` | Install dependencies using uv                                                         |
| `agents-cli playground` | Launch local development environment                                                  |
| `agents-cli lint`    | Run code quality checks                                                               |
| `uv run pytest tests/unit tests/integration` | Run unit and integration tests                                                        |
| `agents-cli deploy`  | Deploy agent to Agent Runtime                                                                |
| `agents-cli publish gemini-enterprise` | Register deployed agent to Gemini Enterprise                    |
| [A2A Inspector](https://github.com/a2aproject/a2a-inspector) | Launch A2A Protocol Inspector                                                        |

## 🛠️ Project Management

| Command | What It Does |
|---------|--------------|
| `agents-cli scaffold enhance` | Add CI/CD pipelines and Terraform infrastructure |
| `agents-cli infra cicd` | One-command setup of entire CI/CD pipeline + infrastructure |
| `agents-cli scaffold upgrade` | Auto-upgrade to latest version while preserving customizations |

---

## Development

Edit workflow composition in `app/agent.py` and TaskSplitter internals in
`app/task_splitter/`.

Run deterministic tests:

```bash
uv run pytest tests/unit
```

Run unit tests plus integration tests. Integration tests are skipped by default
because they require live Gemini/Agent Runtime behavior:

```bash
uv run pytest tests/unit tests/integration
```

Opt into live integration tests only when you intend to use real credentials:

```bash
RUN_LIVE_ADK_TESTS=1 uv run pytest tests/integration
```

For interactive LLM testing, use `agents-cli playground` after confirming you
want to call remote model services.

## Deployment

```bash
gcloud config set project <your-project-id>
agents-cli deploy
```

To add CI/CD and Terraform, run `agents-cli scaffold enhance`.
To set up your production infrastructure, run `agents-cli infra cicd`.

## Observability

Built-in telemetry exports to Cloud Trace, BigQuery, and Cloud Logging.

## A2A Inspector

This agent supports the [A2A Protocol](https://a2a-protocol.org/). Use the [A2A Inspector](https://github.com/a2aproject/a2a-inspector) to test interoperability.
See the [A2A Inspector docs](https://github.com/a2aproject/a2a-inspector) for details.
