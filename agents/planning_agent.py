from deepagents import create_deep_agent
import os
from deepagents.backends import FilesystemBackend
from deepagents.middleware import SkillsMiddleware
from pathlib import Path
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from typing import Optional
import json
from langchain.messages import HumanMessage
import re


def extract_json_from_markdown(text: str) -> dict:
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    return json.loads(text)


class resp_format(BaseModel):
    tech_stack: list[str] = Field(
        description=(
            "List of specific technologies, services, and infrastructure components "
            "recommended for this plan (e.g., 'AWS Lambda', 'PostgreSQL RDS', "
            "'Cloudflare CDN'). Be specific — name actual services/products, not "
            "generic categories."
        )
    )
    description: str = Field(
        description=(
            "A concise (3-5 sentence) summary of the proposed architecture: what "
            "the overall system design looks like, how the major components fit "
            "together, and what this plan is optimized for. Should be understandable "
            "without needing to read the reasoning field."
        )
    )
    reasoning: str = Field(
        description=(
            "Explanation of why this specific combination of technologies was chosen, "
            "written from this agent's optimization perspective (cost, performance, or "
            "security/compliance). Should explicitly call out any trade-offs accepted "
            "(e.g., 'chose managed Postgres over self-hosted to reduce ops overhead at "
            "a modest cost premium') and confirm how hard user-stated constraints "
            "(budget ceiling, compliance requirements, etc.) were respected."
        )
    )


def extract_and_validate_plans(result: dict):
    messages = result["messages"]
    tool_call_to_agent = {}
    for m in messages:
        if m.type == "ai" and getattr(m, "tool_calls", None):
            for tc in m.tool_calls:
                if tc.get("name") == "task":
                    tool_call_to_agent[tc["id"]] = tc["args"].get("subagent_type")

    validated_plans = {}
    for m in messages:
        if m.type == "tool" and m.tool_call_id in tool_call_to_agent:
            agent_name = tool_call_to_agent[m.tool_call_id]
            try:
                raw_json = extract_json_from_markdown(m.content)
                validated = resp_format(**raw_json)
                validated_plans[agent_name] = validated.model_dump()
            except Exception as e:
                print(f"Failed to parse/validate {agent_name}: {e}")
                validated_plans[agent_name] = {"_raw": m.content, "_error": str(e)}

    return validated_plans


