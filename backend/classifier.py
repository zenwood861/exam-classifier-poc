"""
VB/PN Classifier for English grammar exercises (P2-P6).

Classification pipeline:
  1. detect_language(text) → "EN" | "NOT_EN"
  2. detect_unit(instruction, text) → "VB" | "PN" | None
  3. detect_format(instruction, text) → format code string
  4. detect_section_and_lp(unit, instruction, text) → (E, G)
  5. estimate_grade(unit, E, G, instruction, text) → "P2"-"P6" | None
"""

import re

import pandas as pd


# ============================================================
# TAXONOMY NAME LOADING (from Excel)
# ============================================================

_vb_lp_names: dict[tuple[int, int], str] = {}
_pn_lp_names: dict[tuple[int, int], str] = {}
_sp_lp_names: dict[tuple[int, int], str] = {}


def load_taxonomy_names(excel_path: str) -> None:
    """
    Load LP (learning point) names from the English index table Excel file.

    Columns: A=subject, B=subject desc, C=unit code, D=unit name,
             E=section#, F=section name, G=LP#, H=LP name, I=format code, J=format name.

    Populates _vb_lp_names and _pn_lp_names with (E, G) -> H mappings.
    Only stores the first occurrence per (E, G) combo (the Excel has duplicate rows for each format).
    """
    global _vb_lp_names, _pn_lp_names, _sp_lp_names

    df = pd.read_excel(excel_path, header=None)
    # Skip header row
    df = df.iloc[1:]

    for _, row in df.iterrows():
        unit_code = row[2]
        if unit_code not in ("VB", "PN", "SP"):
            continue

        try:
            E = int(row[4])
            G = int(row[6])
        except (ValueError, TypeError):
            continue

        H = str(row[7]) if pd.notna(row[7]) else ""

        key = (E, G)
        if unit_code == "VB":
            if key not in _vb_lp_names:
                _vb_lp_names[key] = H
        elif unit_code == "PN":
            if key not in _pn_lp_names:
                _pn_lp_names[key] = H
        elif unit_code == "SP":
            if key not in _sp_lp_names:
                _sp_lp_names[key] = H


# ============================================================
# 1. LANGUAGE DETECTION
# ============================================================

def detect_language(text: str) -> str:
    """Returns 'EN' if English, 'NOT_EN' otherwise."""
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    total = len(text.strip())
    if total == 0:
        return "NOT_EN"
    if chinese_chars / total > 0.1:
        return "NOT_EN"
    return "EN"


# ============================================================
# 2. UNIT DETECTION (VB vs PN vs neither)
# ============================================================

# --- PN signals: pronoun-specific keywords in instruction ---
_PN_INSTRUCTION_KW = [
    r"pronoun", r"possessive\s+pronoun", r"possessive\s+adjective",
    r"reflexive\s+pronoun", r"emphatic\s+pronoun",
    r"subject\s+pronoun", r"object\s+pronoun",
    r"reciprocal", r"demonstrative",
]

# Pronoun word lists (answers/options that signal PN)
_PN_WORDS = {
    # subject
    "i", "you", "he", "she", "it", "we", "they",
    # object
    "me", "him", "her", "us", "them",
    # possessive adj
    "my", "your", "his", "its", "our", "their",
    # possessive pron
    "mine", "yours", "hers", "ours", "theirs",
    # reflexive
    "myself", "yourself", "himself", "herself", "itself",
    "ourselves", "yourselves", "themselves", "oneself",
    # demonstrative
    "this", "that", "these", "those",
}

# --- VB signals: tense/verb-specific keywords in instruction ---
_VB_INSTRUCTION_KW = [
    r"tense", r"past\s+tense", r"present\s+tense", r"future\s+tense",
    r"continuous\s+tense", r"perfect\s+tense",
    r"past\s+continuous", r"present\s+continuous", r"present\s+perfect",
    r"passive\s+(voice|form|sentence)", r"active\s+(voice|form)",
    r"active\s+to\s+passive", r"passive\s+to\s+active",
    r"conditional", r"if\s*\.\.\.\s*will", r"if\s*\.\.\.\s*would",
    r"gerund", r"infinitive", r"modal",
    r"correct\s+forms?\s+of\s+(the\s+)?verbs?",
    r"forms?\s+of\s+(the\s+)?(given\s+)?verbs?",
    r"going\s+to",
    r"using\s+.{0,5}will.{0,5}",
]

# VB answer patterns: verb forms that signal tense exercises
_VB_ANSWER_PATTERNS = [
    r"\b(was|were)\s+\w+ing\b",        # past continuous
    r"\b(is|are|am)\s+\w+ing\b",       # present continuous
    r"\b(has|have)\s+(not\s+)?\w+ed\b", # present perfect
    r"\b(has|have)\s+(not\s+)?(been|gone|done|seen|taken|written|given|eaten)\b",
    r"\bwill\s+(not\s+)?\w+\b",        # future
    r"\bwould\s+(not\s+)?\w+\b",       # conditional
    r"\b(is|are|was|were)\s+\w+ed\b",  # passive
    r"\b(is|are|was|were)\s+being\s+\w+ed\b",  # passive continuous
    r"\bgoing\s+to\s+\w+\b",           # be going to
]

# --- SP signals: sentence transformation keywords in instruction ---
_SP_INSTRUCTION_KW = [
    r"reported\s+speech", r"direct\s+.{0,10}indirect", r"indirect\s+.{0,10}direct",
    r"inversion", r"participle\s+clause", r"reduced\s+(relative\s+)?clause",
]

# SP transformation verbs — only count when paired with sentence-level tasks
_SP_TRANSFORMATION_PATTERNS = [
    r"(rewrite|convert|change)\s+.{0,30}(passive|active)",
    r"(rewrite|convert|change)\s+.{0,30}(reported|indirect|direct)\s+speech",
    r"(join|combine)\s+.{0,20}sentence",
    r"(join|combine)\s+.{0,20}(who|which|whom|whose|where|that)",
    r"(rewrite|convert)\s+.{0,20}(inversion|participle)",
    r"rewrite\s+.{0,20}using\s+(who|which|whom|whose|where)",
]


