"""
StudyMate AI — An AI-Powered Study Assistant (AppLocker / Device-Guard Safe Edition)
==================================================================================
Pure-Python core: operates cleanly without triggering Windows Application Control
or AppLocker blocks on compiled C-extension libraries (.pyd / .dll).
"""

import os
import sys
import re
import math
import hashlib
import datetime
from typing import List, Dict, Tuple, Optional, Any

import streamlit as st

# ==============================================================================
# SECTION 1: DATABASE PERSISTENCE (PURE SQLITE3 / SQLALCHEMY COMPATIBLE)
# ==============================================================================

import sqlite3

DB_FILE = os.path.join(os.path.dirname(__file__), "studymate_local.db")

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        file_type TEXT NOT NULL,
        word_count INTEGER DEFAULT 0,
        extracted_text TEXT NOT NULL,
        upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS study_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        topic TEXT NOT NULL,
        duration_minutes INTEGER DEFAULT 15,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS quiz_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        document_id INTEGER,
        topic TEXT NOT NULL,
        score REAL NOT NULL,
        total_questions INTEGER NOT NULL,
        correct_answers INTEGER NOT NULL,
        incorrect_answers INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS flashcards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        document_id INTEGER,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        status TEXT DEFAULT 'Needs Revision',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS study_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        subject TEXT NOT NULL,
        topic TEXT NOT NULL,
        exam_date TEXT NOT NULL,
        daily_minutes INTEGER DEFAULT 45,
        priority TEXT DEFAULT 'Medium',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)
    conn.commit()
    conn.close()

init_db()

# ==============================================================================
# SECTION 2: AUTHENTICATION & MULTI-TENANCY SECURITY
# ==============================================================================

class SecurityService:
    SECRET_KEY = "studymate-secure-capstone-key-2026"

    @classmethod
    def hash_password(cls, password: str) -> str:
        salt = hashlib.sha256(cls.SECRET_KEY.encode()).hexdigest()[:16]
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            iterations=100_000
        )
        return f"{salt}${key.hex()}"

    @classmethod
    def verify_password(cls, stored_hash: str, password: str) -> bool:
        try:
            salt, key_hex = stored_hash.split("$")
            new_key = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt.encode('utf-8'),
                iterations=100_000
            )
            return new_key.hex() == key_hex
        except Exception:
            return False

