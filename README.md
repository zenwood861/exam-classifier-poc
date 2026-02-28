# Exam Question Classifier POC

Auto-splits an English exam PDF into individual questions and classifies each one against a taxonomy using **Gemini 2.0 Flash**.

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.9+ |
| Node.js | 18+ |
| Poppler | (see below) |

### Install Poppler (required for PDF→image conversion)

**macOS**
```bash
brew install poppler
```

**Ubuntu / Debian**
```bash
sudo apt-get install poppler-utils
```

**Windows**
Download the latest release from https://github.com/oschwartz10612/poppler-windows
Extract and add the `bin/` folder to your system `PATH`.

---

## Project Setup

### 1. Taxonomy file
Copy `english index table.xlsx` into the `backend/` folder:
```
exam-classifier-poc/
└── backend/
    └── english index table.xlsx   ← place here
```

### 2. Backend
```bash
cd backend
pip install -r requirements.txt

# Copy env file and add your key
copy .env.example .env        # Windows
# cp .env.example .env        # Mac/Linux
```

Edit `.env`:
```
GEMINI_API_KEY=your_actual_key_here
```

Get a free API key from https://aistudio.google.com

### 3. Frontend
```bash
cd frontend
npm install
```

---

## Running the App

Open **two terminals**:

**Terminal 1 — Backend**
```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend**
```bash
cd frontend
npm start
```

Then open **http://localhost:3000** in your browser.

---

## How to Use

1. Click **選擇 PDF 檔案** and pick an exam PDF
2. Wait for the spinner — Gemini is classifying each question
3. Review the question cards:
   - Green tag = high confidence (≥85%)
   - Orange tag = medium confidence (70–84%)
   - Red tag / ⚠️ 需人手確認 = low confidence (<70%), manual review needed
4. Hover over any tag to see the full taxonomy breakdown (A→J fields)
5. Click the page image to open it full size

---

## File Structure

```
exam-classifier-poc/
├── backend/
│   ├── main.py               # FastAPI app
│   ├── requirements.txt
│   ├── .env.example
│   └── english index table.xlsx   ← you place this here
├── frontend/
│   ├── public/index.html
│   └── src/
│       ├── App.js            # Main React app
│       └── index.js
├── uploads/                  # Uploaded PDFs (auto-created)
├── output/                   # Page images (auto-created)
└── README.md
```

---

## Taxonomy Slots

Each question is tagged with all 5 dimensions:

| Code | Description |
|------|-------------|
| A / B | Subject |
| C / D | Unit |
| E / F | Section |
| G / H | Learning Point |
| I / J | Type |

One question can receive multiple slot assignments if it spans topics.
