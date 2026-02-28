import os
import re
import json
import logging
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import fitz  # pymupdf
import pandas as pd
import pdfplumber
from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Exam Classifier POC")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR.parent / "output"
UPLOADS_DIR = BASE_DIR.parent / "uploads"
OUTPUT_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)

app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

# ---------------------------------------------------------------------------
# Gemini setup
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY not set — classification will be skipped")
    gemini_client = None

# ---------------------------------------------------------------------------
# Load taxonomy Excel files on startup (English + Chinese)
# ---------------------------------------------------------------------------
# Per-language taxonomy: lang -> { "slots_by_unit": {...}, "all_slots": [...] }
taxonomies: dict[str, dict] = {}

TAXONOMY_FILES = {
    "EN": "english index table.xlsx",
    "CH": "CHINESE index table.xlsx",
}


def _load_one_taxonomy(lang: str, filename: str):
    excel_path = BASE_DIR / filename
    if not excel_path.exists():
        logger.warning(f"Taxonomy file not found: {excel_path}")
        return
    df = pd.read_excel(excel_path, header=0, usecols="A:J")
    df.columns = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
    df = df.fillna("")
    df = df[df["A"].str.strip().ne("") & df["C"].str.strip().ne("")]

    sbu: dict[str, list[dict]] = {}
    rows: list[dict] = []
    for _, row in df.iterrows():
        entry = {col: str(row[col]).strip() for col in df.columns}
        unit_code = entry["C"]
        sbu.setdefault(unit_code, []).append(entry)
        rows.append(entry)

    taxonomies[lang] = {"slots_by_unit": sbu, "all_slots": rows}
    logger.info(f"[{lang}] Loaded {len(rows)} taxonomy rows across {len(sbu)} units")


@app.on_event("startup")
def load_taxonomy():
    for lang, filename in TAXONOMY_FILES.items():
        _load_one_taxonomy(lang, filename)


# ---------------------------------------------------------------------------
# Keyword → unit code mapping  (per language)
# ---------------------------------------------------------------------------
UNIT_KEYWORDS_EN: dict[str, list[str]] = {
    "PN": ["pronoun", "he", "she", "him", "her", "my", "mine", "myself", "yourself",
           "themselves", "hers", "ours", "yours", "theirs", "its", "it", "they", "them",
           "we", "us", "our", "his", "who", "whom", "whose", "which", "that",
           "this", "these", "those", "someone", "anyone", "everyone", "nobody",
           "somebody", "anything", "everything", "nothing", "something",
           "one another", "each other", "herself", "himself", "itself", "ourselves"],
    "VB": ["verb", "tense", "past", "present", "future", "has", "have", "had",
           "is", "are", "was", "were", "will", "would", "infinitive", "gerund",
           "participle", "modal", "can", "could", "shall", "should", "may", "might",
           "must", "do", "does", "did", "been", "being", "going to"],
    "AJ": ["adjective", "comparative", "superlative", "more", "most", "less",
           "least", "enough", "too", "big", "small", "tall", "short",
           "good", "better", "best", "bad", "worse", "worst",
           "beautiful", "ugly", "happy", "sad", "angry"],
    "DT": ["article", "determiner", "some", "any", "many", "much", "few",
           "little", "each", "both", "quantifier", "several", "all", "every",
           "no", "neither", "either", "another", "other"],
    "PP": ["preposition", "under", "above", "below", "beside",
           "between", "through", "phrasal verb", "across", "along",
           "among", "behind", "beyond", "during", "except", "into",
           "onto", "toward", "upon", "within", "without"],
    "CJ": ["conjunction", "because", "although", "therefore", "however", "but",
           "and", "or", "so", "since", "unless", "while", "whereas", "moreover",
           "furthermore", "nevertheless", "consequently", "meanwhile",
           "not only", "but also", "either or", "neither nor", "both and"],
    "NS": ["noun", "plural", "singular", "collective", "countable", "uncountable",
           "noun phrase", "compound noun", "proper noun", "common noun",
           "abstract noun", "concrete noun"],
    "AV": ["adverb", "always", "usually", "sometimes", "never", "often",
           "frequency", "manner", "degree", "rarely", "seldom", "hardly",
           "already", "yet", "still", "just", "recently", "quickly", "slowly"],
    "MS": ["proofread", "spelling", "punctuation", "capitalization", "cloze",
           "idiom", "riddle", "summary", "comprehension", "passage", "read",
           "rewrite", "correct", "error", "mistake", "fill in"],
    "PS": ["part of speech", "prefix", "suffix", "word box", "identify pos",
           "word class", "word form", "word family"],
}