def detect_unit(instruction: str, text: str) -> str | None:
    """
    Detect whether exercise is VB, PN, SP, or neither.
    Returns 'VB', 'PN', 'SP', or None.
    """
    instr_lower = instruction.lower()
    text_lower = text.lower()
    combined = f"{instr_lower} {text_lower}"

    # --- Score PN ---
    pn_score = 0
    for pat in _PN_INSTRUCTION_KW:
        if re.search(pat, instr_lower):
            pn_score += 3

    # Count pronoun words in text AND instruction (answers/options/word box)
    all_words = set(re.findall(r"[a-z']+", combined))
    pn_word_hits = all_words & _PN_WORDS
    # Exclude very common words that overlap (his, her, it, etc.)
    _COMMON_OVERLAP = {"his", "her", "it", "i", "you", "he", "she", "we", "they",
                       "my", "your", "our", "their", "its", "this", "that", "these", "those"}
    distinctive_pn_hits = pn_word_hits - _COMMON_OVERLAP
    # If distinctive pronoun words present (mine, yours, hers, ours, theirs, myself, etc.)
    if len(distinctive_pn_hits) >= 2:
        pn_score += 4
    elif len(pn_word_hits) >= 3:
        pn_score += 2

    # Strong PN signal: instruction explicitly says "pronoun"
    if re.search(r"pronoun", instr_lower):
        pn_score += 5

    # PN signal: instruction contains a word box of pronouns
    instr_pn_words = set(re.findall(r"[a-z']+", instr_lower)) & _PN_WORDS
    instr_distinctive = instr_pn_words - _COMMON_OVERLAP
    if len(instr_distinctive) >= 3:
        pn_score += 6  # strong: word box of pronouns in instruction
    elif len(instr_pn_words) >= 5:
        # A word box of common pronouns (e.g., "I we you they he she it")
        # Even without distinctive ones, 5+ pronoun words in instruction = word box
        pn_score += 6

    # PN signal: text has pronoun options with slash (MC-style: itself / themselves)
    if re.search(r"\b(myself|yourself|himself|herself|itself|ourselves|yourselves|themselves)\s*/\s*(myself|yourself|himself|herself|itself|ourselves|yourselves|themselves)\b", text_lower):
        pn_score += 6

    # PN signal: proofreading instruction + pronoun in text
    if re.search(r"underlined\s+words?\s+are\s+wrong|proofread|correct\s+the\s+(mistake|error|underlined)", instr_lower):
        if len(distinctive_pn_hits) >= 1:
            pn_score += 4

    # --- Score VB ---
    vb_score = 0
    for pat in _VB_INSTRUCTION_KW:
        if re.search(pat, instr_lower):
            vb_score += 3

    # Check for verb form patterns in answers
    for pat in _VB_ANSWER_PATTERNS:
        if re.search(pat, combined):
            vb_score += 1

    # Strong VB signal: instruction mentions tense by name
    if re.search(r"(past|present|future|perfect|continuous|passive)\s+(simple\s+)?tense", instr_lower):
        vb_score += 5
    if re.search(r"correct\s+form\s+of\s+(the\s+)?verb", instr_lower):
        vb_score += 5
    if re.search(r"conditional|if\s*[\.\s]*will|if\s*[\.\s]*would", instr_lower):
        vb_score += 5
    if re.search(r"passive\s+voice|active\s+voice|passive\s+form|active\s+to\s+passive|passive\s+to\s+active", instr_lower):
        vb_score += 5
    if re.search(r"gerund|infinitive|bare\s+infinitive", instr_lower):
        vb_score += 5

    # VB signal from text: conditional patterns (if...will/would)
    if re.search(r"\bif\s+\w+.*\bwill\s+\w+", text_lower):
        vb_score += 4
    if re.search(r"\bif\s+\w+\s+(were|was)\b.*\bwould\b", text_lower):
        vb_score += 4

    # VB signal from text: passive patterns (is/are + past participle + by)
    if re.search(r"\b(is|are|was|were)\s+\w+(ed|en|t)\s+by\b", text_lower):
        vb_score += 4
    if re.search(r"\b(is|are)\s+made\s+(of|from|by)\b", text_lower):
        vb_score += 4

    # PN-only exercises: if instruction says "fill in with correct pronoun" etc.
    if re.search(r"(fill|complete|write).{0,30}pronoun", instr_lower):
        pn_score += 5

    # VB signal from text: multiple past tense irregular verbs (story/exercise with tenses)
    past_irreg = re.findall(r"\b(went|came|saw|took|gave|ate|met|ran|said|told|found|made|had|got|jumped|opened|heard|lived|became|fell|broke)\b", text_lower)
    if len(past_irreg) >= 3:
        vb_score += 3
    # VB signal from text: will + verb pattern (future tense)
    will_matches = re.findall(r"\bwill\s+\w+\b", text_lower)
    if len(will_matches) >= 2:
        vb_score += 3

    # VB signal from text: strong present perfect patterns (have/has + past participle)
    present_perfect_matches = len(re.findall(
        r"\b(has|have)\s+(just|already|not)?\s*(been|done|gone|seen|taken|written|given|eaten|drunk|made|had|got|said|found|lost|put|begun|become|bought|broken|brought|caught|chosen|drawn|driven|fallen|felt|flown|forgotten|grown|heard|held|hurt|kept|known|left|let|meant|met|paid|ridden|risen|sent|shaken|shown|shut|slept|spoken|spent|stood|stolen|struck|swum|taught|thrown|thought|understood|woken|won|worn|finished|washed|baked|cooked|posted|watered|cleaned|packed|\w+ed)\b",
        text_lower
    ))
    if present_perfect_matches >= 2:
        vb_score += 4
    elif present_perfect_matches >= 1:
        vb_score += 2

    # VB signal: instruction mentions just/already/yet (present perfect markers)
    if re.search(r"\bjust\b.{0,10}\balready\b|\balready\b.{0,10}\byet\b|\bjust\b.{0,10}\byet\b", instr_lower):
        vb_score += 4

    # Suppress VB for non-VB instructions mentioning "verb" loosely
    # e.g., "Write sentences using where and suitable verbs" is NOT a VB exercise
    if re.search(r"using\s+\w+\s+and\s+(suitable\s+)?verbs?\b", instr_lower):
        vb_score = max(vb_score - 5, 0)
    # Bare "verb" in instruction only counts if combined with "form", "tense", "correct"
    if re.search(r"\bverb(s)?\b", instr_lower) and not re.search(r"(form|tense|correct|given|past|present|future|continuous|perfect|passive|active)\s.{0,20}verb|verb.{0,20}(form|tense|given)", instr_lower):
        vb_score = max(vb_score - 3, 0)

    # --- Score SP ---
    sp_score = 0
    for pat in _SP_INSTRUCTION_KW:
        if re.search(pat, instr_lower):
            sp_score += 5

    for pat in _SP_TRANSFORMATION_PATTERNS:
        if re.search(pat, instr_lower):
            sp_score += 6

    # SP signal: "rewrite/convert/change" + sentence-level task (even without specific grammar keyword)
    if re.search(r"(rewrite|convert|change)\s+.{0,20}sentence", instr_lower):
        sp_score += 3

    # SP signal: "join/combine" + "relative pronoun" → sentence combination task, not PN
    if re.search(r"(join|combine)\s+.{0,30}relative\s+pronoun", instr_lower):
        sp_score += 5

    # SP suppression: if instruction says "fill in" or "circle", it's likely VB/PN not SP
    if re.search(r"fill\s+in|complete\s+the\s+blank|circle\s+the\s+correct", instr_lower):
        sp_score = max(sp_score - 8, 0)

    # All below threshold → neither
    if vb_score < 3 and pn_score < 3 and sp_score < 3:
        return None

    # SP wins if highest
    if sp_score > vb_score and sp_score > pn_score:
        return "SP"
    if vb_score > pn_score and vb_score > sp_score:
        return "VB"
    if pn_score > vb_score and pn_score > sp_score:
        return "PN"

    # Tie-breaks
    if sp_score == vb_score and sp_score > pn_score:
        # Transformation instruction → SP; otherwise VB
        if re.search(r"rewrite|convert|join|combine|change\s+.{0,15}(to|into)", instr_lower):
            return "SP"
        return "VB"
    if sp_score == pn_score and sp_score > vb_score:
        if re.search(r"rewrite|convert|join|combine", instr_lower):
            return "SP"
        return "PN"
    if vb_score == pn_score:
        return "VB" if vb_score > 0 else None

    return None


# ============================================================
# 3. FORMAT DETECTION
# ============================================================