def run_planning_agent():
    model = ChatOllama(model="minimax-m3:cloud")

    PROJECT_ROOT = Path(__file__).resolve().parent
    backend = FilesystemBackend(root_dir=str(PROJECT_ROOT))

    COA = {
        "name": "COA",
        "description": "Designs infrastructure architectures that minimize total cost of ownership while still meeting the stated functional requirements. Prioritizes serverless/managed services over dedicated infrastructure where viable, favors reserved/spot pricing models, and avoids over-provisioning. Will accept modest performance or redundancy trade-offs if they meaningfully reduce cost. Does not compromise on hard security or compliance constraints explicitly stated by the user.",
        "system_prompt": ''' You are the Cost-Optimized Planning Agent in a multi-agent infrastructure procurement system.
                            Keep the output constrained to 200 words.
                            Your job: given a set of validated project requirements, design ONE candidate infrastructure architecture that minimizes total cost of ownership (TCO) while still satisfying every functional requirement.

                            Core priorities, in order:
                            1. Never violate hard constraints explicitly stated by the user (compliance requirements, mandatory on-prem/cloud provider, explicit budget ceiling, required uptime SLA if stated as mandatory).
                            2. Minimize ongoing monthly/annual cost.
                            3. Prefer serverless and managed services over self-hosted/dedicated infrastructure wherever the workload allows it.
                            4. Prefer reserved, spot, or committed-use pricing over on-demand where usage patterns are predictable.
                            5. Avoid over-provisioning — right-size everything to actual stated load, not worst-case headroom, unless the user explicitly asked for headroom.

                            You may accept modest reductions in redundancy, performance, or provisioned headroom if doing so meaningfully reduces cost. You must flag clearly (in `tradeoffs_accepted`) any such reduction so downstream agents can evaluate it.

                            Do not recommend cutting-edge, experimental, or performance-first services just because they're popular — this is not your lens. If in doubt between two options, choose the cheaper one that still meets the stated requirement.

                            Always read your skill file at /skills/cost_optimized_agent before producing output. Respond only in the structured format provided (resp_format).''',
        "skills": ["/skills/coa"]
    }

    POA = {
        "name": "POA",
        "description": "Designs infrastructure architectures that maximize throughput, low latency, and scalability under expected load. Prioritizes dedicated compute, high-performance storage/networking tiers, and horizontal scaling patterns over cost savings. Assumes budget is a secondary constraint relative to meeting performance SLAs, but still respects explicit budget ceilings if provided. Does not compromise on hard security or compliance constraints.",
        "system_prompt": ''' You are the Performance-Optimized Planning Agent in a multi-agent infrastructure procurement system.
                            Keep the output constrained to 200 words.
                            Your job: given a set of validated project requirements, design ONE candidate infrastructure architecture that maximizes throughput, minimizes latency, and scales cleanly under expected and peak load.

                            Core priorities, in order:
                            1. Never violate hard constraints explicitly stated by the user (compliance requirements, mandatory provider, explicit hard budget ceiling if stated as non-negotiable).
                            2. Meet or exceed any stated performance SLA (latency, throughput, concurrent users).
                            3. Prefer dedicated compute, high-performance storage tiers, and low-latency networking over cost-minimized alternatives.
                            4. Design for horizontal scalability (auto-scaling groups, load balancing, read replicas, caching layers) even if the user didn't explicitly ask for it, when the stated scale suggests it will matter.
                            5. Treat cost as a secondary constraint — you may recommend more expensive options than a cost-optimized plan would, but you must still respect any budget ceiling the user explicitly stated as a hard limit.

                            Do not recommend the cheapest viable option just because it works — this is not your lens. If in doubt between two options of similar performance, prefer the one with better scalability headroom.

                            Always read your skill file at /skills/performance_optimized_agent before producing output. Respond only in the structured format provided (resp_format).''',
        "skills": ["/skills/poa"]
    }

    SACA = {
        "name": "SACA",
        "description": "Designs infrastructure architectures that prioritize data protection, regulatory compliance, and attack-surface minimization above cost or raw performance. Prefers private networking, encryption-by-default services, strict IAM boundaries, and audit-logging-capable components. Will recommend more conservative, higher-cost, or lower-performance options if they materially reduce security or compliance risk.",
        "system_prompt": ''' You are the Security & Compliance-First Planning Agent in a multi-agent infrastructure procurement system.
                            Keep the output constrained to 200 words.
                            Your job: given a set of validated project requirements, design ONE candidate infrastructure architecture that prioritizes data protection, regulatory compliance, and attack-surface minimization above cost or raw performance.

                            Core priorities, in order:
                            1. Satisfy every explicitly stated compliance/regulatory requirement (e.g., GDPR, HIPAA, SOC 2, data residency) without exception — these are non-negotiable regardless of cost or performance impact.
                            2. Minimize attack surface: prefer private networking, least-privilege IAM, encryption-by-default (at rest and in transit), and audit-logging-capable services.
                            3. Prefer well-established, widely-audited services over newer/less-proven options when both are otherwise viable.
                            4. Accept higher cost or lower raw performance if it materially reduces security or compliance risk.
                            5. Still respect any explicitly stated hard budget ceiling if one exists — flag a conflict rather than silently ignoring it.

                            Do not recommend the fastest or cheapest option if it compromises data protection, access control, or auditability — this is not your lens. If in doubt between two options, choose the one with the stronger security/compliance posture.

                            Always read your skill file at /skills/security_and_compliance_agent before producing output. Respond only in the structured format provided (resp_format).''',
        "skills": ["/skills/saca"]
    }

    subagents = [COA, POA, SACA]
    agent = create_deep_agent(
        model=model,
        subagents=subagents,
        system_prompt='''You are the Planning Agent — the orchestrator in a multi-agent infrastructure procurement system called InfraPilot.

## Your role
Your three specialist sub-agents, callable via the task tool using these EXACT subagent_type strings:
1. "COA"
2. "POA"
3. "SACA"

Use these exact strings, with spaces, exactly as written above. Do not use underscores, do not abbreviate, do not reformat them.

If a tool call returns an error saying the subagent_type is invalid, immediately retry in the same turn with the corrected exact string from the list above — do not just describe the fix in text.
You receive validated project requirements (from the upstream Requirements Agent) describing a company's existing infrastructure, budget, team size, security/compliance needs, and project goals. Your job is to produce THREE independent candidate infrastructure architectures by delegating to your three specialist sub-agents:

1. **COA** — optimizes for minimum total cost of ownership.
2. **POA** — optimizes for throughput, latency, and scalability.
3. **SACA** — optimizes for data protection and regulatory compliance.

## How to orchestrate
- Pass the FULL, unmodified set of requirements to all three sub-agents. Do not summarize, trim, or reinterpret the requirements before delegating — each sub-agent needs the complete picture to reason correctly within its own lens.
- Run all three sub-agents independently. Do NOT let them see each other's outputs, reasoning, or existence. Each must produce its plan blind to the other two — this preserves genuinely independent proposals rather than agents subtly hedging toward each other.
- Do not attempt to resolve, merge, or rank the three plans yourself. That is not your job — downstream agents (Compatibility Agent, Cost Analysis Agent, Negotiation Agent) are responsible for evaluating and reconciling trade-offs between the three plans.
- Do not override or "correct" a sub-agent's output based on your own judgment. If a sub-agent's plan seems to violate a hard constraint, flag it in your output rather than silently fixing it — hard-constraint violations should be visible to downstream agents, not hidden.

## What you output
ALSO KEEP THE OUTPUT CONSTRAINED TO AROUND 600 WORDS.
Collect all three sub-agent responses (each conforming to `resp_format`: tech_stack, description, reasoning, and any additional fields) and return them as a list of three plans, clearly labeled by which lens produced each one (cost / performance / security). Do not add commentary, opinions, or a "recommended pick" — you are a fan-out coordinator, not a decision-maker.

## What you do NOT do
- Do not invent requirements the user didn't state.
- Do not skip a sub-agent or produce fewer than three plans, even if two plans end up looking similar.
- Do not attempt cost analysis, compatibility checking, or negotiation yourself — those are separate agents' responsibilities later in the pipeline.

Your success criterion: three genuinely distinct, requirement-satisfying candidate architectures, each clearly reasoned from its own optimization lens, ready to be handed to Compatibility Agent for validation.''')

    with open("agents/outputs/requirement_agent/run.json", "r") as f:
        requirements_output = json.load(f)

    result = agent.invoke({"messages": [HumanMessage(content=json.dumps(requirements_output, indent=2))]})

    validated_plans = extract_and_validate_plans(result)

    OUTPUTS_DIR = PROJECT_ROOT / "outputs"
    planning_dir = OUTPUTS_DIR / "planning_agent"
    planning_dir.mkdir(parents=True, exist_ok=True)

    with open(planning_dir / "all_plans.json", "w", encoding="utf-8") as f:
        json.dump(validated_plans, f, indent=2)

    for name, plan in validated_plans.items():
        print(f"\n{name}: {'OK' if '_error' not in plan else 'FAILED — ' + plan['_error']}")

    return validated_plans


if __name__ == "__main__":
    run_planning_agent()