UNIT_KEYWORDS_CH: dict[str, list[str]] = {
    "LU": ["語文", "運用", "文字", "詞彙", "短語", "標點", "句子", "筆畫", "筆順",
           "偏旁", "部首", "部件", "造字", "象形", "指事", "會意", "形聲",
           "詞類", "詞義", "近義", "反義", "同義", "量詞", "助詞", "嘆詞",
           "感情色彩", "褒義", "貶義", "口語", "書面語",
           "標點符號", "句號", "逗號", "問號", "感嘆號", "冒號", "引號",
           "句式", "複句", "句子成分", "主語", "謂語", "賓語",
           "錯別字", "改正", "改錯", "改寫", "填充", "填寫"],
    "RH": ["修辭", "比喻", "比擬", "擬人", "擬物", "排比", "複疊", "疊詞",
           "誇張", "反問", "設問", "對偶", "對比", "借代", "反復"],
    "DE": ["描寫", "描寫文", "人物描寫", "外貌", "動作", "神態", "心理",
           "直接描寫", "間接描寫", "正面描寫", "側面描寫",
           "觀察", "五感", "視覺", "聽覺", "嗅覺", "味覺", "觸覺",
           "動物", "植物", "食物", "景物"],
    "EX": ["說明", "說明文", "說明方法", "說明順序", "說明層次",
           "舉例", "列數字", "打比方", "作比較", "分類別", "下定義"],
    "LY": ["抒情", "抒情文", "直接抒情", "間接抒情",
           "敍景", "觸景生情", "寓情於景", "情景交融", "借事抒情", "借物抒情"],
    "AR": ["議論", "議論文", "論點", "論據", "論證",
           "立論", "駁論", "舉例論證", "引用論證", "比喻論證", "對比論證",
           "總分", "總分總"],
    "RS": ["閱讀", "閱讀策略", "理解", "關鍵字", "標題", "主旨", "段意",
           "歸納", "推論", "推斷", "概括", "中心思想", "主題"],
    "PT": ["實用文", "書信", "日記", "週記", "通告", "啟事", "啟示",
           "邀請", "感謝", "投訴", "建議", "報告", "電郵", "電子郵件",
           "守則", "規則", "說明書", "海報", "傳單", "便條"],
    "OS": ["看圖", "排句", "排列", "看圖寫作", "看圖作文",
           "順序", "重組", "組句", "排句成段"],
    "CC": ["字詞", "成語", "諺語", "歇後語", "四字詞", "慣用語",
           "供詞填充", "選詞填充", "配詞"],
    "TR": ["翻譯", "中譯英", "英譯中"],
    "WR": ["寫作", "作文", "記敘", "記敍文", "記事", "遊記", "讀後感"],
    "LI": ["聆聽", "聽力"],
    "SP": ["說話", "口語"],
}

