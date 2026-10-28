# JARVIS Three-Tier Policy-Aware Model Router

## Routing Topology
```text
                 User: Voice / Text / Dashboard / Phone
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │     JARVIS ORCHESTRATOR   │
                    │ Intent → Memory → Plan    │
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │   POLICY + PRIVACY GATE   │
                    │ Sensitivity, risk, cost,  │
                    │ approval, redaction       │
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │       MODEL ROUTER        │
                    └─────────────┬─────────────┘
                     /            │            \
                    ▼             ▼             ▼
          ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
          │ TIER 1: LOCAL │ │ TIER 2: PRIVATE│ │ TIER 3:      │
          │ Reflex / SLM  │ │ GPU / vLLM     │ │ FRONTIER API │
          ├───────────────┤ ├───────────────┤ ├───────────────┤
          │ Ollama        │ │ vLLM server    │ │ Claude/GPT/   │
          │ Small models  │ │ Larger models  │ │ Gemini        │
          └───────────────┘ └───────────────┘ └───────────────┘
```

## Inference Tiers

### 1. BYPASS: Deterministic Instant OS Commands
- **Use Case**: Application launching, workstation locking, volume/display controls, telemetry retrieval.
- **Overhead**: Zero LLM tokens, ~1-5ms response time.

### 2. Tier 1: Local Reflex (Ollama / SLM)
- **Use Case**: Simple chat, classification, memory retrieval, routine summaries, private document Q&A, screen OCR/vision.
- **Runtimes**: Ollama (`llama3.2:3b`), faster-whisper, Piper TTS.
- **Cost**: $0.00. 100% data remains on local host.

### 3. Tier 2: Private GPU Reasoning (vLLM)
- **Use Case**: Multi-step planning, private codebase analysis, multi-agent coordination, private server diagnostics.
- **Runtimes**: vLLM OpenAI-compatible server on home GPU / private LAN.
- **Throughput**: High-concurrency continuous batching.

### 4. Tier 3: Frontier Cloud Gateway
- **Use Case**: Complex multi-hop public research, advanced refactors, high-difficulty reasoning.
- **Providers**: Claude 3.7 Sonnet, GPT-4o, Gemini 2.0 Pro.
- **Prerequisites**: Must pass Privacy Gate redaction + Cost Governor budget checks.

## Explicit Routing Rules
| Task Intent | Target Route | Justification |
|---|---|---|
| "Open VS Code", "Lock screen" | BYPASS | Purely deterministic system control |
| "What's on my screen?", "Summarize private PDF" | Tier 1 Local | Sensitive screen/file context cannot leave host |
| "Debug private repository", "Multi-agent planning" | Tier 2 Private | High reasoning required while keeping code private |
| "Research best local AI stack with citations" | Tier 3 Cloud | Public web research benefits from frontier models |
| "Send email to client", "Delete build artifacts" | Policy Gate First | Sensitive action requires cryptographic approval token |
