# Nexora AI — Modern React Frontend

A clinical-grade, modern React single-page application (SPA) for **Nexora AI — Multimodal Agentic Assistant**.

## Features

- **Clinical Glassmorphic Design**: Deep slate palette with cyan/emerald glowing accents, responsive sidebar, and clean typography.
- **Intelligent Mode Switcher**:
  - `AUTO` (Intelligent Orchestrator)
  - `DOCUMENT_RAG` (Clinical Document Retrieval)
  - `WEB_SEARCH` (Live Web & PubMed Research)
  - `HYBRID` (Cross-referenced Docs + Web Guidelines)
  - `VISION` (Diagnostic Imaging & Handwriting OCR)
  - `GENERAL_LLM` (Clinical Reasoning Assistant)
- **Claim-Level Verification Badge**:
  - Factual Confidence Meter
  - Grounding Score (`≥ 70%`)
  - Relevance & Faithfulness Scores
  - Hallucination Risk Indicators (`LOW`, `MEDIUM`, `HIGH`)
  - Unsupported Claims Alert & CRAG Repair Notices
- **Advanced Clinical Tools Panel**:
  - **Knowledge Base Dropzone**: Upload PDFs, DOCX, TXT, CSV, XLSX, and images with real-time status.
  - **Document Scope Selector**: Scope queries to specific uploaded files.
  - **Evidence & CRAG Inspector**: Inspect retrieved document chunks, rerank scores, and live web source snippets.
  - **Interactive Clinical Calculators**:
    - **BMI & BSA (DuBois)**
    - **Creatinine Clearance (Cockcroft-Gault)**
    - **Mean Arterial Pressure (MAP)**
    - One-click insertion into the clinical prompt.
- **Multimodal Uploads**: Drag-and-drop support with chip previews.
- **Markdown & Tables**: Full GitHub-flavored markdown and clinical data tables support.

## How to Run

### Development Mode (with Hot Reloading)

```bash
cd frontend-react
npm install
npm run dev
```

The application will be accessible at `http://localhost:5173`.

### Production Build

```bash
cd frontend-react
npm run build
```

Once built, the production bundle can also be accessed directly via the FastAPI backend at `http://localhost:8000/app/`.

### Streamlit UI (Unchanged)

The original Streamlit interface remains completely intact and can be run simultaneously:

```bash
streamlit run frontend/utils/app.py
```
