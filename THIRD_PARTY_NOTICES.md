# Third-Party Notices and Licenses

Project JARVIS incorporates or adapts architectural patterns and libraries from the following third-party open-source projects. All adapted components comply with the MIT, Apache-2.0, or 3-Clause BSD licenses.

---

### 1. LangGraph
- **Repository**: `https://github.com/langchain-ai/langgraph`
- **License**: MIT License
- **Copyright**: (c) 2024 LangChain, Inc.
- **Usage**: Core workflow orchestration, state machine checkpoints, conditional edges, and human-in-the-loop interruption.

### 2. Mem0
- **Repository**: `https://github.com/mem0ai/mem0`
- **License**: Apache License, Version 2.0
- **Copyright**: (c) 2024 Mem0, Inc.
- **Usage**: Memory layer extraction and vector search adapter. Wrapped behind `BrainMemoryService` for zero-credential DLP redaction.

### 3. LiteLLM
- **Repository**: `https://github.com/BerriAI/litellm`
- **License**: MIT License
- **Copyright**: (c) 2023 BerriAI
- **Usage**: Model gateway routing, fallbacks, cost governance, and token estimation.

### 4. ActionWeaver
- **Repository**: `https://github.com/TengHu/ActionWeaver`
- **License**: Apache License, Version 2.0
- **Copyright**: (c) 2023 Teng Hu
- **Usage**: Adapted declarative `@action` decorator pattern and type-inferred JSON schema generation in `jarvis/core/action_decorator.py`.

### 5. LLM-Search
- **Repository**: `https://github.com/snexus/llm-search`
- **License**: Apache License, Version 2.0
- **Copyright**: (c) 2023 snexus
- **Usage**: Adapted Reciprocal Rank Fusion (RRF) and hybrid reranking patterns in `jarvis/search/hybrid_reranker.py`.

### 6. GPT Assistants API UI
- **Repository**: `https://github.com/ryo-ma/gpt-assistants-api-ui`
- **License**: MIT License
- **Copyright**: (c) 2024 Ryo-ma
- **Usage**: Adapted OpenAI Assistants API drop-in compatibility route in `jarvis/api/routes_assistants.py`.

### 7. Chainlit
- **Repository**: `https://github.com/Chainlit/chainlit`
- **License**: Apache License, Version 2.0
- **Copyright**: (c) 2023 Chainlit
- **Usage**: Adapted hierarchical step telemetry and execution progress tracking in `jarvis/core/step_telemetry.py`.

### 8. OpenClaw
- **Repository**: `https://github.com/openclaw/openclaw`
- **License**: MIT License
- **Copyright**: (c) 2024 OpenClaw Contributors
- **Usage**: Architectural reference for `SKILL.md` skill packaging and channel gateway patterns.

### 9. Hermes Agent
- **Repository**: `https://github.com/hermes-agent/hermes-agent`
- **License**: MIT License
- **Copyright**: (c) 2024 Hermes Agent Contributors
- **Usage**: Architectural reference for self-written skill lifecycles and command allow-listing patterns.

