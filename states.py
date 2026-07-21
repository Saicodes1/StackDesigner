from typing import TypedDict
from langchain.messages import HumanMessage

class Required_state(TypedDict):
    requirements_output:dict
    messages:HumanMessage