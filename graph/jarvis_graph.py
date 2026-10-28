from langgraph.graph import StateGraph, START, END
from core.state import JarvisState
from graph.nodes import (
    memory_retrieval,
    policy_check,
    model_router,
    memory_update,
)

def build_jarvis_graph():
    graph = StateGraph(JarvisState)
    graph.add_node("memory_retrieval", memory_retrieval)
    graph.add_node("policy_check", policy_check)
    graph.add_node("model_router", model_router)
    graph.add_node("memory_update", memory_update)
    graph.add_edge(START, "memory_retrieval")
    graph.add_edge("memory_retrieval", "policy_check")
    graph.add_edge("policy_check", "model_router")
    graph.add_edge("model_router", "memory_update")
    graph.add_edge("memory_update", END)
    return graph.compile()

jarvis_graph = build_jarvis_graph()

__all__ = ["build_jarvis_graph", "jarvis_graph"]
