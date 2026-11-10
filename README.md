# StudyMate AI 🎓 — An AI-Powered Study Assistant

> A local-first, privacy-preserving academic assistant for students to ingest course materials, generate extractive summaries, ask grounded questions, test themselves with auto-generated quizzes, and plan study schedules.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📌 Features

- 📚 **Multi-Format Document Ingestion**: Upload course slides and notes in `.pdf`, `.docx`, and `.txt` formats.
- 📝 **Deterministic Extractive Summarizer**: Generates concise/detailed summaries and concept definitions using sentence-level TF-IDF and positional heuristics (no hallucinations).
- 💬 **Grounded Study Chatbot**: Natural language Q&A backed by local TF-IDF vector retrieval and cosine similarity ranking. If notes lack an answer, it explicitly informs the student.
- 🎯 **Rule-Based Quiz Generator**: Creates Multiple Choice (MCQ), True/False, and Short-Answer questions directly from facts and definitions with source explanations.
- 🗂️ **Interactive Flashcards**: Flip-card drill system with *Known* and *Needs Revision* mastery tracking.
- 📅 **Constraint-Based Study Planner**: Algorithmic timetable that optimizes daily study quotas based on exam dates and historical quiz weaknesses.
- 📊 **Learning Analytics**: Diagnostic tracking of topic-by-topic scores, revision backlogs, and study time.
- 🔒 **Multi-Tenancy & Data Privacy**: Salted PBKDF2 password hashing with strict per-user database isolation (`WHERE user_id = ?`).

---

## 🛠️ Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Frontend UI** | [Streamlit](https://streamlit.io/) |
| **Language** | Python 3.10+ |
| **NLP & Retrieval** | Pure-Python vector space model (TF-IDF & Cosine Similarity) |
| **Database** | SQLite (Default local) / PostgreSQL via SQLAlchemy |
| **Document Parsing** | PyMuPDF (`fitz`), `python-docx` |
| **Testing** | `pytest` |

---

## 🚀 Quick Start Guide

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/studymate-ai.git
cd studymate-ai
```

### 2. Create and Activate Virtual Environment
```bash
# On Windows:
python -m venv venv
venv\Scripts\activate

# On Linux/macOS:
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Application
```bash
streamlit run app.py
```
Open `http://localhost:8501` in your browser.

---

## 🧪 Running Automated Tests

```bash
pytest test_suite.py -v
```

---

## 📂 Project Structure

```text
studymate_ai/
│── app.py                    # Main Streamlit application
│── requirements.txt          # Python dependencies
│── README.md                 # Project documentation
│── .gitignore                # Ignored files (databases, venv, secrets)
│── test_suite.py             # Automated unit and integration tests
│── studymate_local.db        # SQLite database (auto-created on run)
└── docs/                     # Academic reports and presentation slides
```

---

## 👥 Authors & Academic Credit

Developed as a college mini-capstone project by a team of 4 engineering students:
- **Member 1**: UI/UX, Authentication & Multi-Tenancy
- **Member 2**: Document Parsing & Extractive Summarization
- **Member 3**: Vector Space Retrieval, Chatbot & Rule-Based Quizzes
- **Member 4**: Flashcards, Constraint-Satisfaction Study Planner & Analytics

---

## 📄 License
This project is open-source under the [MIT License](LICENSE).