def detect_format(instruction: str, text: str) -> str:
    """
    Detect exercise format code.
    Returns one or more codes joined with '+': MC, FB, WB+FB, SW, SQ, PR, MA, etc.

    Rules:
    - "circle"/"underline"/"choose" + options → MC
    - "fill in the blanks" + word box provided → WB+FB
    - "fill in the blanks" no words provided → FB
    - "rewrite"/"write sentences"/"change"/"complete sentences using" → SW
    - "correct"/"proofread"/"underline mistakes"/"wrong" → PR
    - "match" → MA
    - Q&A open-ended → SQ
    """
    instr_lower = instruction.lower()
    text_lower = text.lower()

    formats = []

    # --- Check for matching ---
    if re.search(r"\bmatch", instr_lower):
        formats.append("MA")

    # --- Check for proofreading ---
    if re.search(r"proofread|correct\s+(the\s+)?(mistake|error|underlined)|underlined\s+words?\s+are\s+wrong|find\s+(the\s+)?mistake|circle\s+the\s+mistake", instr_lower):
        formats.append("PR")

    # --- Check for MC (circle/underline to choose) ---
    if re.search(r"circle\s+the\s+(correct|suitable|right)|underline\s+the\s+(correct|suitable|right)|choose\s+the\s+(correct|right|suitable)\s+(word|answer|form)", instr_lower):
        if "PR" not in formats:  # don't double-tag as MC if it's proofreading
            formats.append("MC")

    # --- Check for sentence rewriting ---
    if re.search(r"(re)?write\s+(the\s+)?sentence|change\s+.{0,20}(singular|plural|active|passive)|make\s+sentence|complete\s+(the\s+)?sentence\s+using|rewrite|write\s+using|invite\s+your\s+friend|write\s+sentences\s+with\s+the", instr_lower):
        formats.append("SW")

    # --- Check for fill in blanks ---
    is_fill = bool(re.search(r"fill\s+in|complete\s+(the\s+)?(blank|sentence|conversation|passage|diary|letter|postcard|blog|email|article|report|story|entry|message|composition|card)", instr_lower))
    if not is_fill:
        # Also detect implicit fill-in: "finish the sentences with/using"
        is_fill = bool(re.search(r"finish\s+(the\s+)?sentence|put\s+.{0,10}(word|correct|suitable)\s+in", instr_lower))

    if is_fill and "MC" not in formats and "SW" not in formats:
        # Check if words are provided (word box)
        has_word_box = _has_word_box(instruction, text)
        if has_word_box:
            formats.append("WB+FB")
        else:
            formats.append("FB")

    # --- Check for short questions (Q&A, open-ended answers) ---
    if re.search(r"answer\s+the\s+question|write\s+(your\s+)?answer|open.ended|complete\s+sentences?\s+using\s+(will|would)", instr_lower):
        if not formats:  # only if nothing else matched
            formats.append("SQ")

    # If nothing matched, default to FB (most common)
    if not formats:
        # Check if it looks like fill-in by having blanks in text
        if re.search(r"_{2,}|\(\s*\)|blank", text_lower):
            formats.append("FB")
        else:
            formats.append("FB")

    return "+".join(formats)


def _has_word_box(instruction: str, text: str) -> bool:
    """
    Detect if a word box (shared word bank) is provided.
    A word box is a list of words given separately from individual questions.

    Patterns:
    - Words listed on a separate line: "do sleep listen bark read swim"
    - Words in a box/frame notation
    - Instruction mentions "words in the box" or "given words"
    - A line with 3+ base-form words separated by spaces/commas with no sentence structure
    """
    instr_lower = instruction.lower()

    # Explicit mention
    if re.search(r"word\s*(box|bank)|words?\s+in\s+the\s+box|from\s+the\s+box|given\s+words|words?\s+provided|words?\s+below|helping\s+words", instr_lower):
        return True

    # Check if instruction itself contains a word list (e.g., "theirs his hers ours mine yours")
    # Pattern: instruction has parenthesized list or slash-separated list of short words
    if re.search(r"\b(mine|yours|his|hers|ours|theirs|myself|himself|herself|itself|themselves|yourself|yourselves|ourselves)\b", instr_lower):
        # Count how many of these appear — if 3+, it's a word box
        pronoun_list = re.findall(r"\b(mine|yours|his|hers|ours|theirs|myself|himself|herself|itself|themselves|yourself|yourselves|ourselves|me|him|her|us|them|my|your|our|their|he|she|it|we|they|i|you)\b", instr_lower)
        if len(set(pronoun_list)) >= 4:
            return True

    # Check text AND instruction segments for a word-list line
    # (line with multiple base-form words, no punctuation/sentences)
    # For instructions, also split on periods to find embedded word lists
    all_segments = text.split("\n")
    for segment in instruction.split("."):
        all_segments.append(segment)
    for segment in instruction.split("\n"):
        all_segments.append(segment)

    _SENTENCE_WORDS = {"the", "a", "an", "in", "on", "at", "to", "of", "with",
                       "for", "is", "are", "was", "were", "and", "or", "but",
                       "fill", "write", "circle", "complete", "blanks", "blank",
                       "correct", "sentences", "sentence", "words", "word",
                       "tense", "form", "using", "answers"}
    for line in all_segments:
        line = line.strip()
        if not line:
            continue
        words = line.split()
        if 3 <= len(words) <= 20:
            # All short words, no sentence structure (no periods, no "the", no articles)
            if all(re.match(r"^[a-z/]+$", w.lower().strip(",")) for w in words):
                if not re.search(r"[.!?]", line):
                    # Exclude if too many common sentence/instruction words
                    lower_words = {w.lower().strip(",") for w in words}
                    sentence_overlap = lower_words & _SENTENCE_WORDS
                    if len(sentence_overlap) <= len(words) * 0.3:
                        return True

    return False


# ============================================================
# 4. SECTION (E) AND LEARNING POINT (G) DETECTION
# ============================================================

def detect_vb_section_and_lp(instruction: str, text: str) -> tuple[int, int]:
    """
    For VB unit, detect E (section) and G (learning point).
    Returns (E, G).
    """
    instr_lower = instruction.lower()
    combined = f"{instr_lower} {text.lower()}"

    # --- E=3: Conditionals ---
    # Skip conditional if instruction explicitly says "future"/"will" (future tense exercise, not conditional)
    _is_explicit_future = bool(re.search(r"future\s+tense|using\s+.{0,5}will|complete.{0,30}will", instr_lower))
    # Use sentence-level matching for if...will (don't match across sentences)
    _has_if_will_same_sentence = bool(re.search(r"\bif\s+\w+[^.!?]{0,40}\bwill\s+\w+", combined))
    _has_if_would = bool(re.search(r"\bif\s+\w+[^.!?]{0,40}\bwould\s+\w+", combined))
    if not _is_explicit_future and (
        re.search(r"conditional|if\s*[\.\s]*(will|would|might|could)|if\s+i\s+(were|was)\b|if\s+\w+\s+(were|was)\b", combined) or
        _has_if_will_same_sentence or _has_if_would
    ):
        # Detect type
        has_type1 = bool(re.search(r"if\s+\w+\s+(will|won't|might)\b|if\s+\w+\s+\w+s?,\s*\w+\s+will", combined))
        has_type2 = bool(re.search(r"if\s+\w+\s+(were|was)\b.*would|would\s+\w+\s+if|if\s+i\s+were", combined))
        has_type0 = bool(re.search(r"if\s+\w+\s+\w+s?,\s*\w+\s+\w+s?\b", combined)) and not has_type1 and not has_type2

        if has_type1 and has_type2:
            # Check if also mixed with tenses
            if _has_non_conditional_tenses(combined):
                return (3, 10)  # type 0+1+2+tenses
            return (3, 8)  # type 0+1+2
        elif has_type2:
            return (3, 3)  # type 2
        elif has_type1:
            return (3, 2)  # type 1
        elif has_type0:
            return (3, 1)  # type 0
        return (3, 2)  # default to type 1

    # --- E=7: Passive Voice ---
    _PASSIVE_PARTICIPLES = r"(written|spoken|known|called|made|done|given|taken|seen|eaten|driven|drawn|chosen|broken|stolen|worn|torn|born|shown|thrown|grown|blown|flown|frozen|hidden|ridden|risen|shaken|woken|forgotten|bitten|beaten)"
    if re.search(r"passive\s*(voice|form|sentence)|active\s+.{0,10}passive|change\s+.{0,20}passive|is\s+made\s+of|are\s+made\s+of|was\s+made\s+of|were\s+made\s+of|being\s+\w+ed\b|been\s+\w+ed\b", combined) or \
       re.search(r"\b(is|are|was|were)\s+" + _PASSIVE_PARTICIPLES + r"\s+by\b", combined):
        return _detect_passive_g(combined)

    # --- E=4: Gerund and Infinitives ---
    # Only check if instruction explicitly mentions gerund/infinitive, or if text has
    # clear gerund/infinitive patterns AND instruction doesn't mention a specific tense
    has_explicit_tense_in_instr = bool(re.search(
        r"(past|present|future|perfect|continuous)\s+(simple\s+)?tense|past\s+continuous|present\s+continuous|present\s+perfect|passive",
        instr_lower
    ))
    gerund_in_instr = bool(re.search(r"gerund|infinitive|bare\s+infinitive", instr_lower))
    gerund_in_text = bool(re.search(r"\benjoy\s+\w+ing\b|\bwant\s+to\s+\w+\b|\blet\s+\w+\s+\w+\b", combined))
    if gerund_in_instr or (gerund_in_text and not has_explicit_tense_in_instr):
        return _detect_gerund_infinitive_g(combined)

    # --- E=5: Modals ---
    if re.search(r"\bmodal\b|would\s+you\s+like\s+to|can\s+i|may\s+i|could\s+you|should\s+(not\s+)?\w+|must\s+(not\s+)?\w+|ought\s+to", instr_lower):
        return _detect_modal_g(combined)

    # --- E=1: Agreement ---
    if re.search(r"agreement|subject.verb\s+agreement|countable|uncountable", instr_lower):
        return (1, 0)

    # --- E=2: Verb Contraction ---
    if re.search(r"contraction|shorten|short\s+form", instr_lower):
        return (2, 1)

    # --- E=6: Tenses (Actives) — default for VB ---
    return _detect_active_tense_g(instruction, text)


