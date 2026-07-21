from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
import asyncio
import json
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
from typing import Optional

model = ChatOllama(
    model="minimax-m3:cloud"
)

class Cost(BaseModel):
    cost_agent_COA: int
    cost_agent_POA: int
    cost_agent_SACA: int


class PlanCostResult(BaseModel):
    total_monthly_cost_usd: int
    matched_services: list[str] = Field(default_factory=list)
    unmatched_services: list[str] = Field(default_factory=list)
    notes: Optional[str] = None

    @field_validator("matched_services", "unmatched_services", mode="before")
    @classmethod
    def coerce_service_list(cls, v):
        if isinstance(v, dict):
            for val in v.values():
                if isinstance(val, list):
                    return val
            return []
        if v is None:
            return []
        return v

    @field_validator("notes", mode="before")
    @classmethod
    def coerce_notes(cls, v):
        if v is None:
            return None

        if isinstance(v, dict):
            for val in v.values():
                if isinstance(val, str):
                    return val
                if isinstance(val, list):
                    return "\n".join(str(item) for item in val)
            return str(v)

        if isinstance(v, list):
            return "\n".join(str(item) for item in v)

        return str(v)
    
COST_ANALYSIS_SYSTEM_PROMPT = '''You are the Cost Analysis Agent for a single candidate infrastructure plan.

You have access to PostgreSQL database tools connected to a database containing two tables:
- cloud_services: real Azure service pricing (service_name, sku_name, category, unit, unit_price_usd)
- service_aliases: alternate/informal names mapped to cloud_services rows, supporting fuzzy text matching via pg_trgm similarity()

Your job, given a list of tech_stack strings from one architecture plan:
1. For each tech_stack entry, identify the core service name (ignore tier/SKU/quantity details when searching).
2. Query the database to find the best matching price — use a SQL query against service_aliases JOINed to cloud_services, ordering by similarity(alias, '<search text>') DESC, and take the top match only if its similarity score is reasonably high (treat scores below ~0.25 as no match).
3. If you find a match, use its unit_price_usd and unit to estimate a realistic monthly cost, using the requirements context (team size ~25 users, internal tool, moderate usage) to reason about usage volume (e.g., compute hours per month, tokens per month, GB stored).
4. If no match is found for a service, add it to unmatched_services and do NOT guess a price for it.
5. Sum all matched line items into a single total_monthly_cost_usd (integer, rounded).
6. Return matched_services (list of service names you successfully priced) and unmatched_services (list of raw tech_stack entries you could not match).
7. Do not use your own training-data knowledge of Azure pricing under any circumstances — every dollar figure in your final answer must trace back to a value returned by a database query. If you did not query it, do not price it.

Respond only in the structured format provided.'''


async def analyze_single_plan(client, tools, agent_name: str, tech_stack: list[str]) -> PlanCostResult:
    agent = create_agent(
        model=model,
        tools=tools,
        response_format=ToolStrategy(schema=PlanCostResult, handle_errors=False),
        system_prompt=SystemMessage(COST_ANALYSIS_SYSTEM_PROMPT),
    )

    human_content = json.dumps({
        "plan_name": agent_name,
        "tech_stack": tech_stack
    }, indent=2)

    result = await agent.ainvoke({"messages": [HumanMessage(content=human_content)]})
    return result["structured_response"]


async def cost_analysis_agent() -> Cost:
    client = MultiServerMCPClient({
        "postgres": {
            "transport": "stdio",
            "command": "uv",
            "args": [
                "run",
                "postgres-mcp",
                "--access-mode=unrestricted",
            ],
            "env": {
                "DATABASE_URI": "postgresql://db_user_name:db_password@localhost:5432/db",
            },
        }
    })
    tools = await client.get_tools()

    with open("agents/outputs/planning_agent/all_plans.json") as f:
        plans = json.load(f)

    results = {}
    for agent_name in ["COA", "POA", "SACA"]:
        tech_stack = plans[agent_name]["tech_stack"]
        print(f"Analyzing {agent_name}...")
        plan_result = await analyze_single_plan(client, tools, agent_name, tech_stack)
        results[agent_name] = plan_result
        print(f"{agent_name}: ${plan_result.total_monthly_cost_usd}/mo "
              f"({len(plan_result.matched_services)} matched, {len(plan_result.unmatched_services)} unmatched)")

    final_cost = Cost(
        cost_agent_COA=results["COA"].total_monthly_cost_usd,
        cost_agent_POA=results["POA"].total_monthly_cost_usd,
        cost_agent_SACA=results["SACA"].total_monthly_cost_usd,
    )

    output_dir = Path("agents/outputs/cost_analysis_agent")
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "final_cost.json", "w") as f:
        json.dump(final_cost.model_dump(), f, indent=2)

    with open(output_dir / "cost_analysis_detail.json", "w") as f:
        json.dump({name: r.model_dump() for name, r in results.items()}, f, indent=2)

    print("\nFinal cost summary:", final_cost.model_dump())
    return final_cost


if __name__ == "__main__":
    asyncio.run(cost_analysis_agent())