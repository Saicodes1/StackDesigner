from langchain.agents import create_agent
from pydantic import BaseModel,Field

from deepagents.backends import FilesystemBackend
from deepagents.middleware import SkillsMiddleware
from typing import List, Optional
from langchain.messages import HumanMessage, AIMessage, SystemMessage
from langchain_ollama import ChatOllama
from pathlib import Path
from langgraph.graph import StateGraph
from states import Required_state
import json 

model=ChatOllama(model="qwen3:8b")

PROJECT_ROOT = Path(__file__).resolve().parent
backend = FilesystemBackend(
    root_dir=str(PROJECT_ROOT)
)

OUTPUTS_DIR = PROJECT_ROOT/ "outputs"

class RequirementsOutput(BaseModel):
    project_goal: str
    requirements_needed: List[str]
    current_tech_stack: List[str]
    cloud_provider: Optional[dict] = None
    budget: Optional[float] = Field(
        default=None,
        description=(
            "Total budget as a single plain number (e.g. 75000.0), NOT a nested "
            "object or breakdown. If multiple budget figures are mentioned, sum "
            "them into one number."
        ),
    )
    team_size: Optional[int] = None
    constraints: List[str]
    preferences: List[str]
    open_questions: List[str]
    summary: str

def requirements_analyzer(state:Required_state) -> Required_state:

    human_msg= state["messages"]

    system_message= SystemMessage('''
    You are the Requirements Analysis Agent in the InfraPilot multi-agent system.

    Your role is to understand user requirements and transform them into a structured technical requirements specification.

    Use the requirements analysis skill provided to you.

    Do not recommend technologies or architectures.
    Do not perform cost analysis.
    Do not perform security evaluation.

    Your output must follow the RequirementsOutput schema.''')

    agent=create_agent(model=model,
                    response_format=RequirementsOutput,
                    system_prompt=system_message
                    )
    print("invoked")        
    result=agent.invoke({"messages":human_msg})
    print("invoked")
    agent_dir = OUTPUTS_DIR/"requirement_agent"
    filepath= agent_dir/"run.json"
    with open(filepath, "w") as f:
        json.dump({
            "agent_name":"requirement_agent",
            "data":result["structured_response"].model_dump()
        },f,indent=2)
    state["requirements_output"]=result["structured_response"]
    return state