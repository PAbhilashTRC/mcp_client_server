# MCP Client

A configuration-driven **Model Context Protocol (MCP) Client** built with **FastAPI** that enables Large Language Models (LLMs) to discover and invoke tools hosted by one or more MCP servers.

The client reads server definitions from an MCP configuration file, establishes connections using supported transports, discovers available tools, and exposes REST APIs for interacting with the connected MCP ecosystem.

The application supports both local and remote MCP servers while providing a unified interface for tool discovery and execution.

---

# Why This Project Exists

Modern LLM applications often require access to external tools such as Gmail, Outlook, databases, GIS services, or custom enterprise applications.

Instead of implementing separate integrations for every tool, this project uses the **Model Context Protocol (MCP)** as a standard interface between the LLM and external services.

The client is responsible for:

1. Reading MCP server configurations.
2. Connecting to one or more MCP servers.
3. Discovering available tools.
4. Executing tool requests.
5. Returning responses through REST APIs.

---

# Main Flow

```text
                FastAPI Server
                      │
                      ▼
                 MCP Client
                      │
          Read MCP Configuration
                      │
                      ▼
         Connect to MCP Server(s)
                      │
          Discover Available Tools
                      │
                      ▼
        User Request to REST API (/user_query)
                      |
                      ▼
          LLM Selects Required Tool
                      │
                      ▼
             Execute MCP Tool
                      │
                      ▼
           Tool Response Returned
                      │
                      ▼
               API Response
```

---

# Features

* Configuration-driven MCP server connections
* Supports multiple MCP servers
* Automatic tool discovery
* Tool invocation through MCP
* Supports STDIO transport
* Supports Streamable HTTP transport
* Built using FastAPI
* Easy integration with LLM-based applications

---

# Architecture

```
                  +----------------+
                  |     Client     |
                  +--------+-------+
                           |
                           |
                 REST API (FastAPI)
                           |
                           ▼
                  +----------------+
                  |   MCP Client    |
                  +--------+-------+
                           |
          +----------------+----------------+
          |                                 |
          ▼                                 ▼
   STDIO Transport                 Streamable HTTP
          |                                 |
          ▼                                 ▼
     MCP Server A                     MCP Server B
          |                                 |
     Available Tools                  Available Tools
```

---

# Folder Structure

```text
mcp_client/
│
├── app/
│   ├── llm/prompts.py
│   ├── llm/open_ai.py
│   ├── mcp_client/mcp_client.py
│   ├── mcp_client/mcp_config.json
│   ├── config.py
│   ├── model.py
│   └── main.py
│
├── .env
├── requirements.txt
└── README.md
```

---

# Prerequisites

* Python 3.10+
* FastAPI 0.115.0
* Uvicorn 0.29.0
* MCP Python SDK 2.0.0b1
* Azure OpenAI
* Access to one or more MCP servers

---

# Quick Start

## 1. Clone the repository

```bash
git clone https://github.com/PAbhilashTRC/mcp_client_server.git 

cd mcp_client_server
```

## 2. Create a virtual environment

Windows

```powershell
python -m venv .venv

.venv\Scripts\Activate.ps1
```

Linux/macOS

```bash
python -m venv .venv

source .venv/bin/activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure Environment Variables

Add 
```
.env
```

Add AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION and MCP_CONFIG

---

# MCP Configuration File

The client loads MCP server definitions from an MCP configuration file.

Example:

```json
{
    "mcp_servers": {
        "RAG":{
            "url": "http://localhost:8200/fieldOn_rag/mcp",
            "type": "http",
            "mode": "streamable"
        },
        "outlook": {
            "command": "python",
            "args": ["-m", "outlook_mcp_server"],
            "type": "stdio"
            }
    }
}

```

Each server entry specifies the type and connection details (url, command, args) required to establish communication with the MCP server.

---

# Supported Transports

## STDIO

Used for launching local MCP servers as child processes.

Suitable for:

* Local development
* Desktop applications
* Local Python tools

Example:

```json
{
  "type": "stdio",
  "command": "python",
  "args": [
    "-m",
    "gmail_mcp"
  ]
}
```

---

## Streamable HTTP

Used for connecting to remote MCP servers over HTTP.

Suitable for:

* Cloud-hosted MCP servers
* Enterprise deployments
* Shared tool services

Example:

```json
{
  "type": "streamable-http",
  "mode": "streamable",
  "url": "https://example.com/mcp"
}
```

---

# Running the FastAPI Server

Start the development server:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

After the server starts:

```
Application
http://localhost:8000

---

# Connecting to MCP Servers

During application startup:

1. The client loads the MCP configuration file.
2. Reads each configured server.
3. Creates the appropriate transport.
4. Establishes the connection.
5. Discovers available tools.
6. Registers discovered tools for execution.

Once initialized, the client can invoke tools hosted by any connected MCP server.

---

# Tool Discovery & Invocation

The client follows the MCP tool execution lifecycle:

```
User Request
      │
      ▼
LLM Determines Tool
      │
      ▼
Lookup Tool
      │
      ▼
Execute MCP Tool
      │
      ▼
Receive Tool Result
      │
      ▼
Generate Final Response
```

This workflow abstracts communication with multiple MCP servers behind a single interface, allowing the LLM to interact with external capabilities without needing to manage individual server connections.

---

# API Endpoints

| Method | Endpoint  | Description                                                                     |
| ------ | --------- | ------------------------------------------------------------------------------- |
| POST   | `/user_query`   | Sends a user request to the LLM, allowing it to invoke MCP tools when required. |

---

# Limitations

* Supports only the transports implemented by the client.
* MCP servers must be reachable and correctly configured.
* Authentication depends on the capabilities of the target MCP server.
* Tool names should be unique across connected servers to avoid conflicts.
* Invalid MCP configuration files prevent successful initialization.