def _has_non_conditional_tenses(text: str) -> bool:
    """Check if text contains tenses beyond just conditional structures."""
    has_present = bool(re.search(r"\b(is|are|am|do|does)\s+\w+", text))
    has_past = bool(re.search(r"\b(was|were|did)\s+\w+|\w+ed\b", text))
    has_perfect = bool(re.search(r"\b(has|have)\s+(been|done|\w+ed)\b", text))
    return sum([has_present, has_past, has_perfect]) >= 2


def _detect_passive_g(text: str) -> tuple[int, int]:
    """Detect passive voice G value."""
    _IRR_PP = r"(known|called|spoken|written|seen|done|given|taken|made|eaten|driven|drawn|chosen|broken|stolen|worn|torn|born|shown|thrown|grown|blown|flown|frozen|hidden|ridden|risen|shaken|woken|forgotten|bitten|beaten)"
    has_present = bool(re.search(r"\b(is|are)\s+\w+ed\b|\b(is|are)\s+made\b|\b(is|are)\s+" + _IRR_PP + r"\b", text))
    has_past = bool(re.search(r"\b(was|were)\s+\w+ed\b|\b(was|were)\s+made\b|\b(was|were)\s+(known|called|spoken|written|seen|done|given|taken)\b", text))
    has_future = bool(re.search(r"\bwill\s+be\s+\w+ed\b", text))
    has_cont = bool(re.search(r"\b(is|are|was|were)\s+being\s+\w+", text))
    has_perfect = bool(re.search(r"\b(has|have)\s+been\s+\w+ed\b|\b(has|have)\s+been\s+(done|made|seen|given|taken|written)\b", text))

    flags = [has_present, has_past, has_future, has_cont, has_perfect]
    count = sum(flags)

    if count >= 4:
        return (7, 8)  # present+past+will+cont.+present perfect
    if count >= 3:
        if has_present and has_past and has_future:
            return (7, 7)  # present+past+will
        return (7, 12)  # mixed
    if has_present and has_past:
        return (7, 6)  # present+past
    if has_cont:
        return (7, 4)  # present cont.
    if has_perfect:
        return (7, 5)  # present perfect
    if has_future:
        return (7, 3)  # future
    if has_past:
        return (7, 2)  # past
    if has_present:
        return (7, 1)  # present
    return (7, 12)  # mixed (default)


def _detect_gerund_infinitive_g(text: str) -> tuple[int, int]:
    """Detect gerund/infinitive G value."""
    has_gerund = bool(re.search(r"enjoy\s+\w+ing|like\s+\w+ing|love\s+\w+ing|stop\s+\w+ing|keep\s+\w+ing|finish\s+\w+ing|mind\s+\w+ing|avoid\s+\w+ing|suggest\s+\w+ing|practise\s+\w+ing", text))
    has_to_inf = bool(re.search(r"want\s+to\s+\w+|hope\s+to\s+\w+|need\s+to\s+\w+|decide\s+to\s+\w+|plan\s+to\s+\w+|agree\s+to\s+\w+|learn\s+to\s+\w+|promise\s+to\s+\w+|refuse\s+to\s+\w+", text))
    has_bare_inf = bool(re.search(r"let\s+\w+\s+\w+|make\s+\w+\s+\w+|hear\s+\w+\s+\w+|see\s+\w+\s+\w+|watch\s+\w+\s+\w+|feel\s+\w+\s+\w+", text))

    if has_gerund and has_to_inf and has_bare_inf:
        return (4, 7)  # G+TI+BI
    if has_gerund and has_to_inf:
        return (4, 4)  # G+TI
    if has_gerund and has_bare_inf:
        return (4, 5)  # G+BI
    if has_to_inf and has_bare_inf:
        return (4, 6)  # TI+BI
    if has_bare_inf:
        return (4, 3)  # BI
    if has_to_inf:
        return (4, 2)  # TI
    if has_gerund:
        return (4, 1)  # G
    return (4, 7)  # default G+TI+BI


def _detect_modal_g(text: str) -> tuple[int, int]:
    """Detect modal G value."""
    if re.search(r"would\s+you\s+like\s+to|could\s+you\s+please|can\s+you\s+please|will\s+you\s+please", text):
        return (5, 7)  # request
    if re.search(r"can\s+i|may\s+i|could\s+i", text):
        return (5, 6)  # permission
    if re.search(r"can\b|cannot\b|could\b|could\s+not\b|able\s+to\b", text):
        return (5, 1)  # can/could (ability)
    if re.search(r"should\b|ought\s+to\b", text):
        return (5, 4)  # should/ought to
    if re.search(r"must\b|must\s+not\b", text):
        return (5, 3)  # must
    if re.search(r"may\b|might\b", text):
        return (5, 2)  # may/might
    return (5, 12)  # mixed


def _detect_active_tense_g(instruction: str, text: str) -> tuple[int, int]:
    """
    Detect active tense G value by analyzing which tenses appear.
    """
    instr_lower = instruction.lower()
    combined = f"{instr_lower} {text.lower()}"

    # Check instruction for explicit tense name or present perfect markers
    # "just/already/yet" in instruction = present perfect exercise
    if re.search(r"\bjust\b.{0,15}\balready\b|\balready\b.{0,15}\byet\b|\bjust\b.{0,15}\byet\b", instr_lower):
        if re.search(r"just|already|yet", combined):
            return (6, 14)  # present perfect (just/already/yet)
    if re.search(r"present\s+perfect", instr_lower):
        if re.search(r"just|already|yet", combined):
            return (6, 14)  # present perfect (just/already/yet)
        if re.search(r"ever|never|how\s+many\s+times", combined):
            return (6, 15)  # present perfect (ever/never)
        if re.search(r"since|for", combined):
            return (6, 16)  # present perfect (since/for)
        return (6, 13)  # present perfect
    if re.search(r"past\s+continuous", instr_lower):
        return (6, 19)  # past continuous
    if re.search(r"simple\s+past|past\s+tense", instr_lower):
        return (6, 4)  # past
    if re.search(r"simple\s+present|present\s+tense", instr_lower) and not re.search(r"continuous|perfect", instr_lower):
        return (6, 1)  # present
    if re.search(r"present\s+continuous", instr_lower):
        return (6, 2)  # present continuous
    if re.search(r"future|going\s+to|using\s+.{0,5}will|sentences?\s+using\s+.{0,5}will", instr_lower):
        if re.search(r"going\s+to", instr_lower) and re.search(r"will", instr_lower):
            return (6, 9)  # be going to + will
        if re.search(r"going\s+to", instr_lower):
            return (6, 8)  # be going to
        return (6, 7)  # future (will)

    # No explicit tense in instruction — detect from answers
    tenses_found = _detect_tenses_in_text(combined)
    g = _tenses_to_g(tenses_found)

    # If present perfect was detected, check for just/already/yet/ever/never/since/for
    if "present_perfect" in tenses_found:
        if re.search(r"\bjust\b|\balready\b|\byet\b", combined):
            return (6, 14)  # present perfect (just/already/yet)
        if re.search(r"\bever\b|\bnever\b|\bhow\s+many\s+times\b", combined):
            return (6, 15)  # present perfect (ever/never)
        if re.search(r"\bsince\b|\bfor\s+\w+\s+(year|month|week|day|hour)", combined):
            return (6, 16)  # present perfect (since/for)
        # If only present perfect detected (possibly with "present" false positive from is/are)
        if tenses_found <= {"present_perfect", "present"}:
            return (6, 13)  # present perfect

    return (6, g)