# Build per-language keyword→unit lookup
def _build_kw_to_units(unit_kws: dict[str, list[str]]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for unit, kws in unit_kws.items():
        for kw in kws:
            mapping.setdefault(kw, []).append(unit)
    return mapping

KW_TO_UNITS_EN = _build_kw_to_units(UNIT_KEYWORDS_EN)
KW_TO_UNITS_CH = _build_kw_to_units(UNIT_KEYWORDS_CH)

LANG_KEYWORD_MAPS = {"EN": KW_TO_UNITS_EN, "CH": KW_TO_UNITS_CH}


def detect_language(text: str) -> str:
    """Detect language from text. Returns 'CH' if Chinese chars dominate, else 'EN'."""
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    return "CH" if chinese_chars > len(text) * 0.1 else "EN"


def classify_by_keywords(text: str, exercise_title: str = "", lang: str = "EN") -> list[dict]:
    """Classify by keyword matching — instant, no LLM call. Returns multiple slots."""
    combined = f"{exercise_title} {text}".lower()

    kw_map = LANG_KEYWORD_MAPS.get(lang, KW_TO_UNITS_EN)
    tax = taxonomies.get(lang, taxonomies.get("EN", {}))
    sbu = tax.get("slots_by_unit", {})

    matched_units: set[str] = set()
    matched_keywords: dict[str, list[str]] = {}
    for kw, units in kw_map.items():
        if kw in combined:
            for u in units:
                matched_units.add(u)
                matched_keywords.setdefault(u, []).append(kw)

    if not matched_units:
        return []

    result_slots: list[dict] = []
    seen_keys: set[str] = set()

    for unit_code in matched_units:
        rows = sbu.get(unit_code, [])
        kw_count = len(matched_keywords.get(unit_code, []))
        for row in rows:
            slot_key = f"{row['C']}|{row['E']}|{row['G']}"
            if slot_key in seen_keys:
                continue
            seen_keys.add(slot_key)
            confidence = min(0.6 + kw_count * 0.1, 1.0)
            slot = {**row, "confidence": round(confidence, 2)}
            result_slots.append(slot)

    result_slots.sort(key=lambda s: s["confidence"], reverse=True)
    return result_slots[:10]


# ---------------------------------------------------------------------------
# Gemini Vision: extract questions WITH bounding boxes
# ---------------------------------------------------------------------------
def extract_questions_from_image(image_path: Path, page_num: int, lang: str = "EN") -> list[dict]:
    """
    Use Gemini Vision to OCR a scanned page.
    Returns list of {no, text, page, exercise, bbox: [y_min, x_min, y_max, x_max]}.
    Bounding box coords are normalized to 0-1000 scale.
    """
    if not gemini_client:
        return []

    try:
        img = Image.open(str(image_path))

        if lang == "CH":
            prompt = """You are reading a scanned Chinese (中文) exam paper page.

Your job is to extract EVERY exercise and question on this page.

Rules:
- Each exercise/section has a title like "一、", "二、", "（一）", "第一題", "練習一", etc.
- Under each exercise there are numbered questions — numbering may use 1. 2. 3. or （1）（2）（3） or 甲、乙、丙
- Extract EVERY question — fill-in-the-blank (填充), multiple choice (選擇), rewrite (改寫), matching (配對), true/false (判斷), comprehension (閱讀理解), etc.
- Include the blank markers (______) and answer options
- Include any instructions (題目說明) as part of the exercise title
- If there are sub-questions, list each as a separate entry
- Keep all Chinese text exactly as shown — do NOT translate
- IMPORTANT: If the page contains a reading passage/article (閱讀理解/文章/短文), set "has_passage" to true and include the passage text in "passage_text"

For EACH question, also provide a bounding box [y_min, x_min, y_max, x_max] where coordinates are on a 0-1000 scale relative to the full page image. The box should tightly wrap the question text area.

Return JSON:
{
  "exercises": [
    {
      "exercise": "一、選出正確的詞語",
      "has_passage": false,
      "passage_text": "",
      "questions": [
        {"no": 1, "text": "他______地跑回家。（急忙 / 慢慢 / 快樂）", "bbox": [120, 50, 160, 950]},
        {"no": 2, "text": "媽媽買了很多______。", "bbox": [160, 50, 200, 950]}
      ]
    },
    {
      "exercise": "甲.閱讀理解",
      "has_passage": true,
      "passage_text": "在一個美麗的早晨...(full article text)...",
      "questions": [
        {"no": 1, "text": "文章的主角是誰？", "bbox": [600, 50, 640, 950]}
      ]
    }
  ]
}

If NO exercises or questions found, return: {"exercises": []}
Be thorough — do not skip any question."""
        else:
            prompt = """You are reading a scanned English exam paper page.

Your job is to extract EVERY exercise and question on this page.

Rules:
- Each exercise has a title like "Exercise 1", "Exercise 2", "EXERCISE 3", "Ex. 4", etc.
- Under each exercise there are numbered questions — numbering restarts per exercise
- Extract EVERY question — fill-in-the-blank, multiple choice, circle/underline, rewrite, matching, true/false, etc.
- Include the blank markers (______) and answer options
- Include any instructions as part of the exercise title
- If there are sub-questions (a, b, c), list each as a separate entry
- IMPORTANT: If the page contains a reading passage/article (Reading Comprehension), set "has_passage" to true and include the passage text in "passage_text"

For EACH question, also provide a bounding box [y_min, x_min, y_max, x_max] where coordinates are on a 0-1000 scale relative to the full page image. The box should tightly wrap the question text area.

Return JSON:
{
  "exercises": [
    {
      "exercise": "Exercise 1: Choose the correct pronoun",
      "has_passage": false,
      "passage_text": "",
      "questions": [
        {"no": 1, "text": "She gave ______ the book. (I / me / my)", "bbox": [120, 50, 160, 950]},
        {"no": 2, "text": "They enjoyed ______ at the party.", "bbox": [160, 50, 200, 950]}
      ]
    }
  ]
}

If NO exercises or questions found, return: {"exercises": []}
Be thorough — do not skip any question."""

        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[img, prompt],
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0,
            ),
        )
        result = json.loads(response.text)

        questions = []
        for ex in result.get("exercises", []):
            ex_title = ex.get("exercise", "")
            has_passage = ex.get("has_passage", False)
            passage_text = ex.get("passage_text", "")
            for q in ex.get("questions", []):
                questions.append({
                    "no": q.get("no", 0),
                    "text": q.get("text", ""),
                    "page": page_num,
                    "exercise": ex_title,
                    "bbox": q.get("bbox", None),
                    "has_passage": has_passage,
                    "passage_text": passage_text,
                })

        logger.info(f"Vision extracted {len(questions)} questions from page {page_num}")
        return questions

    except Exception as e:
        logger.error(f"Vision extraction error on page {page_num}: {e}")
        return []


