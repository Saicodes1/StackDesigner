from langchain_ollama import ChatOllama
from langchain_mcp_adapters.client import MultiServerMCPClient  
from langchain.agents import create_agent
import asyncio
from langchain.messages import HumanMessage, SystemMessage
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional
from langchain.agents.structured_output import ToolStrategy
import json
model = ChatOllama(
    model="minimax-m3:cloud"
)
class ExtractedService(BaseModel):
    raw_text: str = Field(description="The original tech_stack entry, completely unmodified")
    service_name: str = Field(description="Just the core service name, e.g. 'Azure Database for PostgreSQL Flexible Server'")
    tier_or_sku: Optional[str] = Field(default=None, description="Tier/SKU if mentioned, e.g. 'Burstable B1ms'")
    quantity_hint: Optional[str] = Field(default=None, description="Any quantity/scale hint present in the text, e.g. '2-3 apps', '15 GiB partition'")

class ServiceExtractionOutput(BaseModel):
    agent_name: str = Field(description="Which lens plan this extraction belongs to, e.g. 'COA', 'POA', 'SACA'")
    services: list[ExtractedService]

EXTRACTION_SYSTEM_PROMPT = '''You are the Service Extraction Agent in the InfraPilot cost-analysis pipeline.

Your job: given a raw list of tech_stack strings from a candidate infrastructure plan, decompose EACH entry into a normalized, structured record — nothing else. You do not estimate costs, you do not look anything up, you do not judge whether a service is a good choice. You only extract and normalize.

For each tech_stack entry, produce:
1. raw_text — the original string, completely unmodified, exactly as given.
2. service_name — ONLY the core product/service name (e.g. "Azure Kubernetes Service", "Azure Database for PostgreSQL Flexible Server", "Azure OpenAI Service"). Strip out tier names, SKU details, parenthetical notes, and usage descriptions — those go in separate fields below.
3. tier_or_sku — if the entry mentions a specific tier, SKU, or pricing plan (e.g. "Burstable B1ms", "Standard S1", "Consumption plan", "Premium P2"), extract it here. Leave null if none is mentioned.
4. quantity_hint — if the entry mentions a scale/quantity detail (e.g. "2-3 apps", "15 GiB partition", "8 vCore"), extract it here verbatim. Leave null if none is mentioned.

Rules:
- One tech_stack entry produces exactly one output record, even if it mentions multiple things — capture the PRIMARY service only; if an entry genuinely describes two distinct billable services (e.g. "GitHub Actions (existing, 2k free min/mo for private)" mixing a CI tool with a free-tier note), still treat it as one record about the primary named service.
- Do not invent details not present in the original text. If a field isn't mentioned, leave it null — do not guess.
- Do not skip any entries. If given 12 tech_stack items, return exactly 12 extracted service records.
- Do not merge, deduplicate, or reorder entries — preserve one-to-one correspondence with the input list, in the same order.
- Do not attempt to normalize toward "official" Azure product names if the text is ambiguous — extract what is actually written, even if informal (e.g. "AKS" stays "AKS" in service_name, do not expand it to "Azure Kubernetes Service" unless that's what was written).
'''

def extract_services_for_plan(model, agent_name: str, tech_stack: list[str]) -> ServiceExtractionOutput:
    agent = create_agent(
        model=model,
        response_format=ToolStrategy(schema=ServiceExtractionOutput, handle_errors=False),
        system_prompt=SystemMessage(EXTRACTION_SYSTEM_PROMPT),
    )
    human_content = json.dumps({"agent_name": agent_name, "tech_stack": tech_stack}, indent=2)
    result = agent.invoke({"messages": [HumanMessage(content=human_content)]})
    return result["structured_response"]

def extracting_services():
    model_for_extraction = ChatOllama(
    model="minimax-m3:cloud"
)

    with open("agents/outputs/planning_agent/all_plans.json") as f:
        data = json.load(f)

    all_extractions = {}
    for agent_name, plan in data.items():
        tech_stack = plan["tech_stack"]
        extracted = extract_services_for_plan(model_for_extraction, agent_name, tech_stack)
        all_extractions[agent_name] = extracted.model_dump()
        print(f"{agent_name}: extracted {len(extracted.services)} services from {len(tech_stack)} tech_stack entries")

    output_dir = Path("agents/outputs/extracing_services_agent")
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "extracted_services.json", "w") as f:
        json.dump(all_extractions, f, indent=2)

    return all_extractions

if __name__ == "__main__":
    extracting_services()
    