def _detect_tenses_in_text(text: str) -> set[str]:
    """Detect which tenses appear in answer text."""
    tenses = set()

    # Present simple
    if re.search(r"\b(is|are|am|do|does|has|goes|comes|makes|takes|eats|drinks|plays|works|lives|studies|gets|says|tells|writes|reads|gives|runs|sings|watches|likes|needs|wants|cooks|washes|cleans|keeps|looks|rains|flows)\b", text):
        tenses.add("present")

    # Present continuous
    if re.search(r"\b(is|are|am)\s+\w+ing\b", text):
        tenses.add("present_cont")

    # Past simple
    if re.search(r"\b(was|were|did)\b|\b\w+(ed)\b|\b(went|came|saw|took|gave|ate|drank|ran|sang|wrote|read|made|had|got|said|told|found|lost|put|began|became|built|bought|broke|brought|caught|chose|drew|drove|fell|felt|flew|forgot|grew|heard|held|hurt|kept|knew|left|let|meant|met|paid|rode|rose|sent|set|shook|shot|showed|shut|slept|spoke|spent|stood|stole|struck|swam|taught|threw|thought|understood|woke|won|wore)\b", text):
        tenses.add("past")

    # Future
    if re.search(r"\bwill\s+\w+\b|\bgoing\s+to\s+\w+\b", text):
        tenses.add("future")

    # Present perfect
    if re.search(r"\b(has|have)\s+(?:\w+\s+){0,2}(been|done|gone|seen|taken|written|given|eaten|drunk|made|had|got|said|found|lost|put|begun|become|bought|broken|brought|caught|chosen|drawn|driven|fallen|felt|flown|forgotten|grown|heard|held|hurt|kept|known|left|let|meant|met|paid|ridden|risen|sent|shaken|shown|shut|slept|spoken|spent|stood|stolen|struck|swum|taught|thrown|thought|understood|woken|won|worn|borrowed|\w+ed)\b", text):
        tenses.add("present_perfect")

    # Past continuous
    if re.search(r"\b(was|were)\s+\w+ing\b", text):
        tenses.add("past_cont")

    # Past perfect
    if re.search(r"\bhad\s+(not\s+)?\w+ed\b|\bhad\s+(not\s+)?(been|done|gone|seen|taken)\b", text):
        tenses.add("past_perfect")

    return tenses


def _tenses_to_g(tenses: set[str]) -> int:
    """Map a set of detected tenses to the best matching G value."""
    t = tenses

    # Single tense
    if t == {"present"}:
        return 1
    if t == {"present_cont"}:
        return 2
    if t == {"past"}:
        return 4
    if t == {"future"}:
        return 7
    if t == {"present_perfect"}:
        return 13
    if t == {"past_cont"}:
        return 19
    if t == {"past_perfect"}:
        return 22

    # Two tenses
    if t == {"present", "present_cont"}:
        return 3
    if t == {"present", "past"}:
        return 5
    if t == {"past", "future"}:
        return 12  # past+future implies mixed tenses including future → P4
    if t == {"present_perfect", "past"}:
        return 17
    if t == {"past_cont", "past"}:
        return 20
    if t == {"past_perfect", "past"}:
        return 23

    # Three tenses
    if t == {"present", "present_cont", "past"}:
        return 6

    # Four tenses (present+cont+past+future)
    if {"present", "past", "future"} <= t and "present_perfect" not in t:
        return 12

    # Five tenses (present+cont+past+future+perfect)
    if {"present", "past", "future", "present_perfect"} <= t:
        if "past_cont" in t:
            return 21  # all 6
        return 18  # 5 tenses

    # Six+ tenses
    if {"present", "past", "future", "present_perfect", "past_cont"} <= t:
        if "past_perfect" in t:
            return 25
        return 21

    # Fallback: use count
    count = len(t)
    if count >= 5:
        return 21
    if count >= 4:
        return 18
    if count >= 3:
        return 12
    if count >= 2:
        return 5
    return 0  # Others


def detect_pn_section_and_lp(instruction: str, text: str) -> tuple[int, int]:
    """
    For PN unit, detect E (section) and G (learning point).
    Returns (E, G).
    """
    instr_lower = instruction.lower()
    combined = f"{instr_lower} {text.lower()}"

    # --- Detect word box in instruction (explicit pronoun list) ---
    _SUBJECT_SET = {"i", "you", "he", "she", "it", "we", "they"}
    _OBJECT_SET = {"me", "him", "her", "us", "them"}
    _POSS_ADJ_SET = {"my", "your", "his", "her", "its", "our", "their"}
    _POSS_PRON_SET = {"mine", "yours", "hers", "ours", "theirs"}
    _REFLEXIVE_SET = {"myself", "yourself", "himself", "herself", "itself", "ourselves", "yourselves", "themselves", "oneself"}

    instr_words = set(re.findall(r"[a-z']+", instr_lower))
    instr_subj = instr_words & _SUBJECT_SET
    instr_obj = instr_words & _OBJECT_SET
    instr_poss_adj = instr_words & _POSS_ADJ_SET
    instr_poss_pron = instr_words & _POSS_PRON_SET
    instr_reflexive = instr_words & _REFLEXIVE_SET

    # If instruction has a clear word box of one pronoun type, use that directly
    if len(instr_subj) >= 4 and len(instr_obj) == 0 and len(instr_poss_pron) == 0 and len(instr_reflexive) == 0:
        return (1, 1)  # Subject pronouns only
    # "you" overlaps subject/object; "his"/"her" overlap poss_adj/object/poss_pron
    instr_obj_only = instr_obj - {"you"}
    if len(instr_obj_only) >= 3 and len(instr_poss_pron) == 0 and len(instr_reflexive) == 0:
        return (2, 1)  # Object pronouns only
    if len(instr_poss_adj) >= 4 and len(instr_poss_pron) == 0 and len(instr_reflexive) == 0:
        return (3, 1)  # Possessive adjectives only
    if len(instr_reflexive) >= 3:
        return (5, 1)  # Reflexive pronouns

    # --- Detect which pronoun types are present ---
    has_subject = bool(re.search(r"\b(he|she|it|we|they|i|you)\b", combined)) and re.search(r"subject\s+pronoun|replace.{0,30}(he|she|it|we|they)", combined)
    has_object = bool(re.search(r"\b(me|him|her|us|them)\b", combined))
    has_poss_adj = bool(re.search(r"\b(my|your|his|her|its|our|their)\b", combined))
    has_poss_pron = bool(re.search(r"\b(mine|yours|hers|ours|theirs)\b", combined))
    has_reflexive = bool(re.search(r"\b(myself|yourself|himself|herself|itself|ourselves|yourselves|themselves|oneself)\b", combined))
    has_demonstrative = bool(re.search(r"\b(this|that|these|those)\b", combined))
    has_reciprocal = bool(re.search(r"\b(each\s+other|one\s+another)\b", combined))
    has_indefinite = bool(re.search(r"\b(someone|anyone|everyone|nobody|somebody|anybody|everybody|something|anything|everything|nothing)\b", combined))

    # --- Explicit section from instruction ---
    if re.search(r"subject\s+pronoun", instr_lower):
        return (1, 1)
    if re.search(r"object\s+pronoun", instr_lower):
        return (2, 1)
    if re.search(r"possessive\s+adjective", instr_lower):
        return (3, 1)
    if re.search(r"possessive\s+pronoun", instr_lower):
        return (4, 1)
    if re.search(r"reflexive\s+pronoun|emphatic\s+pronoun", instr_lower):
        return (5, 1)
    if re.search(r"reciprocal", instr_lower):
        return (6, 1)
    if re.search(r"indefinite\s+pronoun", instr_lower):
        return (7, 1)
    if re.search(r"demonstrative", instr_lower):
        return (8, 1)

    # --- Detect from answer content ---
    # If reflexive words dominate
    if has_reflexive and not has_poss_pron:
        if re.search(r"\b(myself|yourself|himself|herself|itself|ourselves|yourselves|themselves)\b", combined):
            # Check if also mixed with other types
            other_types = sum([has_object, has_poss_adj, has_poss_pron])
            if other_types >= 2:
                return (9, 4)  # subject+object+possessive+reflexive
            return (5, 1)

    # If possessive pronouns dominate
    if has_poss_pron and not has_reflexive:
        return (4, 1)

    # If demonstrative words in instruction
    if has_demonstrative and re.search(r"this|that|these|those", instr_lower):
        return (8, 1)

    # --- Mixed detection ---
    types_present = []
    if has_subject or re.search(r"\b(he|she|it|we|they)\b", combined):
        types_present.append("subject")
    if has_object:
        types_present.append("object")
    if has_poss_adj:
        types_present.append("poss_adj")
    if has_poss_pron:
        types_present.append("poss_pron")
    if has_reflexive:
        types_present.append("reflexive")

    if len(types_present) >= 4:
        if has_reflexive:
            return (9, 4)  # subject+object+possessive+reflexive
        return (9, 3)  # subject+object+possessive adj & pron
    if len(types_present) == 3:
        if "poss_adj" in types_present and "poss_pron" in types_present:
            return (9, 2)  # possessive adj & pron
        return (9, 3)  # subject+object+possessive adj & pron
    if len(types_present) == 2:
        if "subject" in types_present and "object" in types_present:
            return (9, 1)  # subject+object
        if "poss_adj" in types_present and "poss_pron" in types_present:
            return (9, 2)  # possessive adj & pron

    # Single type fallback
    if has_object and not has_poss_adj and not has_poss_pron:
        return (2, 1)
    if has_poss_adj and not has_object:
        return (3, 1)

    # Default: mixed
    return (9, 5)  # all mixed