class AuthService:
    @staticmethod
    def register_user(name: str, email: str, password: str) -> Tuple[bool, str]:
        email_clean = email.strip().lower()
        if not email_clean or "@" not in email_clean:
            return False, "Please enter a valid email address."
        if len(password) < 6:
            return False, "Password must be at least 6 characters long."
        if not name.strip():
            return False, "Name cannot be empty."

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT id FROM users WHERE email = ?", (email_clean,))
            if cur.fetchone():
                return False, "An account with this email already exists."

            hashed = SecurityService.hash_password(password)
            cur.execute("INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                        (name.strip(), email_clean, hashed))
            conn.commit()
            return True, "Account created successfully! Please sign in."
        except Exception as e:
            return False, f"Registration failed: {str(e)}"
        finally:
            conn.close()

    @staticmethod
    def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, name, email, password_hash FROM users WHERE email = ?", (email.strip().lower(),))
            row = cur.fetchone()
            if row and SecurityService.verify_password(row["password_hash"], password):
                return {"id": row["id"], "name": row["name"], "email": row["email"]}
            return None
        finally:
            conn.close()

# ==============================================================================
# SECTION 3: PURE-PYTHON NLP & RETRIEVAL (NO C-EXTENSIONS NEEDED)
# ==============================================================================

class PureNLP:
    STOPWORDS = set([
        "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
        "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
        "by", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
        "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
        "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just",
        "me", "more", "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once",
        "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
        "she", "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
        "themselves", "then", "there", "these", "they", "this", "those", "through", "to", "too",
        "under", "until", "up", "very", "was", "we", "were", "what", "when", "where", "which",
        "while", "who", "whom", "why", "with", "would", "you", "your", "yours", "yourself", "yourselves"
    ])

    @staticmethod
    def clean_text(text: str) -> str:
        if not text:
            return ""
        text = text.replace("\r", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{2,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def split_sentences(text: str) -> List[str]:
        cleaned = PureNLP.clean_text(text)
        if not cleaned:
            return []
        raw_sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"\'])', cleaned)
        valid = []
        for s in raw_sentences:
            s_clean = s.strip()
            if len(s_clean) >= 15 and len(s_clean.split()) >= 3:
                valid.append(s_clean)
        return valid

    @staticmethod
    def tokenize(text: str) -> List[str]:
        tokens = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        return [t for t in tokens if t not in PureNLP.STOPWORDS]

    @classmethod
    def compute_tfidf_vectors(cls, docs: List[str]) -> Tuple[List[Dict[str, float]], Dict[str, float]]:
        """Compute pure-Python TF-IDF sparse dictionary representations."""
        doc_tokens = [cls.tokenize(d) for d in docs]
        N = len(docs)
        if N == 0:
            return [], {}

        # Document frequency
        df_count = {}
        for tokens in doc_tokens:
            unique_terms = set(tokens)
            for term in unique_terms:
                df_count[term] = df_count.get(term, 0) + 1

        # Smooth IDF
        idf = {term: math.log((1 + N) / (1 + count)) + 1.0 for term, count in df_count.items()}

        vectors = []
        for tokens in doc_tokens:
            if not tokens:
                vectors.append({})
                continue
            tf = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            total = len(tokens)
            vec = {}
            norm_sq = 0.0
            for t, count in tf.items():
                val = (count / total) * idf.get(t, 1.0)
                vec[t] = val
                norm_sq += val * val
            # L2 normalize
            norm = math.sqrt(norm_sq) if norm_sq > 0 else 1.0
            vectors.append({t: v / norm for t, v in vec.items()})

        return vectors, idf

    @staticmethod
    def cosine_similarity_dict(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
        if not vec_a or not vec_b:
            return 0.0
        dot_product = 0.0
        for k, v in vec_a.items():
            if k in vec_b:
                dot_product += v * vec_b[k]
        return dot_product

# ==============================================================================
# SECTION 4: DOCUMENT EXTRACTION (TXT, DOCX, AND PURE FALLBACKS)
# ==============================================================================

class DocumentProcessor:
    @staticmethod
    def process_file(filename: str, file_bytes: bytes) -> Tuple[bool, str, int, str]:
        if not file_bytes or len(file_bytes) == 0:
            return False, "", 0, "Uploaded file is empty (0 bytes)."

        ext = filename.split(".")[-1].lower() if "." in filename else ""
        text = ""

        if ext in ["txt", "md", "csv"]:
            try:
                text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    text = file_bytes.decode("latin-1")
                except Exception as e:
                    return False, "", 0, f"Encoding error: {str(e)}"
        elif ext in ["docx"]:
            try:
                import docx
                import io
                doc = docx.Document(io.BytesIO(file_bytes))
                text = "\n\n".join([p.text.strip() for p in doc.paragraphs if p.text.strip()])
            except Exception as e:
                return False, "", 0, f"Could not read DOCX: {str(e)}"
        elif ext == "pdf":
            # Attempt fitz or pdfplumber if unblocked, else give clean prompt
            extracted = False
            try:
                import fitz
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                pages = [page.get_text() for page in doc]
                text = "\n\n".join(pages)
                extracted = True
            except Exception:
                pass

            if not extracted:
                # Try simple regex stream scan for unencrypted basic PDFs
                try:
                    raw_str = file_bytes.decode("latin-1")
                    streams = re.findall(r'BT\s*(.*?)\s*ET', raw_str, flags=re.DOTALL)
                    found_words = []
                    for st in streams:
                        text_chunks = re.findall(r'\((.*?)\)\s*Tj', st)
                        if text_chunks:
                            found_words.extend(text_chunks)
                    if found_words:
                        text = " ".join(found_words)
                        extracted = True
                except Exception:
                    pass

            if not extracted or len(text.split()) < 10:
                return False, "", 0, "Could not extract text from this PDF on this restricted system. Please save/convert the document as a .TXT or .DOCX file and re-upload!"

        cleaned = PureNLP.clean_text(text)
        words = len(cleaned.split())
        if words < 10:
            return False, "", 0, "Document text is too brief (< 10 words)."

        return True, cleaned, words, "Extraction successful."

# ==============================================================================
# SECTION 5: SUMMARIZER & INFORMATION RETRIEVAL
# ==============================================================================

class ExtractiveSummarizer:
    @classmethod
    def generate_summary(cls, text: str) -> Dict[str, Any]:
        sentences = PureNLP.split_sentences(text)
        if not sentences:
            return {"concise": "No legible sentences found.", "detailed": "", "bullets": [], "terms": {}}

        if len(sentences) <= 3:
            return {
                "concise": " ".join(sentences),
                "detailed": "\n\n".join(sentences),
                "bullets": sentences,
                "terms": cls.extract_terms(text)
            }

        vectors, _ = PureNLP.compute_tfidf_vectors(sentences)
        scored = []
        for i, s in enumerate(sentences):
            vec = vectors[i]
            base_score = sum(vec.values())
            # Lead bias: early sentences in notes contain definitions/theses
            lead_mult = 1.3 if i == 0 else (1.15 if i < 3 else 1.0)
            score = base_score * lead_mult
            scored.append((i, s, score))

        ranked = sorted(scored, key=lambda x: x[2], reverse=True)

        top_concise = sorted(ranked[:min(3, max(2, len(sentences) // 6))], key=lambda x: x[0])
        top_detailed = sorted(ranked[:min(7, max(4, len(sentences) // 3))], key=lambda x: x[0])
        top_bullets = sorted(ranked[:min(5, max(3, len(sentences) // 4))], key=lambda x: x[0])

        return {
            "concise": " ".join([item[1] for item in top_concise]),
            "detailed": "\n\n".join([item[1] for item in top_detailed]),
            "bullets": [item[1] for item in top_bullets],
            "terms": cls.extract_terms(text)
        }

    @staticmethod
    def extract_terms(text: str) -> Dict[str, str]:
        sentences = PureNLP.split_sentences(text)
        tokens = PureNLP.tokenize(text)
        freq = {}
        for t in tokens:
            freq[t] = freq.get(t, 0) + 1
        sorted_terms = [t for t, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True) if len(t) > 3][:6]

        definitions = {}
        for term in sorted_terms:
            matched = None
            pat = re.compile(rf'\b{term}\b\s+(?:is|are|refers to|means|represents|defined as)\s+([^.]+)', re.IGNORECASE)
            for s in sentences:
                m = pat.search(s)
                if m:
                    matched = m.group(0).strip()
                    break
            if not matched:
                for s in sentences:
                    if term.lower() in s.lower() and len(s.split()) >= 6:
                        matched = s.strip()
                        break
            definitions[term.capitalize()] = matched if matched else f"Key concept occurring {freq[term]} times in notes."
        return definitions

class StudyChatbot:
    @staticmethod
    def chunk_text(text: str, chunk_size: int = 100, overlap: int = 25) -> List[str]:
        words = text.split()
        if len(words) <= chunk_size:
            return [text.strip()]
        chunks = []
        step = max(1, chunk_size - overlap)
        for i in range(0, len(words), step):
            chunk = " ".join(words[i : i + chunk_size])
            if len(chunk.strip()) > 25:
                chunks.append(chunk.strip())
            if i + chunk_size >= len(words):
                break
        return chunks

    @classmethod
    def query(cls, question: str, doc_text: str, doc_title: str) -> Dict[str, Any]:
        chunks = cls.chunk_text(doc_text)
        if not chunks:
            return {"answer": "I could not find enough relevant information in your uploaded notes.", "passages": []}

        # Vectorize
        all_texts = chunks + [question]
        vectors, _ = PureNLP.compute_tfidf_vectors(all_texts)
        q_vec = vectors[-1]
        chunk_vecs = vectors[:-1]

        scored = []
        for i, cv in enumerate(chunk_vecs):
            sim = PureNLP.cosine_similarity_dict(cv, q_vec)
            scored.append((chunks[i], sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        best_passage, best_score = scored[0]

        if best_score < 0.08:
            return {
                "answer": "I could not find enough relevant information in your uploaded notes.",
                "passages": []
            }

        # Find best sentence inside the passage
        q_tokens = set(PureNLP.tokenize(question))
        sentences = PureNLP.split_sentences(best_passage)
        best_sentence = best_passage
        if sentences and q_tokens:
            s_scored = []
            for s in sentences:
                overlap = len(q_tokens.intersection(set(PureNLP.tokenize(s))))
                s_scored.append((s, overlap))
            s_scored.sort(key=lambda x: x[1], reverse=True)
            if s_scored[0][1] > 0:
                best_sentence = s_scored[0][0]

        answer = (
            f"**Based on '{doc_title}':**\n\n"
            f"{best_sentence}\n\n"
            f"*(Cosine relevance score: {best_score:.2f})*"
        )
        return {"answer": answer, "passages": [best_passage]}

# ==============================================================================
# SECTION 6: QUIZ & FLASHCARD GENERATORS
# ==============================================================================

class QuizGenerator:
    @classmethod
    def generate(cls, text: str, max_q: int = 5) -> List[Dict[str, Any]]:
        sentences = PureNLP.split_sentences(text)
        if len(sentences) < 2:
            return []

        tokens = PureNLP.tokenize(text)
        vocab = list(set([t.capitalize() for t in tokens if len(t) > 4]))
        questions = []

        # Rule 1: Definitions
        def_pattern = re.compile(r'\b([A-Z][a-zA-Z0-9_\-\s]{2,20})\s+(?:is defined as|is|refers to|represents)\s+([^,.;]+)', re.IGNORECASE)
        for s in sentences:
            if len(questions) >= max_q:
                break
            m = def_pattern.search(s)
            if m:
                term = m.group(1).strip().capitalize()
                pred = m.group(2).strip()
                distractors = [v for v in vocab if v.lower() != term.lower()][:3]
                if len(distractors) >= 3:
                    opts = [term] + distractors
                    import random
                    random.shuffle(opts)
                    questions.append({
                        "type": "MCQ",
                        "question": f"Which term is described as: \"...{pred}\"?",
                        "options": opts,
                        "correct_answer": term,
                        "explanation": f"Source context: \"{s}\""
                    })

        # Rule 2: Grounded True / False
        for s in sentences:
            if len(questions) >= max_q:
                break
            words = s.split()
            if 8 <= len(words) <= 22:
                # Alternate between true and modified false
                if len(questions) % 2 == 1:
                    altered = s.replace(" is ", " is not ").replace(" can ", " cannot ")
                    if altered != s:
                        questions.append({
                            "type": "TRUE_FALSE",
                            "question": f"True or False: \"{altered}\"",
                            "options": ["True", "False"],
                            "correct_answer": "False",
                            "explanation": f"Source notes state: \"{s}\""
                        })
                        continue
                questions.append({
                    "type": "TRUE_FALSE",
                    "question": f"True or False: \"{s}\"",
                    "options": ["True", "False"],
                    "correct_answer": "True",
                    "explanation": f"Supported by notes: \"{s}\""
                })

        return questions[:max_q]

class FlashcardEngine:
    @classmethod
    def generate(cls, text: str, max_cards: int = 6) -> List[Dict[str, str]]:
        sentences = PureNLP.split_sentences(text)
        cards = []
        copula = re.compile(r'([A-Z][a-zA-Z0-9_\-\s]{2,25})\s+(?:is defined as|is|refers to|means)\s+([^.]+)', re.IGNORECASE)
        for s in sentences:
            if len(cards) >= max_cards:
                break
            m = copula.search(s)
            if m:
                term = m.group(1).strip()
                definition = m.group(2).strip()
                cards.append({
                    "question": f"What is {term}?",
                    "answer": f"{term} is {definition}."
                })
        if len(cards) < max_cards:
            for s in sentences:
                if len(cards) >= max_cards:
                    break
                if any(k in s.lower() for k in ["important", "primary", "key", "function", "purpose"]):
                    cards.append({
                        "question": f"Key concept regarding '{' '.join(s.split()[:4])}...'?",
                        "answer": s
                    })
        return cards[:max_cards]

# ==============================================================================
# SECTION 7: STUDY PLANNER LOGIC
# ==============================================================================

class StudyPlanner:
    @staticmethod
    def generate_schedule(plans: List[sqlite3.Row], quiz_scores: Dict[str, float]) -> List[Dict[str, Any]]:
        today = datetime.date.today()
        tasks = []
        priority_weights = {"High": 3, "Medium": 2, "Low": 1}

        for p in plans:
            try:
                exam_d = datetime.datetime.strptime(p["exam_date"], "%Y-%m-%d").date()
                days_left = max(1, (exam_d - today).days)
            except Exception:
                days_left = 5

            days_to_spread = min(7, days_left)
            score = quiz_scores.get(p["topic"].lower(), 100.0)
            weak_mult = 1.4 if score < 60.0 else 1.0
            daily_quota = int(min(p["daily_minutes"], (p["daily_minutes"] * priority_weights.get(p["priority"], 2) * weak_mult) / 2))

            for d in range(days_to_spread):
                task_date = today + datetime.timedelta(days=d)
                tasks.append({
                    "date": task_date.strftime("%Y-%m-%d"),
                    "subject": p["subject"],
                    "topic": p["topic"],
                    "duration": max(15, daily_quota),
                    "priority": p["priority"],
                    "notes": f"Exam in {days_left}d | Historic Quiz: {score:.0f}%"
                })
        return tasks

# ==============================================================================
# SECTION 8: STREAMLIT USER INTERFACE
# ==============================================================================

def main():
    st.set_page_config(page_title="StudyMate AI", page_icon="🎓", layout="wide")

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.active_doc_id = None
        st.session_state.current_page = "Dashboard"
        st.session_state.fc_idx = 0
        st.session_state.fc_flip = False

    # Login View
    if not st.session_state.authenticated:
        st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>StudyMate AI 🎓</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #64748B;'>An AI-Powered Academic Assistant</p>", unsafe_allow_html=True)
        tab_login, tab_reg = st.tabs(["🔐 Sign In", "📝 Create Account"])

        with tab_login:
            st.subheader("Student Sign In")
            em = st.text_input("Email", key="l_email")
            pw = st.text_input("Password", type="password", key="l_pw")
            if st.button("Sign In", type="primary", use_container_width=True):
                user = AuthService.authenticate_user(em, pw)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid email or password.")

        with tab_reg:
            st.subheader("New Student Registration")
            r_name = st.text_input("Full Name", key="r_name")
            r_email = st.text_input("Email", key="r_email")
            r_pw = st.text_input("Password (min 6 chars)", type="password", key="r_pw")
            if st.button("Create Account", use_container_width=True):
                ok, msg = AuthService.register_user(r_name, r_email, r_pw)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
        return

    # Authenticated Layout & Sidebar
    user_id = st.session_state.user["id"]
    user_name = st.session_state.user["name"]

    with st.sidebar:
        st.markdown(f"### StudyMate AI\n**Student:** {user_name}")
        st.divider()

        pages = [
            "Dashboard", "My Documents", "AI Summarizer", "Study Chatbot",
            "Quiz Generator", "Flashcards", "Study Planner", "Learning Analytics", "Settings"
        ]
        page = st.radio("Navigation", pages, index=pages.index(st.session_state.current_page))
        st.session_state.current_page = page

        st.divider()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, title FROM documents WHERE user_id = ? ORDER BY id DESC", (user_id,))
        docs = cur.fetchall()
        conn.close()

        if docs:
            doc_map = {d["id"]: d["title"] for d in docs}
            curr_id = st.session_state.active_doc_id if st.session_state.active_doc_id in doc_map else docs[0]["id"]
            st.session_state.active_doc_id = curr_id
            chosen = st.selectbox("Active Note Context:", list(doc_map.keys()), format_func=lambda x: doc_map[x],
                                  index=list(doc_map.keys()).index(curr_id))
            st.session_state.active_doc_id = chosen
        else:
            st.caption("No notes uploaded yet.")

        st.divider()
        if st.button("Log Out", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.rerun()

    # ---------------- PAGE ROUTING ----------------
    conn = get_db_connection()
    cur = conn.cursor()

    if page == "Dashboard":
        st.title(f"Welcome back, {user_name}! 👋")
        st.caption("Empirical overview of your notes, quizzes, and learning schedule.")

        cur.execute("SELECT COUNT(*) FROM documents WHERE user_id = ?", (user_id,))
        doc_count = cur.fetchone()[0]
        cur.execute("SELECT SUM(duration_minutes) FROM study_sessions WHERE user_id = ?", (user_id,))
        time_sum = cur.fetchone()[0] or 0
        cur.execute("SELECT AVG(score) FROM quiz_attempts WHERE user_id = ?", (user_id,))
        avg_score = cur.fetchone()[0] or 0.0
        cur.execute("SELECT COUNT(*) FROM flashcards WHERE user_id = ? AND status = 'Known'", (user_id,))
        known_fc = cur.fetchone()[0]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Documents Stored", doc_count)
        c2.metric("Total Study Time", f"{time_sum} mins")
        c3.metric("Average Quiz Score", f"{avg_score:.1f}%")
        c4.metric("Known Flashcards", known_fc)

        st.divider()
        st.subheader("Recent Quiz History")
        cur.execute("SELECT topic, score, created_at FROM quiz_attempts WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,))
        recent_q = cur.fetchall()
        if recent_q:
            for rq in recent_q:
                st.write(f"🎯 **{rq['topic']}** — Score: `{rq['score']:.1f}%` ({rq['created_at']})")
        else:
            st.info("Take a quiz in 'Quiz Generator' to start tracking your scores!")

    elif page == "My Documents":
        st.title("My Documents 📚")
        with st.expander("📤 Upload New Notes (PDF, DOCX, TXT)", expanded=True):
            uploaded = st.file_uploader("Choose file:", type=["txt", "docx", "pdf", "md"])
            if st.button("Save & Process Note", type="primary"):
                if uploaded:
                    content = uploaded.read()
                    ok, text, words, msg = DocumentProcessor.process_file(uploaded.name, content)
                    if ok:
                        cur.execute("INSERT INTO documents (user_id, title, file_type, word_count, extracted_text) VALUES (?, ?, ?, ?, ?)",
                                    (user_id, uploaded.name, uploaded.name.split(".")[-1].upper(), words, text))
                        conn.commit()
                        st.success(f"Successfully processed '{uploaded.name}' ({words} words)!")
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.warning("Please choose a file.")

        st.subheader("Your Stored Notes")
        cur.execute("SELECT id, title, file_type, word_count, upload_date, extracted_text FROM documents WHERE user_id = ? ORDER BY id DESC", (user_id,))
        all_docs = cur.fetchall()
        for d in all_docs:
            col_info, col_act = st.columns([4, 1])
            with col_info:
                st.markdown(f"#### {d['title']} `[{d['file_type']}]`")
                st.caption(f"{d['word_count']} words | Uploaded: {d['upload_date']}")
                with st.expander("Preview Text"):
                    st.text(d['extracted_text'][:800] + ("..." if len(d['extracted_text']) > 800 else ""))
            with col_act:
                if st.button("Set Active", key=f"act_{d['id']}", use_container_width=True):
                    st.session_state.active_doc_id = d['id']
                    st.success("Set active!")
                    st.rerun()
                if st.button("Delete", key=f"del_{d['id']}", use_container_width=True):
                    cur.execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (d['id'], user_id))
                    conn.commit()
                    st.rerun()
            st.divider()

    elif page == "AI Summarizer":
        st.title("AI Document Summarizer 📝")
        if not st.session_state.active_doc_id:
            st.warning("Please select or upload a document first.")
        else:
            cur.execute("SELECT title, extracted_text FROM documents WHERE id = ? AND user_id = ?",
                        (st.session_state.active_doc_id, user_id))
            doc = cur.fetchone()
            st.info(f"Target Note: **{doc['title']}**")
            st.caption("Extractive NLP: ranks original sentences based on word salience, TF-IDF weights, and lead-sentence position.")

            if st.button("Generate Extractive Summary", type="primary"):
                summary = ExtractiveSummarizer.generate_summary(doc["extracted_text"])
                st.session_state[f"sum_{st.session_state.active_doc_id}"] = summary

            if f"sum_{st.session_state.active_doc_id}" in st.session_state:
                res = st.session_state[f"sum_{st.session_state.active_doc_id}"]
                t1, t2, t3, t4 = st.tabs(["📌 Concise Summary", "📖 Detailed Summary", "Core Points", "🔑 Key Terms"])
                with t1:
                    st.write(res["concise"])
                with t2:
                    st.write(res["detailed"])
                with t3:
                    for b in res["bullets"]:
                        st.markdown(f"- {b}")
                with t4:
                    for k, v in res["terms"].items():
                        st.markdown(f"**{k}**: {v}")

    elif page == "Study Chatbot":
        st.title("Study Chatbot 💬")
        if not st.session_state.active_doc_id:
            st.warning("Please select an active note first.")
        else:
            cur.execute("SELECT title, extracted_text FROM documents WHERE id = ? AND user_id = ?",
                        (st.session_state.active_doc_id, user_id))
            doc = cur.fetchone()
            st.info(f"Grounded in: **{doc['title']}** (Pure-Python TF-IDF Retrieval)")

            q = st.text_input("Ask a question about this material:")
            if st.button("Find Answer", type="primary"):
                if q.strip():
                    ans = StudyChatbot.query(q, doc["extracted_text"], doc["title"])
                    st.markdown(ans["answer"])
                    if ans["passages"]:
                        with st.expander("Retrieved Source Grounding Excerpt"):
                            st.write(ans["passages"][0])

    elif page == "Quiz Generator":
        st.title("Rule-Based Quiz Generator 🎯")
        if not st.session_state.active_doc_id:
            st.warning("Please select an active note first.")
        else:
            cur.execute("SELECT id, title, extracted_text FROM documents WHERE id = ? AND user_id = ?",
                        (st.session_state.active_doc_id, user_id))
            doc = cur.fetchone()
            st.info(f"Formulating questions from: **{doc['title']}**")

            if st.button("Generate New Quiz", type="primary"):
                st.session_state.quiz_items = QuizGenerator.generate(doc["extracted_text"], max_q=5)
                st.session_state.quiz_answers = {}

            if "quiz_items" in st.session_state and st.session_state.quiz_items:
                with st.form("quiz_form"):
                    for i, item in enumerate(st.session_state.quiz_items):
                        st.markdown(f"**Q{i+1}: {item['question']}**")
                        choice = st.radio(f"Select answer for Q{i+1}:", item["options"], key=f"qz_{i}")
                        st.session_state.quiz_answers[i] = choice
                        st.write("---")
                    sub = st.form_submit_button("Submit Quiz For Grading", type="primary")

                if sub:
                    correct = 0
                    total = len(st.session_state.quiz_items)
                    for i, item in enumerate(st.session_state.quiz_items):
                        ans = st.session_state.quiz_answers.get(i)
                        is_ok = (ans == item["correct_answer"])
                        if is_ok:
                            correct += 1
                            st.success(f"**Q{i+1}: Correct!** ({ans})")
                        else:
                            st.error(f"**Q{i+1}: Incorrect.** (Your answer: {ans} | Correct: {item['correct_answer']})")
                        st.caption(item["explanation"])

                    pct = (correct / total) * 100
                    st.markdown(f"### Score: **{correct} / {total}** ({pct:.1f}%)")
                    cur.execute("""
                    INSERT INTO quiz_attempts (user_id, document_id, topic, score, total_questions, correct_answers, incorrect_answers)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (user_id, doc["id"], doc["title"], pct, total, correct, total - correct))
                    conn.commit()

    elif page == "Flashcards":
        st.title("Interactive Flashcards 🗂️")
        if st.session_state.active_doc_id and st.button("Generate Flashcards from Active Note", type="primary"):
            cur.execute("SELECT id, extracted_text FROM documents WHERE id = ? AND user_id = ?",
                        (st.session_state.active_doc_id, user_id))
            doc = cur.fetchone()
            cards = FlashcardEngine.generate(doc["extracted_text"])
            for c in cards:
                cur.execute("INSERT INTO flashcards (user_id, document_id, question, answer, status) VALUES (?, ?, ?, ?, 'Needs Revision')",
                            (user_id, doc["id"], c["question"], c["answer"]))
            conn.commit()
            st.success(f"Generated {len(cards)} flashcards!")
            st.rerun()

        cur.execute("SELECT id, question, answer, status FROM flashcards WHERE user_id = ?", (user_id,))
        fc_list = cur.fetchall()

        if not fc_list:
            st.info("No flashcards found. Click the button above to generate cards.")
        else:
            idx = st.session_state.fc_idx % len(fc_list)
            card = fc_list[idx]
            st.markdown(f"**Card {idx + 1} of {len(fc_list)}** | Status: `{card['status']}`")

            disp_text = card["answer"] if st.session_state.fc_flip else card["question"]
            label = "ANSWER" if st.session_state.fc_flip else "QUESTION"
            st.markdown(
                f"""
                <div style="background-color: #F8FAFC; border: 2px solid #CBD5E1; border-radius: 12px; padding: 30px; text-align: center; margin: 15px 0;">
                    <small style="color: #64748B;">{label}</small>
                    <h3 style="color: #0F172A; margin-top: 10px;">{disp_text}</h3>
                </div>
                """,
                unsafe_allow_html=True
            )

            b1, b2, b3, b4 = st.columns(4)
            if b1.button("⬅️ Previous"):
                st.session_state.fc_idx = (idx - 1) % len(fc_list)
                st.session_state.fc_flip = False
                st.rerun()
            if b2.button("🔄 Flip Card"):
                st.session_state.fc_flip = not st.session_state.fc_flip
                st.rerun()
            if b3.button("✅ Mark Known"):
                cur.execute("UPDATE flashcards SET status = 'Known' WHERE id = ?", (card["id"],))
                conn.commit()
                st.session_state.fc_idx = (idx + 1) % len(fc_list)
                st.session_state.fc_flip = False
                st.rerun()
            if b4.button("⚠️ Needs Revision"):
                cur.execute("UPDATE flashcards SET status = 'Needs Revision' WHERE id = ?", (card["id"],))
                conn.commit()
                st.session_state.fc_idx = (idx + 1) % len(fc_list)
                st.session_state.fc_flip = False
                st.rerun()

    elif page == "Study Planner":
        st.title("Study Planner & Timetable 📅")
        with st.expander("➕ Add Exam Target", expanded=False):
            with st.form("plan_form"):
                subj = st.text_input("Course (e.g. Operating Systems)")
                top = st.text_input("Topic (e.g. Virtual Memory)")
                ed = st.date_input("Target Exam Date", min_value=datetime.date.today())
                mins = st.slider("Daily Available Study Time (minutes)", 15, 120, 45, 15)
                prio = st.selectbox("Priority", ["High", "Medium", "Low"], index=1)
                if st.form_submit_button("Save Target"):
                    cur.execute("INSERT INTO study_plans (user_id, subject, topic, exam_date, daily_minutes, priority) VALUES (?, ?, ?, ?, ?, ?)",
                                (user_id, subj, top, ed.strftime("%Y-%m-%d"), mins, prio))
                    conn.commit()
                    st.success("Target saved!")
                    st.rerun()

        cur.execute("SELECT id, subject, topic, exam_date, daily_minutes, priority FROM study_plans WHERE user_id = ?", (user_id,))
        plans = cur.fetchall()

        if plans:
            st.subheader("Configured Examination Targets")
            for p in plans:
                st.write(f"📖 **{p['subject']}** — *{p['topic']}* | Exam: `{p['exam_date']}` | Daily: `{p['daily_minutes']}m` | Priority: `{p['priority']}`")

            if st.button("Generate Algorithmic Schedule", type="primary"):
                cur.execute("SELECT topic, AVG(score) as s FROM quiz_attempts WHERE user_id = ? GROUP BY topic", (user_id,))
                q_map = {r["topic"].lower(): r["s"] for r in cur.fetchall()}
                sched = StudyPlanner.generate_schedule(plans, q_map)
                st.session_state.sched = sched

            if "sched" in st.session_state:
                st.subheader("Your Personalized Timetable")
                for s in st.session_state.sched:
                    st.info(f"📅 **{s['date']}** — Study **{s['subject']}** ({s['topic']}) for **{s['duration']} mins** | *{s['notes']}*")
        else:
            st.info("No exam targets added yet.")

    elif page == "Learning Analytics":
        st.title("Learning Analytics 📊")
        cur.execute("SELECT topic, AVG(score) as avg_score, COUNT(*) as attempts FROM quiz_attempts WHERE user_id = ? GROUP BY topic", (user_id,))
        stats = cur.fetchall()

        if stats:
            st.subheader("Topic Mastery Summary")
            for r in stats:
                sc = r["avg_score"]
                status = "Mastered" if sc >= 80 else ("Review Recommended" if sc >= 50 else "Critical Revision Needed")
                st.write(f"📌 **{r['topic']}**: Average Score **{sc:.1f}%** ({r['attempts']} attempts) — Status: `{status}`")
        else:
            st.info("Take quizzes to see analytics here.")

    elif page == "Settings":
        st.title("Settings & Demonstration ⚙️")
        st.write(f"Logged in as: **{user_name}** ({st.session_state.user['email']})")
        st.divider()
        if st.button("Load Sample Course Notes (Operating Systems)"):
            sample = (
                "Operating Systems: Memory Management and Virtual Memory.\n\n"
                "Virtual memory is a memory management capability of an operating system that uses hardware and software "
                "to allow a computer to compensate for physical memory shortages by temporarily transferring data from random "
                "access memory to disk storage. Paging is a memory management scheme by which a computer stores and retrieves "
                "data from secondary storage for use in main memory in same-size blocks called pages.\n\n"
                "A page fault occurs when a program attempts to access a block of memory that is not stored in physical RAM. "
                "Thrashing occurs when a computer's virtual memory subsystem is constantly paging, leading to severe performance "
                "degradation. The operating system was invented in 1956 at General Motors. Demand paging is the primary technique "
                "where pages are loaded only when requested by the executing process."
            )
            cur.execute("INSERT INTO documents (user_id, title, file_type, word_count, extracted_text) VALUES (?, ?, ?, ?, ?)",
                        (user_id, "CS201_Operating_Systems_Notes.txt", "TXT", len(sample.split()), sample))
            conn.commit()
            st.session_state.active_doc_id = cur.lastrowid
            st.success("Sample notes loaded! You can now use AI Summarizer, Chatbot, or Quiz Generator.")
            st.rerun()

    conn.close()

if __name__ == "__main__":
    main()