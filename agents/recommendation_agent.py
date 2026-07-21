from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field
import json
from pathlib import Path

model = ChatOllama(model="qwen3:8b", keep_alive="30m")


class PlanSummary(BaseModel):
    plan_name: str = Field(description="COA, POA, or SACA")
    estimated_monthly_cost_usd: int
    pros: list[str] = Field(description="Short bullet points on the strengths of this plan")
    cons: list[str] = Field(description="Short bullet points on the weaknesses/trade-offs of this plan")


class RecommendationOutput(BaseModel):
    plan_summaries: list[PlanSummary] = Field(description="Pros, cons, and cost for all three plans (COA, POA, SACA)")
    recommended_plan: str = Field(description="The name of the single recommended plan: COA, POA, or SACA")
    recommendation_reasoning: str = Field(description="A few sentences explaining why this plan best fits what the user asked for/prioritized")


RECOMMENDATION_SYSTEM_PROMPT = '''You are the Recommendation Agent in the InfraPilot system.

You will be given:
1. The user's original project requirements/request.
2. Three candidate architecture plans (COA - cost-optimized, POA - performance-optimized, SACA - security/compliance-optimized), each with a tech stack, description, and reasoning.
3. The estimated monthly cost for each of the three plans.

Your job:
- Write a short pros and cons list for each of the three plans.
- Include each plan's estimated cost.
- Based on what the user actually asked for/prioritized in their original request, recommend the single most suitable plan and explain why.

Do not invent details not present in the plans provided. Respond only in the structured format provided.'''


def recommendation_agent():
    with open("agents/outputs/requirement_agent/run.json") as f:
        requirements = json.load(f)["data"]

    with open("agents/outputs/planning_agent/all_plans.json") as f:
        plans = json.load(f)

    with open("agents/outputs/cost_analysis_agent/final_cost.json") as f:
        costs = json.load(f)

    human_content = json.dumps({
        "user_requirements": requirements,
        "plans": plans,
        "estimated_monthly_costs": costs
    }, indent=2)

    agent = create_agent(
        model=model,
        response_format=ToolStrategy(schema=RecommendationOutput, handle_errors=False),
        system_prompt=SystemMessage(RECOMMENDATION_SYSTEM_PROMPT),
    )

    result = agent.invoke({"messages": [HumanMessage(content=human_content)]})
    output = result["structured_response"]

    output_dir = Path("agents/outputs/recommendation_agent")
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "recommendation.json", "w", encoding="utf-8") as f:
        json.dump(output.model_dump(), f, indent=2)

    print(json.dumps(output.model_dump(), indent=2))
    return output


if __name__ == "__main__":
    recommendation_agent()