# ============================================================
# 4c. SP SECTION (E) AND LEARNING POINT (G) DETECTION
# ============================================================

def detect_sp_section_and_lp(instruction: str, text: str) -> tuple[int, int]:
    """
    For SP unit, detect E (section) and G (learning point).
    Returns (E, G).

    Sections:
      1 = Relative Pronouns & Relative Clauses
      2 = Reported Speech
      3 = Passive Voice (sentence transformation)
      4 = Participles
      5 = Inversion
    """
    instr_lower = instruction.lower()
    combined = f"{instr_lower} {text.lower()}"

    # --- E=2: Reported Speech ---
    if re.search(r"reported\s+speech|direct\s+.{0,10}indirect|indirect\s+.{0,10}direct|she\s+said|he\s+said|asked\s+.{0,5}(if|whether)", combined):
        return _detect_sp_reported_speech_g(instr_lower, text.lower())

    # --- E=4: Participles (check before E=1 so "reduced relative clause" isn't caught as relative pronoun) ---
    if re.search(r"participle|reduced\s+(relative\s+)?clause", combined):
        return _detect_sp_participle_g(instr_lower, combined)

    # --- E=1: Relative Pronouns & Clauses ---
    if re.search(r"(join|combine)\s+.{0,20}(who|which|whom|whose|where|that|relative|sentence)", instr_lower) or \
       re.search(r"relative\s+(pronoun|clause)", instr_lower) or \
       re.search(r"rewrite\s+.{0,20}using\s+(who|which|whom|whose|where)", instr_lower):
        return _detect_sp_relative_g(instr_lower, combined)

    # --- E=3: Passive Voice ---
    if re.search(r"(rewrite|convert|change)\s+.{0,30}(passive|active)", instr_lower) or \
       re.search(r"passive\s+.{0,10}active|active\s+.{0,10}passive", instr_lower):
        return _detect_sp_passive_g(instr_lower, combined)

    # --- E=5: Inversion ---
    if re.search(r"inversion|so\s+(do|does|did|am|is|are|was|were|have|has|had|can|will|would)\s+\w+|neither\s+(do|does|did|am|is|are|was|were|have|has|had|can|will|would)\s+\w+", combined):
        return _detect_sp_inversion_g(combined)

    # Default: passive voice (most common SP)
    return (3, 0)


def _detect_sp_reported_speech_g(instruction: str, text: str) -> tuple[int, int]:
    """Detect reported speech G value."""
    # Indirect → direct (reverse direction)
    if re.search(r"indirect\s+.{0,10}direct|reported\s+.{0,10}direct", instruction):
        return (2, 7)

    # Detect from text content
    has_command = bool(re.search(r'"\s*(close|open|sit|stand|stop|don\'t|do\s+not|come|go|bring|take|give|put|clean|wash|finish|be\s+quiet)\b', text, re.IGNORECASE))
    has_question = bool(re.search(r'"\s*(where|when|what|who|how|why|do\s+you|did\s+you|are\s+you|is\s+there|can\s+you|will\s+you|have\s+you)\b.*\?"', text, re.IGNORECASE))
    has_statement = bool(re.search(r'(?:^|[\s(])"\s*(i\s+(am|was|have|had|will|like|love|want|need|think)|she\s+\w+|he\s+\w+|we\s+\w+|they\s+\w+|it\s+is|there\s+is)\b', text, re.IGNORECASE))

    types = sum([has_command, has_question, has_statement])
    if types >= 3:
        return (2, 6)  # command+statement+question
    if has_command and has_statement:
        return (2, 4)  # command+statement
    if has_statement and has_question:
        return (2, 5)  # statement+question
    if has_command:
        return (2, 1)
    if has_statement:
        return (2, 2)
    if has_question:
        return (2, 3)
    return (2, 2)  # default statement


def _detect_sp_relative_g(instruction: str, combined: str) -> tuple[int, int]:
    """Detect relative pronoun G value based on which pronouns are mentioned."""
    has_who = bool(re.search(r"\bwho\b", combined))
    has_which = bool(re.search(r"\bwhich\b", combined))
    has_whom = bool(re.search(r"\bwhom\b", combined))
    has_whose = bool(re.search(r"\bwhose\b", combined))
    has_where = bool(re.search(r"\bwhere\b", combined))
    has_prep = bool(re.search(r"\bwith\s+prep|prepositional|in\s+which|at\s+which|for\s+which|to\s+which", combined))

    # With preposition combos
    if has_prep:
        if has_who or has_which or has_whom:
            return (1, 11)  # mixed + with prep
        return (1, 10)  # with prep only

    # Count pronouns mentioned
    pronouns = [has_who, has_which, has_whom, has_whose, has_where]
    count = sum(pronouns)

    if count >= 4:
        return (1, 9)  # mixed

    # Specific combos
    if has_who and has_which and has_where and has_whose:
        return (1, 8)
    if has_who and has_which and has_whose:
        return (1, 7)
    if has_who and has_which and has_where:
        return (1, 6)
    if has_who and has_whom and has_whose:
        return (1, 5)
    if has_who and has_whom and has_which:
        return (1, 4)
    if has_who and has_whose:
        return (1, 3)
    if has_who and has_whom:
        return (1, 2)
    if has_who and has_which:
        return (1, 1)

    if count >= 2:
        return (1, 9)  # mixed
    return (1, 9)  # default mixed (can't tell from instruction alone)


