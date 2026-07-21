import asyncio
import json
from pathlib import Path

import streamlit as st
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict
from langchain.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from agents import requirement_agent
from agents import planning_agent         
from agents import cost_analysis_agent     
from agents import recommendation_agent     

from states import Required_state


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUTS_DIR = PROJECT_ROOT / "agents" / "outputs"
print(PROJECT_ROOT)

def planning_node(state: Required_state) -> Required_state:
    planning_agent.run_planning_agent()   
    return state


def cost_node(state: Required_state) -> Required_state:
    asyncio.run(cost_analysis_agent.cost_analysis_agent())  
    return state


def recommendation_node(state: Required_state) -> Required_state:
    recommendation_agent.recommendation_agent()  
    return state


def build_graph():
    graph = StateGraph(state_schema=Required_state)
    graph.add_node("req_agent", requirement_agent.requirements_analyzer)
    graph.add_node("planning_agent", planning_node)
    graph.add_node("cost_agent", cost_node)
    graph.add_node("recommendation_agent", recommendation_node)

    graph.add_edge(START, "req_agent")
    graph.add_edge("req_agent", "planning_agent")
    graph.add_edge("planning_agent", "cost_agent")
    graph.add_edge("cost_agent", "recommendation_agent")
    graph.add_edge("recommendation_agent", END)

    return graph.compile()


def run_pipeline(user_text: str):
    app = build_graph()
    human_msg = HumanMessage(content=user_text)
    result = app.invoke({"messages": human_msg})
    return result



def generate_summary(recommendation: dict, plans: dict, costs: dict) -> str:
    model = ChatOllama(model="qwen3:8b")
    system_prompt = SystemMessage(
        "You are summarizing the final output of an infrastructure recommendation pipeline. "
        "Given the recommended plan(THE FULL STACK), all plan pros/cons, and costs, write a short, plain-text "
        "summary (5-8 sentences) explaining what was recommended and why, in a way a "
        "non-technical stakeholder could understand. No markdown, no headers."
    )
    human_content = json.dumps({
        "recommendation": recommendation,
        "plans": plans,
        "costs": costs
    }, indent=2)
    result = model.invoke([system_prompt, HumanMessage(content=human_content)])
    return result.content



def main():
    st.set_page_config(page_title="StackDesigner", layout="centered")
    st.title("StackDesigner: The one and only Tech Stack Recommender")

    user_input = st.text_area(
        "Describe your project requirements",
        height=250,
        placeholder="e.g. We are a mid-sized company planning to build..."
    )

    if st.button("Run Pipeline"):
        if not user_input.strip():
            st.warning("Please enter your project requirements first.")
            return

        with st.spinner("Running the pipeline — this may take a few minutes..."):
            run_pipeline(user_input)

            with open(OUTPUTS_DIR / "planning_agent" / "all_plans.json") as f:
                plans = json.load(f)
            with open(OUTPUTS_DIR/ "cost_analysis_agent" / "final_cost.json") as f:
                costs = json.load(f)
            with open(OUTPUTS_DIR / "recommendation_agent" / "recommendation.json") as f:
                recommendation = json.load(f)

            summary_text = generate_summary(recommendation, plans, costs)

        st.session_state["plans"] = plans
        st.session_state["costs"] = costs
        st.session_state["recommendation"] = recommendation
        st.session_state["summary_text"] = summary_text

    if "recommendation" in st.session_state:
        recommendation = st.session_state["recommendation"]
        plans = st.session_state["plans"]
        costs = st.session_state["costs"]
        summary_text = st.session_state["summary_text"]

        recommended_name = recommendation["recommended_plan"]
        recommended_plan = plans[recommended_name]
        recommended_cost_map = {
            "COA": costs.get("cost_agent_COA"),
            "POA": costs.get("cost_agent_POA"),
            "SACA": costs.get("cost_agent_SACA"),
        }
        recommended_cost = recommended_cost_map.get(recommended_name)

        st.header(f"Recommended: {recommended_name}")
        st.subheader(f"Estimated cost: ${recommended_cost:,}/month")

        st.subheader("Recommended Tech Stack")
        tech_stack = recommended_plan["tech_stack"]
        for item in tech_stack:
            st.write(f"- {item}")

        tech_stack_text = "\n".join(tech_stack)
        st.download_button(
            label="Download Tech Stack",
            data=tech_stack_text,
            file_name=f"{recommended_name}_tech_stack.txt",
            mime="text/plain",
        )

        st.subheader("Summary")
        st.write(summary_text)


if __name__ == "__main__":
    main()