# JARVIS MASTER IMPLEMENTATION DIRECTIVE

## Vision: Personal AI Operating System for Ganesh Nair

## MISSION

JARVIS is not a chatbot.

JARVIS is not a collection of repositories.

JARVIS is not a dashboard.

JARVIS is a personal AI operating system whose sole mission is:

**"Maximize Ganesh's growth, opportunities, learning, productivity, engineering output, research capability, and long-term career trajectory."**

Every component, repository, agent, service, route, workflow, and future feature must contribute to that mission.

Anything that does not contribute should be removed.

---

## THE FIRST LAW OF JARVIS

### NO EVIDENCE = NO CLAIM

JARVIS MUST NEVER CLAIM:

- An email was read
- A website was searched
- A repository was created
- A job was applied for
- A form was submitted
- A task was completed
- A project was built
- A model was queried

unless verifiable evidence exists.

Every external action must produce:

**TrustResult + Evidence object(s)**

or

**an honest failure.**

Forbidden:

"Task completed"

without proof.

"Found opportunities"

without proof.

"Application submitted"

without proof.

All future development must obey this law.

---

## CURRENT VERIFIED ARCHITECTURE

### CONFIRMED ACTIVE

- Task Graph Engine
- Goal Execution
- Task Executor
- Reflection Engine
- Orchestrator
- Model Router
- Scheduler Infrastructure
- Policy Gate
- Approval System
- WebSocket HUD
- Evidence System
- Trust Layer

### CONFIRMED PARTIAL

- Voice System
- Capability Registry
- Memory
- Opportunity Engine

### CONFIRMED MISSING OR INCOMPLETE

- Real Gmail OAuth
- Production Whisper STT
- Real Wake Word Detection
- Complete Capability Enforcement
- 100% Trust Coverage

---

## OFFICIAL JARVIS SYSTEM ARCHITECTURE

```
                    USER

          Phone / Voice / Desktop

                         │

                         ▼

                 JARVIS CORE

              Architect Agent

                         │

                         ▼

                 Task Graph Engine

               Goal → DAG → Tasks

                         │

       ┌─────────────────┼─────────────────┐

       ▼                 ▼                 ▼

 Career Dept      Research Dept     Development Dept

       ▼                 ▼                 ▼

 Opportunity      Web Research      Antigravity
 Discovery        OpenClaw          OpenHands

                         │

                         ▼

                  Execution Layer

       MCP
       Power Registry
       Browser Service
       GitHub Service
       Memory Service

                         │

                         ▼

                  Evidence Layer

                 TrustResult

                         │

                         ▼

                 Reflection Engine

                         │

                         ▼

               Capability Registry

                         │

                         ▼

               Improvement Requests

                         │

                         ▼

                    Human Review
```

---

## SPRINT 1 STATUS

### COMPLETED

- Gmail hallucination removed
- TrustResult implemented
- Evidence objects implemented
- First Law compliance tests
- Sleeping agent removed
- Approval token leakage fixed
- Authenticated approvals
- Replay protection
- Scheduler verification
- Opportunity pipeline tests

---

## SPRINT 1.5 STATUS

### COMPLETED

- Fake success paths eliminated
- Task executor executes real tools
- Power Registry dispatch
- Evidence verification
- Security hardening
- Trust compliance CI

Branch: `sprint1.5/eliminate-fake-success`

---

## SPRINT 2: RUNTIME & VOICE RELIABILITY

### GOAL

Make JARVIS feel alive.

Highest Priority.

### P0 — VOICE OPERATING SYSTEM

**Current State:**

- TTS: REAL
- Wake Word: STUB
- Microphone: DEAD
- STT: MOCK
- Barge-In: SCAFFOLDED

**Required Result:**

```
Speak: "Hey Jarvis"
   ↓
 Wake Event
   ↓
 Speech Capture
   ↓
 STT
   ↓
 Task Graph
   ↓
 Response
   ↓
 TTS
```

Implemented end-to-end.

### P0 — MICROPHONE PIPELINE

Implement: `sounddevice` or `PyAudio`

Requirements:

- Open microphone automatically
- Continuously stream audio
- Health check endpoint
- Evidence logs