def _detect_sp_passive_g(instruction: str, combined: str) -> tuple[int, int]:
    """Detect SP passive voice G value — maps to SP's 33 G values."""
    # Check for explicit conversion exercise
    if re.search(r"(active\s+to\s+passive\s+.{0,10}passive\s+to\s+active|passive\s+to\s+active\s+.{0,10}active\s+to\s+passive|change\s+.{0,10}(active|passive)\s+.{0,10}(active|passive))", instruction):
        return (3, 32)  # conversion

    if re.search(r"question", instruction):
        return (3, 31)  # question forms

    # Detect tenses in text to map to G
    _IRR_PP = r"(known|called|spoken|written|seen|done|given|taken|made|eaten|driven|drawn|chosen|broken|stolen|worn|torn|born|shown|thrown|grown|blown|flown|frozen|hidden|ridden|risen|shaken|woken|forgotten|bitten|beaten)"
    has_present = bool(re.search(r"\b(is|are)\s+\w+ed\b|\b(is|are)\s+made\b|\b(is|are)\s+" + _IRR_PP + r"\b", combined)) or \
                  bool(re.search(r"\b(marks?|makes?|builds?|writes?|eats?|cleans?|washes?|reads?|gives?|takes?|plays?)\b", combined) and not re.search(r"\b(was|were|had|did)\b", combined))
    has_past = bool(re.search(r"\b(was|were)\s+\w+ed\b|\b(was|were)\s+" + _IRR_PP + r"\b", combined)) or \
               bool(re.search(r"\b(chased|opened|closed|finished|watched|cleaned|washed|cooked|built|wrote|ate|gave|took|made|broke|stole|drove|drew|chose)\b", combined))
    has_future = bool(re.search(r"\bwill\s+be\s+\w+ed\b|\bwill\s+be\s+" + _IRR_PP + r"\b", combined))
    has_present_cont = bool(re.search(r"\b(is|are)\s+being\s+\w+", combined))
    has_past_cont = bool(re.search(r"\b(was|were)\s+being\s+\w+", combined))
    has_present_perfect = bool(re.search(r"\b(has|have)\s+been\s+\w+ed\b|\b(has|have)\s+been\s+" + _IRR_PP + r"\b", combined))
    has_past_perfect = bool(re.search(r"\bhad\s+been\s+\w+ed\b|\bhad\s+been\s+" + _IRR_PP + r"\b", combined))

    flags = [has_present, has_past, has_future, has_present_cont, has_past_cont, has_present_perfect, has_past_perfect]
    count = sum(flags)

    if count >= 5:
        return (3, 30)  # all tenses
    if has_present and has_present_cont and has_past and has_future and has_present_perfect and has_past_cont:
        return (3, 21)
    if has_present and has_present_cont and has_past and has_future and has_present_perfect:
        return (3, 18)
    if has_present and has_present_cont and has_past and has_future:
        return (3, 12)
    if has_present_perfect and has_past:
        return (3, 17)
    if has_past_perfect and has_past:
        return (3, 23)
    if has_past_cont and has_past:
        return (3, 20)
    if has_present and has_past:
        return (3, 5)
    if has_present and has_present_cont:
        return (3, 3)
    if has_present_cont:
        return (3, 2)
    if has_past_cont:
        return (3, 19)
    if has_past_perfect:
        return (3, 22)
    if has_present_perfect:
        return (3, 13)
    if has_future:
        return (3, 7)
    if has_past:
        return (3, 4)
    if has_present:
        return (3, 1)
    return (3, 0)  # Others


def _detect_sp_participle_g(instruction: str, combined: str) -> tuple[int, int]:
    """Detect SP participle G value."""
    if re.search(r"reduced\s+(relative\s+)?clause", combined):
        return (4, 6)  # reduced relative clause
    if re.search(r"perfect\s+participle", combined):
        return (4, 5)  # perfect participles
    if re.search(r"feeling|\bbore[d]?\b|\bboring\b|\bexcite[d]?\b|\bexciting\b|\binterest(ed|ing)?\b|\btire[d]?\b|\btiring\b|\bamaze[d]?\b|\bamazing\b", combined):
        if re.search(r"cause|effect|result", combined):
            return (4, 2)  # cause and effect
        return (4, 1)  # feeling
    if re.search(r"active\s+.{0,10}passive|passive\s+.{0,10}active", combined):
        return (4, 3)  # active and passive participles
    if re.search(r"cause\s+.{0,10}effect|effect\s+.{0,10}cause", combined):
        return (4, 2)  # cause and effect
    return (4, 7)  # mixed


def _detect_sp_inversion_g(combined: str) -> tuple[int, int]:
    """Detect SP inversion G value."""
    has_so_neither = bool(re.search(r"\bso\s+(do|does|did|am|is|are|was|were|have|has|had|can|will|would)\b|\bneither\s+(do|does|did|am|is|are|was|were|have|has|had|can|will|would)\b", combined))
    has_negative_adv = bool(re.search(r"\b(never|rarely|seldom|hardly|barely|no\s+sooner|not\s+only|at\s+no\s+time|on\s+no\s+account|under\s+no\s+circumstances)\b", combined))
    has_conditional = bool(re.search(r"\b(had\s+I|were\s+I|should\s+you|had\s+he|were\s+he|had\s+she|were\s+she|had\s+they|were\s+they)\b", combined))

    types = sum([has_so_neither, has_negative_adv, has_conditional])
    if types >= 2:
        return (5, 5)  # mixed
    if has_conditional:
        return (5, 4)
    if has_negative_adv:
        return (5, 2)
    if has_so_neither:
        return (5, 1)
    return (5, 5)  # default mixed


# ============================================================
# 5. GRADE ESTIMATION
# ============================================================

def estimate_grade(unit: str, E: int, G: int, instruction: str, text: str) -> str | None:
    """
    Estimate grade level P2-P6 from taxonomy classification and content.
    Returns 'P2', 'P3', 'P4', 'P5', 'P6', or None if can't determine.
    """
    instr_lower = instruction.lower()
    combined = f"{instr_lower} {text.lower()}"

    if unit == "VB":
        return _grade_from_vb(E, G, combined)
    elif unit == "PN":
        return _grade_from_pn(E, G, combined, instr_lower)
    elif unit == "SP":
        return _grade_from_sp(E, G, combined)
    return None


def _grade_from_vb(E: int, G: int, text: str) -> str:
    """Grade estimation for VB exercises."""

    # --- P6-only topics ---
    if E == 3:  # Conditionals
        return "P6"
    if E == 7:  # Passive voice
        return "P6"
    if E == 4:  # Gerund and Infinitives (advanced)
        # P2 has like + gerund/infinitive (very basic)
        if G == 1 and re.search(r"like\s+\w+ing|like\s+to\s+\w+", text):
            return "P2"
        return "P6"
    if E == 5:  # Modals
        # Basic modals (can) appear in P3-P4
        if G in (1, 5):  # can/ability
            return "P4"
        return "P6"

    # --- E=6: Tenses (Actives) — grade depends on which tenses ---
    if E == 6:
        # Past continuous → P5+
        if G == 19:  # past cont only
            if re.search(r"present\s+perfect|has\s+\w+ed|have\s+\w+ed", text):
                return "P6"
            return "P5"  # could be P5 or P6
        if G in (20, 21):  # past cont + other
            return "P5"  # P5 introduces past cont

        # Present perfect → P5+
        if G in (13, 14, 15, 16, 17):
            return "P5"

        # Mixed 5+ tenses → P5 or P6
        if G in (18, 25, 27, 31):
            # P6 has more complex mixing; P5 introduces this
            if re.search(r"conditional|passive|if\s+.*will|gerund|infinitive", text):
                return "P6"
            return "P5"

        # Future tense (will) → P4+
        if G in (7, 8, 9, 10, 11):
            return "P4"

        # Present + past + future mixed → P4
        if G == 12:
            if re.search(r"present\s+perfect|has\s+\w+ed|have\s+\w+ed", text):
                return "P5"
            return "P4"

        # Past tense only → P3+
        if G == 4:
            # P3 first introduces past tense
            # P4+ also uses it but typically mixed
            if re.search(r"once\s+upon\s+a\s+time|story|diary", text):
                return "P3"
            return "P3"

        # Present + past → P3
        if G in (5, 6):
            return "P3"

        # Present simple only → P2 or P3
        if G == 1:
            return "P3"  # P3 has more structured present simple

        # Present continuous only → P2 or P3
        if G == 2:
            return "P2"

        # Present + present continuous → P2 or P3
        if G == 3:
            return "P3"

        return "P4"  # default for other G values

    return "P5"  # default