def crop_question_image(page_image_path: Path, bbox: list, question_id: int, pdf_label: str = "") -> str | None:
    """
    Crop a question region from the full page image.
    bbox = [y_min, x_min, y_max, x_max] in 0-1000 scale.
    Returns the filename of the saved crop, or None.
    """
    if not bbox or len(bbox) != 4:
        return None

    try:
        img = Image.open(str(page_image_path))
        img_w, img_h = img.size

        y_min, x_min, y_max, x_max = bbox

        # Convert from 0-1000 normalised coords to pixel coords
        left = int(x_min * img_w / 1000)
        top = int(y_min * img_h / 1000)
        right = int(x_max * img_w / 1000)
        bottom = int(y_max * img_h / 1000)

        # Add some padding (20px each side)
        pad = 20
        left = max(0, left - pad)
        top = max(0, top - pad)
        right = min(img_w, right + pad)
        bottom = min(img_h, bottom + pad)

        # Ensure minimum height
        if bottom - top < 30:
            bottom = min(img_h, top + 60)

        cropped = img.crop((left, top, right, bottom))

        # Include pdf_label in filename to avoid collisions between uploads
        safe_label = re.sub(r"[^\w\-]", "_", pdf_label) if pdf_label else ""
        crop_filename = f"{safe_label}_q_{question_id}.png" if safe_label else f"q_{question_id}.png"
        crop_path = OUTPUT_DIR / crop_filename
        cropped.save(str(crop_path), "PNG")
        return crop_filename

    except Exception as e:
        logger.warning(f"Crop failed for question {question_id}: {e}")
        return None


