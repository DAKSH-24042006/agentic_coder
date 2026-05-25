import logging
from typing import TypedDict, List, Dict, Any, Optional, AsyncGenerator
from app.services.peft_inference import peft_inference
from app.services.rag_service import rag_service
from app.services.context_engine import context_engine
from app.services.sandbox_service import sandbox_service

logger = logging.getLogger(__name__)

# 1. State Definition
class AgentState(TypedDict):
    query: str
    workspace_context: Optional[Dict[str, Any]]
    project_filter: Optional[str]
    use_peft: bool
    plan: str
    retrieved_code: List[Dict[str, Any]]
    generated_code: str
    review_feedback: str
    sandbox_results: Optional[Dict[str, Any]]
    iterations: int
    max_iterations: int
    stream_output: List[str]

# 2. Node Implementations
async def planner_agent(state: AgentState) -> Dict[str, Any]:
    logger.info("Starting Planner Agent...")
    system_prompt = (
        "You are an enterprise AI system Planner. Your job is to analyze the user coding task, "
        "identify the necessary files, libraries, patterns, and style specifications required. "
        "Create a step-by-step implementation plan. Do not write full code, focus on architecture and plan."
    )
    
    user_prompt = f"User Request: {state['query']}\nWorkspace context metadata: {state['workspace_context']}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    plan = await peft_inference.generate(messages, use_peft=state["use_peft"])
    return {"plan": plan, "iterations": state["iterations"] + 1}

async def retrieval_agent(state: AgentState) -> Dict[str, Any]:
    logger.info("Starting Retrieval Agent...")
    query = state["query"]
    project_filter = state["project_filter"]
    
    # RAG search across Qdrant
    retrieved_snippets = rag_service.hybrid_search(
        query=query,
        top_k=4,
        project_filter=project_filter,
        workspace_context=state["workspace_context"]
    )
    
    logger.info(f"Retrieved {len(retrieved_snippets)} matches from company projects repository.")
    return {"retrieved_code": retrieved_snippets}

async def coding_agent(state: AgentState) -> Dict[str, Any]:
    logger.info("Starting Coding Agent...")
    
    # Build RAG knowledge base string
    rag_context = ""
    for idx, snippet in enumerate(state["retrieved_code"]):
        rag_context += (
            f"\n--- Snippet {idx+1} (Project: {snippet['project_name']}, File: {snippet['filepath']}) ---\n"
            f"{snippet['code_content']}\n"
        )
        
    system_prompt = (
        "You are the Enterprise Coding Agent. Write production-grade code that resolves the task.\n"
        "Crucially, align your work with the organizational standards, styling patterns, and helper patterns "
        "illustrated in the historical snippets below. Do not use generic placeholders."
    )
    
    user_prompt = (
        f"Task plan: {state['plan']}\n"
        f"Historical Project Context:\n{rag_context}\n"
        f"Feedback from previous run (if any): {state['review_feedback']}\n"
        f"Sandbox Test outcomes: {state['sandbox_results']}\n"
        "Generate the complete solution now."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    generated_code = await peft_inference.generate(messages, use_peft=state["use_peft"])
    return {"generated_code": generated_code}

async def reviewer_agent(state: AgentState) -> Dict[str, Any]:
    logger.info("Starting Reviewer Agent...")
    
    system_prompt = (
        "You are an enterprise Code Reviewer. Analyze the generated code for security issues, "
        "syntax errors, strict pattern compliance, and potential bugs. "
        "Respond with 'PASSED' if the code is flawless. Otherwise, detail the problems clearly."
    )
    
    user_prompt = f"Generated Code:\n{state['generated_code']}\nPlan context: {state['plan']}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    review_feedback = await peft_inference.generate(messages, use_peft=False)
    return {"review_feedback": review_feedback}

async def tool_execution_agent(state: AgentState) -> Dict[str, Any]:
    logger.info("Starting Tool Execution Agent...")
    # Extract code and attempt sandboxed unit test checks if possible
    # We will simulate a quick syntax/pytest run on the output
    code = state["generated_code"]
    
    # Save the file payload
    files = {"generated_solution.py": code}
    command = "python -m py_compile generated_solution.py"
    
    exit_code, stdout, stderr, duration = sandbox_service.run_in_sandbox(command, files)
    
    results = {
        "command": command,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "duration": duration
    }
    
    return {"sandbox_results": results}

# 3. LangGraph Orchestrator Flow
class LangGraphOrchestrator:
    def __init__(self):
        self.nodes = {
            "planner": planner_agent,
            "retrieval": retrieval_agent,
            "coding": coding_agent,
            "reviewer": reviewer_agent,
            "tool_execution": tool_execution_agent
        }

    async def execute(
        self,
        query: str,
        workspace_context: Optional[Dict[str, Any]] = None,
        project_filter: Optional[str] = None,
        use_peft: bool = True
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Executes the agent nodes in a structured sequence, mimicking LangGraph state transitions,
        and yielding state outputs sequentially for telemetry and client-side visualization.
        """
        # Initialize State
        state: AgentState = {
            "query": query,
            "workspace_context": workspace_context,
            "project_filter": project_filter,
            "use_peft": use_peft,
            "plan": "",
            "retrieved_code": [],
            "generated_code": "",
            "review_feedback": "",
            "sandbox_results": None,
            "iterations": 0,
            "max_iterations": 3,
            "stream_output": []
        }

        # Step 1: Planning
        state.update(await self.nodes["planner"](state))
        yield {"node": "planner", "data": state["plan"]}

        # Step 2: Retrieval
        state.update(await self.nodes["retrieval"](state))
        yield {"node": "retrieval", "data": [
            {"file": s["filepath"], "project": s["project_name"]} for s in state["retrieved_code"]
        ]}

        # Step 3: Coding Loop (Loops if code fails sandbox compile or review)
        while state["iterations"] <= state["max_iterations"]:
            # Code synthesis
            state.update(await self.nodes["coding"](state))
            yield {"node": "coding", "data": state["generated_code"]}

            # Sandbox verification (Tool Execution)
            state.update(await self.nodes["tool_execution"](state))
            yield {"node": "tool_execution", "data": state["sandbox_results"]}

            # Architectural Review
            state.update(await self.nodes["reviewer"](state))
            yield {"node": "reviewer", "data": state["review_feedback"]}

            # Check termination condition
            if "PASSED" in state["review_feedback"].upper() or state["sandbox_results"]["exit_code"] == 0:
                logger.info("Code passed verification. Orchestration successful.")
                break
                
            state["iterations"] += 1
            logger.warning(f"Re-entering coding loop. Iteration {state['iterations']}")

        # Yield final completed output details
        yield {
            "node": "final_output",
            "data": {
                "code": state["generated_code"],
                "sources": state["retrieved_code"],
                "sandbox": state["sandbox_results"]
            }
        }

agent_orchestrator = LangGraphOrchestrator()
