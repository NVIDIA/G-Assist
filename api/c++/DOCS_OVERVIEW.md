# Documentation Overview

The C++ API documentation is organized into three focused documents:

## [README.md](README.md)
**For: Users who want to run the demo**

Quick start guide for building and running the demo application.

**Contents:**
- What the demo shows
- Prerequisites and setup
- Build instructions (Visual Studio & command line)
- Running the application
- Feature demonstrations
- Troubleshooting guide
- Project structure

**Use when:** You want to compile and run the demo to see RISE in action.

---

## [INTEGRATION.md](INTEGRATION.md)
**For: Developers building applications with RISE**

Comprehensive guide for integrating RISE into your own C++ applications.

**Contents:**
- Architecture overview with diagrams
- Step-by-step integration process
- Request/response patterns
- Common integration scenarios (chatbot, voice commands, background AI)
- Thread safety and synchronization strategies
- Error handling best practices
- Performance optimization tips
- Testing strategies
- Example architectures (console, GUI, service)
- Reference to implementation code

**Use when:** You're ready to integrate RISE into your own application and need architectural guidance.

---

## [API_REFERENCE.md](API_REFERENCE.md)
**For: Developers who need detailed API specifications**

Complete technical reference for all RISE API functions and structures.

**Contents:**
- Core function signatures and usage
- Structure definitions and field descriptions
- Content type enumeration with values
- Request format specifications (LLM & ASR)
- Response format details
- Error codes and meanings
- Constants and limits
- Complete code examples

**Use when:** You need specific details about function parameters, return values, or data formats.

---

## Documentation Flow

```
New User Journey:
1. README.md        → Build and run the demo
2. INTEGRATION.md   → Understand architecture and patterns
3. API_REFERENCE.md → Look up specific function details
4. main.cpp         → See production implementation

Quick Reference Journey:
1. API_REFERENCE.md → Find function signature
2. INTEGRATION.md   → See usage pattern
3. main.cpp         → See real example
```

---

## Content Mapping

| Topic | README | INTEGRATION | API_REFERENCE |
|-------|--------|-------------|---------------|
| Building the demo | Yes | | |
| Running examples | Yes | | |
| Troubleshooting | Yes | | |
| Architecture diagrams | | Yes | |
| Integration patterns | | Yes | |
| Thread safety | | Yes | |
| Performance tips | | Yes | |
| Function signatures | | | Yes |
| Structure definitions | | | Yes |
| Error codes | | | Yes |
| Request formats | | Yes | Yes |
| Code examples | Yes | Yes | Yes |

---

## Quick Links

**I want to...**

- Build and run the demo → [README.md](README.md)
- Integrate RISE into my app → [INTEGRATION.md](INTEGRATION.md)
- Look up a function → [API_REFERENCE.md](API_REFERENCE.md)
- See example code → [main.cpp](main.cpp)
- Understand callbacks → [INTEGRATION.md#step-2-implement-callback-architecture](INTEGRATION.md#step-2-implement-callback-architecture)
- Send LLM requests → [API_REFERENCE.md#llm-request-format](API_REFERENCE.md#llm-request-format)
- Send ASR audio → [API_REFERENCE.md#asr-audio-chunk-format](API_REFERENCE.md#asr-audio-chunk-format)
- Handle errors → [INTEGRATION.md#error-handling](INTEGRATION.md#error-handling)
- Optimize performance → [INTEGRATION.md#performance-optimization](INTEGRATION.md#performance-optimization)

---

**Happy Coding!**