### P0 — STT

Install: `faster-whisper`

Requirements:

- Local transcription
- GPU acceleration
- Evidence output
- Confidence scores
- Health checks

### P0 — WAKE WORD

Install: `OpenWakeWord` or `Porcupine`

Requirements:

- Wake phrases: "Hey Jarvis", "Jarvis"
- Events stored to evidence logs.

### P0 — CONCURRENCY FIXES

Remove blocking inference.

Replace sync calls in async routes with `asyncio.to_thread()` or native async clients.

Requirements:

- No event-loop starvation.
- HUD remains responsive.
- Voice remains responsive.

---

## SPRINT 3: ALWAYS-ON JARVIS

### GOAL

No localhost. No browser. No manual startup.

### REQUIREMENTS

Create: Windows Service or Scheduled Startup

- Auto-start login
- Headless mode
- Background daemon
- Automatic recovery
- Health heartbeat

### Required User Experience

```
Boot laptop
   ↓
 JARVIS starts automatically
   ↓
 "Hey Jarvis"
   ↓
 Instant response
```

---

## SPRINT 4: PHONE ↔ LAPTOP RELAY

### GOAL

Cross-device continuity.

### Architecture

```
Phone
   ↓
Relay Queue
   ↓
Laptop Worker
   ↓
Task Execution
   ↓
Response sent back
```

### Requirements

- WhatsApp
- Switch Protocol
- Task Queue
- Delivery receipts
- Retry system
- Evidence system

### IMPORTANT

Laptop OFF does not mean task executes.

Laptop OFF means: Task queued.

Laptop ON means: Task executed.

No fake claims.

---

## SPRINT 5: REAL CONNECTORS

Implement:

- Gmail OAuth
- GitHub OAuth
- LinkedIn Connector
- Calendar Connector
- WhatsApp Connector

### Rules

Disconnected Connector → Honest refusal. Not hallucination.

All outputs require evidence.

---

## SPRINT 6: SELF IMPROVEMENT

### Goal

Controlled evolution.

```
Reflection
   ↓
Capability Gaps
   ↓
Improvement Requests
   ↓
Antigravity Pull Request
   ↓
Tests
   ↓
Security Review
   ↓
Human Approval
   ↓
Merge
```

### FORBIDDEN

```
Reflection → Push Main
```

No direct self-modification.

---

## CAPABILITY REGISTRY

Every capability must have:

- Capability Name
- Provider
- Health
- Evidence
- Maturity Level

Levels: MISSING, EXPERIMENTAL, BASIC, ADVANCED, ELITE

### Example

```
gmail_scan: MISSING
voice_input: EXPERIMENTAL
tts: ADVANCED
task_graph: ELITE
```

---

## TRUST COVERAGE METRIC

Primary success metric.

NOT: tests passed
NOT: routes created
NOT: agents added
NOT: repositories integrated

Track: **Trust Coverage %**

Example:

- Task Executor: 100%
- Policy Gate: 100%
- Scheduler: 95%
- Voice: 50%
- Research: 70%

Goal: **100% Trust Coverage**

---

## REPOSITORY ROLE MAP

```
Jarvis         = Operating System
OpenMausBot    = Agent Interaction Layer
OpenClaw/Obscura = Web Perception Layer
Switch         = Cross-Agent Communication Layer
Antigravity    = Development Workforce
OpenHands      = Engineering Workforce
MCP            = Tool Bus
Postgres       = Operational Memory
Vector DB      = Semantic Memory
Neo4j          = Knowledge Graph
```

---

## FINAL SUCCESS CRITERIA

JARVIS succeeds when:

Ganesh can say:

**"Hey Jarvis, find the best AI opportunity today."**

and JARVIS can:

```
Wake
Listen
Transcribe
Research
Evaluate
Explain findings
Provide evidence
Request approval if needed
Act
Report results
```

without opening localhost

without manual intervention

without hallucinating

without fake success

while obeying:

**NO EVIDENCE = NO CLAIM**

---

This document is the prompt pinned as the constitution for JARVIS development. Every future sprint, agent, repository, and pull request must conform to it.
