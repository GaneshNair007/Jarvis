# JARVIS: Personal AI Operating System

> **Personal AI Operating System**  
> *A screen-first, voice-driven, always-available multi-agent assistant for real computer work.*

---

## ⚡ Key Highlights
- **Three-Tier Hybrid Model Router**:
  - **BYPASS**: Deterministic Instant OS Commands (0 tokens, ~1ms).
  - **Tier 1 (Local Reflex)**: Ollama (`llama3.2:3b`), local OCR, zero external data leakage.
  - **Tier 2 (Private GPU Reasoning)**: vLLM OpenAI-compatible server for deep reasoning within the private boundary.
  - **Tier 3 (Frontier Cloud)**: Claude 3.7 / GPT-4o / Gemini 2.0 Pro for complex public research and advanced refactoring.
- **Deterministic Policy Gate**: Deny-by-default access control with HMAC-SHA256 human approval tokens.
- **Data Loss Prevention (DLP)**: Automatic secret and PII redaction pipeline.
- **Cost Governor**: Strict per-task ($0.50), daily ($5.00), and monthly budget caps with circuit breakers.
- **Cryptographic Audit Ledger**: Tamper-evident SHA-256 chained audit trail.
- **355 Powers Catalog**: Built-in registry spanning 20 functional domains.
- **5-Layer Persistent Memory**: SQLite WAL storage with cognitive layers (Raw, Semantic, Episodic, Working, Directive).

---

## 🚀 Quick Start

### 1. Installation
```bash
git clone https://github.com/GaneshNair007/Jarvis.git
cd jarvis
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your personal keys and preferences
```

### 3. Run the Server
```bash
python -m jarvis.main serve
```
The FastAPI and WebSocket server will start on **http://127.0.0.1:8000**.

### 4. CLI Commands
```bash
# Check host performance telemetry
python -m jarvis.main health

# Send an instant command or chat query
python -m jarvis.main chat "System health"
python -m jarvis.main chat "Open VS Code"
python -m jarvis.main chat "Research latest PyTorch releases"

# Verify audit trail integrity
python -m jarvis.main audit

# Inspect power catalog summary
python -m jarvis.main powers
```

### 5. Running Tests
```bash
pytest
```
