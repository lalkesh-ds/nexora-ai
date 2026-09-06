<div align="center">

# 🧠 Nexora — AI-Powered RAG Knowledge Assistant

**An intelligent, document-grounded assistant powered by Retrieval-Augmented Generation (RAG)**

Upload your documents, ask questions in plain language, and get accurate, source-cited answers — grounded strictly in *your* data, never hallucinated.

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Frontend-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![LangChain](https://img.shields.io/badge/LangChain-RAG_Framework-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)](https://www.langchain.com/)
[![Pinecone](https://img.shields.io/badge/Pinecone-Vector_DB-000000?style=for-the-badge&logo=pinecone&logoColor=white)](https://www.pinecone.io/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

</div>

---

## 📖 Overview

**Nexora** is a full-stack **Retrieval-Augmented Generation (RAG)** application that turns static documents into an interactive knowledge base you can *talk to*.

Instead of relying on an LLM's raw memory — which can be outdated, generic, or simply wrong — Nexora retrieves the most relevant passages from **your own uploaded documents** and asks the LLM to answer strictly from that context. If the answer isn't in the documents, the assistant says so instead of guessing.

> 🚧 **Status:** This is an actively evolving personal project. The current version covers the core RAG pipeline (upload → embed → retrieve → answer); advanced capabilities like **Corrective RAG (CRAG)**, **live web search fallback**, hybrid retrieval, and agentic reasoning are in active development — see [Roadmap](#️-roadmap).

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 📄 **Multi-PDF Ingestion** | Upload multiple PDFs at once via a simple drag-and-drop sidebar |
| ✂️ **Smart Chunking** | Documents are split into overlapping semantic chunks for high-quality retrieval |
| 🧠 **Vector Search** | Google's `gemini-embedding-001` embeddings, indexed in a Pinecone serverless vector store |
| 🤖 **Grounded Answers** | Answers are generated **only** from retrieved context — no hallucinated facts |
| 📚 **Source Attribution** | Every answer displays which document chunks it was derived from |
| 💬 **Conversational UI** | A polished, dark-themed Streamlit chat interface with suggested prompts |
| 📥 **Chat Export** | Download the full conversation history as a `.txt` file |
| 🛡️ **Centralized Error Handling** | Global FastAPI middleware catches and logs unhandled exceptions gracefully |
| ⚡ **Fast Inference** | Uses Groq's LPU-accelerated inference (`openai/gpt-oss-120b`) for near-instant responses |

---

## 🏗️ Architecture

Nexora follows a decoupled two-service architecture: a **FastAPI backend** handling ingestion and retrieval, and a **Streamlit frontend** providing the chat experience.

```
                         ┌──────────────────────────┐
                         │      Streamlit UI        │
                         │  (upload · chat · export)│
                         └────────────┬─────────────┘
                                      │ REST (HTTP)
                                      ▼
                         ┌──────────────────────────┐
                         │      FastAPI Backend      │
                         │  /upload_pdfs/   /ask/    │
                         └──────┬────────────┬───────┘
                                │            │
                 ┌──────────────┘            └──────────────┐
                 ▼                                           ▼
     ┌───────────────────────┐                  ┌────────────────────────┐
     │  Ingestion Pipeline    │                  │   Retrieval Pipeline    │
     │  1. PyPDFLoader        │                  │  1. Embed user query    │
     │  2. Recursive chunking │                  │  2. Pinecone similarity │
     │  3. Google embeddings  │                  │     search (top-k)      │
     │  4. Pinecone upsert    │                  │  3. Custom retriever    │
     └───────────┬────────────┘                  │  4. RetrievalQA chain   │
                 │                                │  5. ChatGroq LLM       │
                 ▼                                │  6. Answer + sources   │
         ┌───────────────┐                        └────────────┬───────────┘
         │   Pinecone     │◄───────────────────────────────────┘
         │  Vector Index  │
         └───────────────┘
```

**Flow summary:**
1. **Upload** — PDFs are parsed page-by-page, split into ~500-character overlapping chunks, embedded with Google's embedding model, and upserted into a Pinecone index.
2. **Ask** — The user's question is embedded the same way, Pinecone returns the top-k most similar chunks, and those chunks are fed into a `RetrievalQA` chain backed by a Groq-hosted LLM using a strict, context-grounded prompt template.
3. **Respond** — The answer, along with its source document references, is returned to the Streamlit UI and rendered in the chat.

---

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| **Backend Framework** | [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn |
| **Frontend Framework** | [Streamlit](https://streamlit.io/) |
| **Orchestration** | [LangChain](https://www.langchain.com/) (`langchain-community`, `langchain-core`) |
| **LLM Inference** | [Groq](https://groq.com/) via `langchain-groq` (`openai/gpt-oss-120b`) |
| **Embeddings** | Google Generative AI — `gemini-embedding-001` (768 dimensions) |
| **Vector Database** | [Pinecone](https://www.pinecone.io/) (serverless, AWS `us-east-1`, dot-product metric) |
| **PDF Parsing** | `PyPDFLoader` (PyPDF backend) |
| **Config & Secrets** | `python-dotenv` |
| **Logging** | Python `logging` |

---

## 📂 Project Structure

```
nexora-ai/
├── backend/
│   ├── main.py                      # FastAPI app entrypoint, CORS & middleware setup
│   ├── logger.py                    # Centralized logger configuration
│   ├── middlewares/
│   │   └── exception_handlers.py    # Global exception-catching middleware
│   ├── routes/
│   │   ├── upload_pdfs.py           # POST /upload_pdfs/ — ingest & index PDFs
│   │   └── ask_question.py          # POST /ask/ — RAG query endpoint
│   └── modules/
│       ├── load_vectorstore.py      # PDF loading, chunking, embedding, Pinecone upsert
│       ├── llm.py                   # Groq LLM + prompt template + RetrievalQA chain
│       ├── query_handlers.py        # Chain execution & response formatting
│       └── pdf_handlers.py          # File-saving utilities
├── frontend/
│   ├── utils/
│   │   ├── app.py                   # Streamlit app entrypoint
│   │   ├── api.py                   # HTTP client for backend endpoints
│   │   └── config.py                # Frontend configuration (API base URL)
│   ├── components/
│   │   ├── upload.py                # Sidebar PDF uploader
│   │   ├── chatUI.py                # Chat interface, theming & message rendering
│   │   └── history_download.py      # Chat history export
│   └── assets/
│       └── nexora.png               # Assistant avatar
├── assets/                          # Sample/reference documents
├── requirements.txt
├── .env                             # Environment secrets (not committed)
├── .gitignore
└── LICENSE
```

---

## 🚀 Getting Started

### Prerequisites
- Python **3.11+**
- A [Groq API key](https://console.groq.com/keys)
- A [Pinecone API key](https://app.pinecone.io/)
- A [Google AI Studio API key](https://aistudio.google.com/app/apikey) (for Gemini embeddings)

### 1. Clone the repository
```bash
git clone https://github.com/lalkesh-ds/nexora-ai.git
cd nexora-ai
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key
PINECONE_API_KEY=your_pinecone_api_key
GOOGLE_API_KEY=your_google_api_key
PINECONE_INDEX_NAME=your_pinecone_index_name
```

### 5. Run the backend (FastAPI)
```bash
uvicorn backend.main:app --reload
```
The API will be available at `http://127.0.0.1:8000` — interactive docs at `http://127.0.0.1:8000/docs`.

### 6. Run the frontend (Streamlit)
In a second terminal:
```bash
streamlit run frontend/utils/app.py
```
The chat UI will open at `http://localhost:8501`.

---

## 🔌 API Reference

### `POST /upload_pdfs/`
Uploads one or more PDF files, chunks and embeds them, and stores them in the Pinecone index.

**Request:** `multipart/form-data`

| Field | Type | Description |
|---|---|---|
| `files` | `File[]` | One or more `.pdf` files |

**Response**
```json
{ "messages": "Files processed and vectorstore updated" }
```

---

### `POST /ask/`
Answers a natural-language question using retrieved context from previously uploaded documents.

**Request:** `application/x-www-form-urlencoded`

| Field | Type | Description |
|---|---|---|
| `question` | `string` | The user's question |

**Response**
```json
{
  "response": "Based on your uploaded document, the key finding was...",
  "sources": ["document.pdf", "document.pdf"]
}
```

---

## ⚙️ Configuration Reference

| Variable | Used By | Description |
|---|---|---|
| `GROQ_API_KEY` | `backend/modules/llm.py` | Auth key for the Groq-hosted LLM |
| `GOOGLE_API_KEY` | `backend/modules/load_vectorstore.py`, `ask_question.py` | Auth key for Gemini embeddings |
| `PINECONE_API_KEY` | `backend/modules/load_vectorstore.py`, `ask_question.py` | Auth key for Pinecone vector store |
| `PINECONE_INDEX_NAME` | Vector store setup | Name of the Pinecone index |

---

## 🛡️ Grounded, Honest Answers

The core prompt (see `backend/modules/llm.py`) constrains Nexora's assistant to:
- Answer **only** using the retrieved document context
- Explicitly decline to answer when the context doesn't contain the information
- Avoid fabricating facts
- Respond in a calm, clear, and factual tone

This keeps the system reliable for **document comprehension, summarization, and Q&A** across any domain.

---

## 🗺️ Roadmap

Nexora is actively evolving into a **general-purpose, production-grade advanced RAG platform**. Planned upgrades:

#### 🔁 Retrieval Intelligence
- [ ] **Corrective RAG (CRAG)** — a retrieval evaluator scores retrieved chunks, triggers query rewriting/re-retrieval when confidence is low, and falls back to alternate sources when local context is insufficient
- [ ] **Web Search Fallback / Agentic Retrieval** — when the vector store lacks a confident answer, the agent autonomously queries the live web and blends results with document context
- [ ] **Hybrid Search** — combine dense vector similarity with sparse keyword search (BM25) for better recall
- [ ] **Reranking** — cross-encoder reranker (e.g., Cohere Rerank / BGE-reranker) applied after initial top-k retrieval
- [ ] **Self-Querying Retriever** — LLM-generated metadata filters for more precise document lookup
- [ ] **Adaptive/Agentic RAG** — an LLM router that decides per-query whether to retrieve, search the web, use a tool, or answer directly

#### 🧠 Reasoning & Memory
- [ ] Multi-turn conversational memory (context-aware follow-ups)
- [ ] Query decomposition for multi-part / complex questions
- [ ] Self-reflection / answer verification step before returning a response

#### 🧩 Ingestion & Modalities
- [ ] Support for additional file types (DOCX, TXT, HTML, scanned/OCR PDFs)
- [ ] Multi-modal support (image/chart understanding inside PDFs)
- [ ] Automatic document summarization on upload

#### 🏗️ Platform & Ops
- [ ] Streaming token-by-token responses
- [ ] User authentication & per-user document namespaces
- [ ] Dockerized deployment (backend + frontend)
- [ ] RAG evaluation framework (faithfulness, relevance, answer correctness — e.g., RAGAS)
- [ ] Automated test suite (pytest)
- [ ] Observability & tracing (LangSmith / OpenTelemetry)

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1. Fork the project
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 👤 Author

**Lalkesh Yaduvanshi**
AI Engineer | Data Scientist | Machine Learning Engineer

- GitHub: [@lalkesh-ds](https://github.com/lalkesh-ds)
- Email: lalkeshyaduvanshi65@gmail.com

<div align="center">

If you found this project useful, consider giving it a ⭐ on GitHub!

</div>