# ---------------------------------------------------------------------------
# POST /upload  —  now supports multiple files
# ---------------------------------------------------------------------------
@app.post("/upload")
async def upload_exam(files: list[UploadFile] = File(...)):
    # Clean output directory to avoid stale images from previous uploads
    for old_file in OUTPUT_DIR.glob("*.png"):
        try:
            old_file.unlink()
        except OSError:
            pass

    all_questions: list[dict] = []
    global_id = 0

    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            logger.warning(f"Skipping non-PDF file: {file.filename}")
            continue

        # Save uploaded file
        upload_path = UPLOADS_DIR / file.filename
        with open(upload_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        pdf_label = Path(file.filename).stem

        # ── Step 1: Convert PDF pages to images ──
        page_image_paths: list[Path] = []
        try:
            doc = fitz.open(str(upload_path))
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                mat = fitz.Matrix(150 / 72, 150 / 72)  # 150 dpi
                pix = page.get_pixmap(matrix=mat)
                img_path = OUTPUT_DIR / f"{pdf_label}_page_{page_idx + 1}.png"
                pix.save(str(img_path))
                page_image_paths.append(img_path)
            doc.close()
            logger.info(f"[{pdf_label}] Converted {len(page_image_paths)} pages")
        except Exception as e:
            logger.warning(f"[{pdf_label}] PDF→image failed: {e}")

        # ── Step 2: Try text extraction (digital PDFs) + detect language ──
        questions: list[dict] = []
        all_text_for_lang = ""
        try:
            with pdfplumber.open(str(upload_path)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ""
                    all_text_for_lang += text
                    if text.strip():
                        current_exercise = ""
                        for line in text.split("\n"):
                            # Match English or Chinese exercise headers
                            ex_match = re.match(r"(?i)(exercise|ex\.?)\s*\d+.*", line.strip())
                            if not ex_match:
                                ex_match = re.match(r"^[一二三四五六七八九十]+[、．.].*", line.strip())
                            if ex_match:
                                current_exercise = line.strip()
                                continue
                            q_match = re.match(r"^(\d+)[\.\)、．]\s*(.+)", line.strip())
                            if not q_match:
                                q_match = re.match(r"^[（(](\d+)[)）]\s*(.+)", line.strip())
                            if q_match:
                                questions.append({
                                    "no": int(q_match.group(1)),
                                    "text": q_match.group(2).strip(),
                                    "page": page_num,
                                    "exercise": current_exercise,
                                    "bbox": None,
                                })
        except Exception as e:
            logger.warning(f"[{pdf_label}] pdfplumber error: {e}")

        # Detect language from extracted text, filename hints, or defer to OCR
        if all_text_for_lang.strip():
            pdf_lang = detect_language(all_text_for_lang)
        elif re.search(r"(?i)(ch|chinese|中文|語文)", pdf_label):
            pdf_lang = "CH"
        else:
            pdf_lang = None  # will detect after OCR
        logger.info(f"[{pdf_label}] Pre-OCR language guess: {pdf_lang}")

        # ── Step 3: Scanned PDF fallback — Gemini Vision OCR (PARALLEL) ──
        if not questions:
            logger.info(f"[{pdf_label}] No text — using Gemini Vision OCR ({len(page_image_paths)} pages in parallel)")
            if not gemini_client:
                continue

            # If language unknown, OCR first page to detect it
            if pdf_lang is None and page_image_paths:
                first_qs = extract_questions_from_image(page_image_paths[0], 1, lang="CH")
                if not first_qs:
                    first_qs = extract_questions_from_image(page_image_paths[0], 1, lang="EN")
                sample_text = " ".join(q.get("text", "") for q in first_qs)
                pdf_lang = detect_language(sample_text)
                logger.info(f"[{pdf_label}] Detected language from OCR: {pdf_lang}")
                # Keep the first page results
                questions.extend(first_qs)
                remaining_pages = page_image_paths[1:]
            else:
                remaining_pages = page_image_paths

            def _ocr_page(img_path: Path) -> list[dict]:
                pn = int(img_path.stem.split("_page_")[1])
                return extract_questions_from_image(img_path, pn, lang=pdf_lang or "EN")

            if not remaining_pages:
                remaining_pages = []
            with ThreadPoolExecutor(max_workers=max(1, min(6, len(remaining_pages)))) as pool:
                futures = {pool.submit(_ocr_page, p): p for p in remaining_pages}
                for future in as_completed(futures):
                    try:
                        questions.extend(future.result())
                    except Exception as e:
                        logger.error(f"OCR thread error: {e}")

            # Sort by page number to maintain order
            def _sort_key(q):
                try:
                    return (int(q.get("page") or 0), int(q.get("no") or 0))
                except (ValueError, TypeError):
                    return (0, 0)
            questions.sort(key=_sort_key)

        if not questions:
            logger.warning(f"[{pdf_label}] No questions found")
            continue

        # ── Step 4: Classify + crop each question, and detect passage groups ──
        if not pdf_lang:
            pdf_lang = "EN"

        # ── Detect passage-based questions and assign them to groups ──
        PASSAGE_TITLE_KW = ["閱讀理解", "reading comprehension", "comprehension",
                            "閱讀", "古文", "古詩", "文言文", "read the passage"]
        PASSAGE_TEXT_KW = ["根據文章", "從文章", "文章中", "文章第", "文中",
                          "according to the passage", "in the passage",
                          "refer to the passage", "the article"]

        # Step A: Find all named passage sections (e.g., "甲.閱讀理解", "古文知識:閱讀以下古詩")
        named_passages: list[dict] = []  # {name, pages}
        for q in questions:
            ex = q.get("exercise") or ""
            if q.get("has_passage") or any(kw in ex for kw in PASSAGE_TITLE_KW):
                # Check if we already have this named passage
                found = False
                for np in named_passages:
                    if np["name"] == ex:
                        np["pages"].add(q.get("page", 0))
                        found = True
                        break
                if not found:
                    named_passages.append({"name": ex, "pages": {q.get("page", 0)}})

        # Step B: For questions that reference an article but don't belong to a named section,
        # find the nearest named passage by page proximity
        for i, q in enumerate(questions):
            ex = q.get("exercise") or ""
            txt = q.get("text") or ""
            combined = f"{ex} {txt}"

            # Skip if already in a named passage
            if any(np["name"] == ex for np in named_passages):
                continue

            # Check if this question references an article
            if any(kw in combined for kw in PASSAGE_TEXT_KW):
                page = q.get("page", 0)
                # Find closest named passage by page distance
                best = None
                best_dist = 999
                for np in named_passages:
                    for p in np["pages"]:
                        dist = abs(page - p)
                        if dist < best_dist:
                            best_dist = dist
                            best = np
                if best and best_dist <= 3:
                    best["pages"].add(page)
                    q["_passage_group"] = best["name"]
                else:
                    # Create a new unnamed group for this page region
                    group_name = f"閱讀理解 (p.{page})"
                    named_passages.append({"name": group_name, "pages": {page}})
                    q["_passage_group"] = group_name

        # Step C: Assign all questions belonging to named passage exercises
        for q in questions:
            if "_passage_group" in q:
                continue
            ex = q.get("exercise") or ""
            for np in named_passages:
                if np["name"] == ex:
                    q["_passage_group"] = ex
                    break

        for q in questions:
            global_id += 1
            exercise = q.get("exercise") or ""
            q_text = q.get("text") or ""
            slots = classify_by_keywords(q_text, exercise, lang=pdf_lang)

            # Crop question image if we have a bbox — but NOT for passage-based exercises
            page_num = q["page"]
            page_img = OUTPUT_DIR / f"{pdf_label}_page_{page_num}.png"
            crop_file = None
            is_passage_q = "_passage_group" in q
            if q.get("bbox") and page_img.exists() and not is_passage_q:
                crop_file = crop_question_image(page_img, q["bbox"], global_id, pdf_label)

            ex_num = ""
            ex_match = re.search(r"(\d+)", exercise)
            if ex_match:
                ex_num = f"Ex{ex_match.group(1)} "
            elif pdf_lang == "CH":
                ch_num_match = re.search(r"[（(]?([一二三四五六七八九十]+)[)）、]", exercise)
                if ch_num_match:
                    cn_map = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
                              "六": "6", "七": "7", "八": "8", "九": "9", "十": "10"}
                    cn = ch_num_match.group(1)
                    ex_num = f"Ex{cn_map.get(cn, cn)} "

            all_questions.append({
                "id": global_id,
                "no": q.get("no") or 0,
                "label": f"{ex_num}Q{q.get('no') or 0}",
                "text": q_text,
                "exercise": exercise,
                "page": q["page"],
                "pdf": pdf_label,
                "lang": pdf_lang,
                "image_url": f"/output/{crop_file}" if crop_file else f"/output/{pdf_label}_page_{page_num}.png",
                "full_page_url": f"/output/{pdf_label}_page_{page_num}.png",
                "slots": slots,
                "passage_group": q.get("_passage_group") if is_passage_q else None,
                "passage_text": (q.get("passage_text") or "") if is_passage_q else "",
            })

    if not all_questions:
        raise HTTPException(status_code=422, detail="No questions detected in any uploaded PDF")

    # ── Build passage groups for the response ──
    groups: list[dict] = []
    grouped_ids: set[int] = set()
    seen_groups: dict[str, dict] = {}

    for q in all_questions:
        pg = q.get("passage_group")
        if not pg:
            continue
        grouped_ids.add(q["id"])
        if pg not in seen_groups:
            # Collect all page images for this passage group
            group_pages = sorted(set(
                qq["page"] for qq in all_questions if qq.get("passage_group") == pg
            ))
            page_urls = [f"/output/{q['pdf']}_page_{p}.png" for p in group_pages]

            # Classify the group as a whole using the exercise title + passage text
            passage_text = q.get("passage_text", "")
            group_slots = classify_by_keywords(passage_text, pg, lang=q["lang"])

            seen_groups[pg] = {
                "group_id": f"grp_{len(groups)+1}",
                "exercise": pg,
                "pdf": q["pdf"],
                "lang": q["lang"],
                "page_urls": page_urls,
                "passage_text": passage_text[:500] if passage_text else "",
                "slots": group_slots,
                "questions": [],
            }
            groups.append(seen_groups[pg])

        seen_groups[pg]["questions"].append({
            "id": q["id"],
            "no": q["no"],
            "label": q["label"],
            "text": q["text"],
            "slots": q["slots"],
        })

    # Standalone questions (not in any passage group)
    standalone = [q for q in all_questions if q["id"] not in grouped_ids]

    logger.info(f"Processed {len(all_questions)} questions ({len(groups)} passage groups, {len(standalone)} standalone) from {len(files)} file(s)")
    return {"questions": standalone, "groups": groups}


@app.get("/")
def health():
    counts = {lang: len(t["all_slots"]) for lang, t in taxonomies.items()}
    return {"status": "ok", "taxonomy_rows": counts}
