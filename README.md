# StackDesigner: The One and Only Tech Stack Recommender

A multi-agent AI system that helps you figure out what infrastructure to actually build. Instead of throwing three different architects at the same problem and hoping for consensus, this system runs them independently - one optimizing for cost, one for speed, one for security. Then it ranks them all by real pricing data.

## Features

- **Multi-Agent Orchestration**: Four specialized agents coordinate via LangGraph to extract requirements, generate architecture plans, analyze costs, and recommend the best fit
- **Three Independent Planning Perspectives**:
  - **COA** (Cost-Optimized Agent) - Minimizes TCO using serverless/managed services
  - **POA** (Performance-Optimized Agent) - Maximizes throughput and scalability with dedicated compute
  - **SACA** (Security & Compliance Agent) - Prioritizes data protection and regulatory compliance
- **Real-Time Cost Analysis** - Queries PostgreSQL pricing database (via MCP) to estimate monthly costs for each plan
- **AI-Generated Summaries** - Non-technical stakeholder-friendly explanations powered by local LLMs

## Tech Stack

- **LangGraph**: Multi-step workflow orchestration and state management
- **DeepAgents**: Coordinated multi-agent reasoning with sub-agent delegation
- **LangChain**: Agent framework and structured output handling
- **LangChain-MCP-Adapters**: Database connectivity for cost queries
- **Streamlit**: Interactive web frontend
- **Ollama**: Local LLM inference (qwen3:8b, minimax-m3:cloud models)
- **PostgreSQL**: Pricing and service alias database
- **Pydantic**: Schema validation for structured outputs

## Quick Start

### Prerequisites
- Python 3.12+
- Ollama running locally with `qwen3:8b` and `minimax-m3:cloud` models pulled
- PostgreSQL instance with pricing data (`cloud_services`, `service_aliases` tables)
- `uv` package manager

### Installation

```bash
git clone [<repo>](https://github.com/Saicodes1/StackDesigner)
cd StackDesigner
uv sync
```

### Running the App

```bash
streamlit run main.py
```

Open your browser to `http://localhost:8501` and describe your infrastructure needs. The system will generate three candidate architectures, cost estimates, and a personalized recommendation.

## Architecture

```
Requirement Agent (extract & validate user input)
    ↓
Planning Agent (fan-out to 3 independent sub-agents)
├─ COA Sub-agent → cost-optimized architecture
├─ POA Sub-agent → performance-optimized architecture  
└─ SACA Sub-agent → security-optimized architecture
    ↓
Cost Analysis Agent (MCP + PostgreSQL pricing lookup)
    ↓
Recommendation Agent (rank & pick best fit)
    ↓
Streamlit UI (display tech stack, cost, summary)
```

### Key Technical Insights

- **DeepAgents Integration**: The Planning Agent uses DeepAgents to coordinate three independent sub-agents via the `task` tool. Each sub-agent works blind to the others' reasoning, which means you get genuinely different perspectives instead of them all hedging toward the same answer.
- **MCP Database Access**: Cost Analysis Agent connects to PostgreSQL via LangChain-MCP-Adapters. Instead of guessing prices from training data, it actually queries a live database with fuzzy matching (pg_trgm similarity) to find the closest service match.
- **Structured Outputs**: All agents use Pydantic models + LangChain's `ToolStrategy` to guarantee schema compliance. No hallucinated fields, no surprises.
- **Skill-Driven Reasoning**: Each planning sub-agent gets a domain-specific skill file (COA/POA/SACA) that guides their technology choices. This keeps them focused without needing massive system prompts.

### Skill Files

The system uses four domain-specific skill files to guide agent reasoning:

- **`coa/SKILL.md`** - Cost optimization heuristics (serverless preferences, reserved instances, managed services, lifecycle policies)
- **`poa/SKILL.md`** - Performance optimization heuristics (dedicated compute, replicas, caching layers, multi-AZ deployment)
- **`saca/SKILL.md`** - Security & compliance heuristics (private networking, encryption-by-default, least-privilege IAM, audit logging, HIPAA/GDPR/SOC 2 guidance)
- **`requirements/SKILL.md`** - Requirement extraction guide (identifies explicit/implicit needs, guides agent to suggest alternatives)

Each skill file is basically a knowledge base. Agents reference them to stay consistent with their optimization lens, so you don't need to jam everything into the system prompt.

## Project Structure

```
.
├── main.py                          # Streamlit UI + pipeline orchestrator
├── states.py                        # LangGraph state schema
├── agents/
│   ├── requirement_agent.py         # Requirements extraction
│   ├── planning_agent.py            # Multi-lens planning orchestrator
│   ├── cost_analysis_agent.py       # MCP-based pricing lookup
│   ├── recommendation_agent.py      # Final ranking
│   ├── extracting_services_agent.py # Service normalization
│   ├── skills/                      # Agent knowledge bases
│   │   ├── coa/SKILL.md            # Cost optimization heuristics
│   │   ├── poa/SKILL.md            # Performance optimization heuristics
│   │   ├── saca/SKILL.md           # Security/compliance heuristics
│   │   └── requirements/SKILL.md   # Requirement extraction guide
│   └── outputs/                     # Generated JSON artifacts
└── pyproject.toml
```

## Output Examples

After running the pipeline, check:
- `agents/outputs/requirement_agent/run.json` - Parsed requirements
- `agents/outputs/planning_agent/all_plans.json` - Three architectures with reasoning
- `agents/outputs/cost_analysis_agent/final_cost.json` - Estimated monthly costs
- `agents/outputs/recommendation_agent/recommendation.json` - Recommendation + pros/cons


## Example Outputs

The repository includes sample JSON outputs demonstrating the system's full pipeline:

- `agents/outputs/requirement_agent/run.json` - Example parsed requirements
- `agents/outputs/planning_agent/all_plans.json` - Example three-plan output (COA/POA/SACA with tech stacks and reasoning)
- `agents/outputs/cost_analysis_agent/` - Example cost analysis with matched/unmatched services
- `agents/outputs/recommendation_agent/recommendation.json` - Example ranked recommendation with pros/cons
- `agents/outputs/extracing_services_agent/extracted_services.json` - Example normalized services

Review these to understand the output format before running the pipeline.