def _grade_from_pn(E: int, G: int, text: str, instruction: str = "") -> str:
    """Grade estimation for PN exercises."""

    # --- E=5: Reflexive → P4+ ---
    if E == 5:
        if re.search(r"emphatic", text):
            return "P6"
        if re.search(r"singular.{0,20}plural|change.{0,20}plural", text):
            return "P6"
        # Word box with reflexive words listed in instruction → P4 (basic)
        # No word box → P5 (student must choose reflexive pronoun from context)
        reflexive_in_instr = re.findall(
            r"\b(myself|ourselves|herself|themselves|himself|itself|yourself|yourselves)\b",
            instruction,
        )
        if len(reflexive_in_instr) >= 3:
            return "P4"
        return "P5"

    # --- E=4: Possessive Pronouns → P4+ ---
    if E == 4:
        # P5: possessive pronouns in conversation/complex contexts
        poss_pron_words = set(re.findall(r"\b(mine|yours|hers|his|ours|theirs)\b", text))
        if len(poss_pron_words) >= 4:
            return "P5"
        return "P4"  # first introduced in P4

    # --- E=8: Demonstratives → P4 ---
    if E == 8:
        return "P4"

    # --- E=9: Mixed Pronouns ---
    if E == 9:
        if G >= 4:  # includes reflexive
            return "P6"
        if G == 3:
            return "P5"
        if G == 2:
            return "P5"
        return "P4"

    # --- E=1: Subject Pronouns → P2 ---
    if E == 1:
        return "P2"

    # --- E=2: Object Pronouns → P2 ---
    if E == 2:
        return "P2"

    # --- E=3: Possessive Adjectives → P2 or P3 ---
    if E == 3:
        # Basic word-box exercise ("put one of the following") → P2
        if re.search(r"put\s+one\s+of\s+the\s+following", text):
            return "P2"
        return "P3"

    # --- E=6: Reciprocal → P5+ ---
    if E == 6:
        return "P5"

    # --- E=7: Indefinite → P5+ ---
    if E == 7:
        return "P5"

    return "P4"  # default


def _grade_from_sp(E: int, G: int, text: str) -> str:
    """Grade estimation for SP exercises."""
    if E == 1:  # Relative Pronouns & Clauses
        # Basic who/which → P4; whom/whose → P5; with prep → P6
        if G in (1, 2):  # who+which, who+whom
            return "P4"
        if G in (3, 4, 5, 6, 7, 8, 9):  # more complex combos
            return "P5"
        if G in (10, 11):  # with preposition
            return "P6"
        return "P5"  # default

    if E == 2:  # Reported Speech
        return "P6"

    if E == 3:  # Passive Voice
        return "P6"

    if E == 4:  # Participles
        return "P6"

    if E == 5:  # Inversion
        return "P6"

    return "P6"  # default for SP


# ============================================================
# 6. MAIN CLASSIFICATION FUNCTION
# ============================================================

def classify_exercise(instruction: str, text: str) -> dict:
    """
    Full classification pipeline for a single exercise.

    Returns dict with:
      - language: 'EN' or 'NOT_EN'
      - unit: 'VB', 'PN', or None (not VB/PN)
      - E: section number (int)
      - F: section name (str)
      - G: learning point number (int)
      - H: learning point name (str)
      - I: format code (str)
      - grade: 'P2'-'P6' or None
      - confidence: float 0-1
    """
    # Step 1: Language
    lang = detect_language(f"{instruction} {text}")
    if lang == "NOT_EN":
        return {
            "language": "NOT_EN",
            "unit": None,
            "unit_name": None,
            "E": None, "F": None,
            "G": None, "H": None,
            "I": None, "J": None,
            "grade": None,
            "confidence": 0.9,
            "reason": "Not English text",
        }

    # Step 2: Unit
    unit = detect_unit(instruction, text)
    if unit is None:
        return {
            "language": "EN",
            "unit": None,
            "unit_name": None,
            "E": None, "F": None,
            "G": None, "H": None,
            "I": None, "J": None,
            "grade": None,
            "confidence": 0.7,
            "reason": "Not VB, PN, or SP exercise",
        }

    # Step 3: Format
    fmt = detect_format(instruction, text)

    # Step 4: Section + Learning Point
    if unit == "VB":
        E, G = detect_vb_section_and_lp(instruction, text)
    elif unit == "SP":
        E, G = detect_sp_section_and_lp(instruction, text)
    else:
        E, G = detect_pn_section_and_lp(instruction, text)

    # Step 5: Grade
    grade = estimate_grade(unit, E, G, instruction, text)

    # Look up names from taxonomy constants
    F = _section_name(unit, E)
    H = _lp_name(unit, E, G)

    return {
        "language": "EN",
        "unit": unit,
        "unit_name": {"VB": "Verb Tense", "PN": "Pronouns", "SP": "Sentence Patterns"}.get(unit, unit),
        "E": E, "F": F,
        "G": G, "H": H,
        "I": fmt, "J": _format_name(fmt),
        "grade": grade,
        "confidence": 0.8,
        "reason": None,
    }


# ============================================================
# TAXONOMY NAME LOOKUPS
# ============================================================

_VB_SECTIONS = {
    1: "Agreement",
    2: "Verb Contraction",
    3: "Conditionals",
    4: "Gerund and Infinitives",
    5: "Modals",
    6: "Tenses (Actives)",
    7: "Tenses (Passive)",
}

_PN_SECTIONS = {
    1: "Subject Pronouns",
    2: "Object Pronouns",
    3: "Possessive Adjectives",
    4: "Possessive Pronouns",
    5: "Reflexive Pronouns",
    6: "Reciprocal Pronouns",
    7: "Indefinite Pronouns",
    8: "Demonstratives",
    9: "Mixed Pronouns",
}

_SP_SECTIONS = {
    1: "Relative Pronouns & Relative Clauses",
    2: "Reported Speech",
    3: "Passive Voice",
    4: "Participles",
    5: "Inversion",
}

_FORMAT_NAMES = {
    "MC": "Multiple choices",
    "FB": "Fill in the Blanks",
    "WB+FB": "Word box + Fill in the Blanks",
    "SW": "Sentences rewriting",
    "SQ": "Short questions",
    "PR": "Proofreading",
    "MA": "Matching",
    "WB+FB+MA": "Word box + Fill in the Blanks + Matching",
    "TA": "Table",
    "TF": "True or False",
}


def _section_name(unit: str, E: int) -> str:
    if unit == "VB":
        return _VB_SECTIONS.get(E, f"Section {E}")
    if unit == "SP":
        return _SP_SECTIONS.get(E, f"Section {E}")
    return _PN_SECTIONS.get(E, f"Section {E}")


def _lp_name(unit: str, E: int, G: int) -> str:
    """Look up learning point name from taxonomy dicts loaded by load_taxonomy_names()."""
    key = (E, G)
    if unit == "VB":
        name = _vb_lp_names.get(key)
    elif unit == "SP":
        name = _sp_lp_names.get(key)
    else:
        name = _pn_lp_names.get(key)
    if name:
        return name
    return f"G={G}"


def _format_name(fmt: str) -> str:
    # Handle compound formats like "WB+FB+MA"
    parts = fmt.split("+")
    names = [_FORMAT_NAMES.get(p, p) for p in parts]
    if fmt in _FORMAT_NAMES:
        return _FORMAT_NAMES[fmt]
    return " + ".join(names)
