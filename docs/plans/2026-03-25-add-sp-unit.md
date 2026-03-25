# Add SP (Sentence Patterns) Unit — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add SP (Sentence Patterns) as a third classifiable English grammar unit alongside VB and PN, with format-aware disambiguation to handle overlapping grammar topics.

**Architecture:** Hybrid approach — teach Gemini the SP taxonomy + disambiguation rules in the prompt, then apply format-aware rule overrides as safety net. The key insight: SP = sentence-level transformation (rewrite/convert/join), VB = word-level morphology (fill in verb form), PN = word-level substitution (fill in pronoun).

**Tech Stack:** Python, FastAPI, regex, Gemini 2.0 Flash, pytest

---

### Task 1: Add SP score to unit detection (classifier.py)

**Files:**
- Modify: `backend/classifier.py:82-268` (unit detection section)
- Create: `backend/tests/test_sp_unit_detection.py`

**Step 1: Write the failing tests**

Create `backend/tests/__init__.py` (empty) and `backend/tests/test_sp_unit_detection.py`:

```python
"""Tests for SP unit detection in classifier.py."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from classifier import detect_unit


class TestSPUnitDetection:
    """SP should win when instruction indicates sentence transformation."""

    def test_rewrite_passive(self):
        assert detect_unit("Rewrite the sentences in passive voice.", "") == "SP"

    def test_convert_passive(self):
        assert detect_unit("Convert the following sentences from active to passive.", "") == "SP"

    def test_join_relative_pronoun(self):
        assert detect_unit("Join the sentences using who or which.", "") == "SP"

    def test_combine_relative_clause(self):
        assert detect_unit("Combine the sentences using a relative pronoun.", "") == "SP"

    def test_reported_speech(self):
        assert detect_unit("Change the sentences into reported speech.", "") == "SP"

    def test_direct_indirect(self):
        assert detect_unit("Change the following from direct to indirect speech.", "") == "SP"

    def test_inversion(self):
        assert detect_unit("Rewrite the sentences using inversion.", "") == "SP"

    def test_participle_clause(self):
        assert detect_unit("Rewrite the sentences using participle clauses.", "") == "SP"


class TestVBStillWinsForFillIn:
    """VB should still win for fill-in-the-blank verb exercises."""

    def test_fill_passive_form(self):
        assert detect_unit("Fill in the blanks with the correct passive form.", "") == "VB"

    def test_passive_tense_fill(self):
        assert detect_unit("Fill in the blanks with the correct form of the verbs. Use passive voice.", "") == "VB"

    def test_past_tense(self):
        assert detect_unit("Fill in the blanks with the past tense.", "") == "VB"

    def test_conditional(self):
        assert detect_unit("Finish the sentences with the correct form of the verbs.", "If it rains, we will stay home.") == "VB"


class TestPNStillWinsForPronouns:
    """PN should still win for pronoun substitution exercises."""

    def test_fill_pronoun(self):
        assert detect_unit("Fill in the blanks with the correct pronoun.", "") == "PN"

    def test_pronoun_word_box(self):
        assert detect_unit("Fill in the blanks. (theirs his hers ours mine yours)", "") == "PN"

    def test_reflexive_mc(self):
        assert detect_unit("Circle the correct words.", "itself / themselves") == "PN"
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_sp_unit_detection.py -v`
Expected: All `TestSPUnitDetection` tests FAIL (detect_unit returns "VB" or None, not "SP"). VB/PN tests may pass already.

**Step 3: Add SP keywords and scoring to `detect_unit()`**

In `backend/classifier.py`, add SP instruction keywords after the PN/VB keyword lists (around line 120):

```python
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
```

Then in `detect_unit()`, add SP scoring after the VB scoring block (before the decision logic at line 257):

```python
    # --- Score SP ---
    sp_score = 0
    for pat in _SP_INSTRUCTION_KW:
        if re.search(pat, instr_lower):
            sp_score += 5

    for pat in _SP_TRANSFORMATION_PATTERNS:
        if re.search(pat, instr_lower):
            sp_score += 6

    # SP signal: "rewrite/convert" + sentence-level task (even without specific grammar keyword)
    if re.search(r"(rewrite|convert|change)\s+.{0,20}sentence", instr_lower):
        sp_score += 3

    # SP suppression: if instruction says "fill in" or "circle", it's likely VB/PN not SP
    if re.search(r"fill\s+in|complete\s+the\s+blank|circle\s+the\s+correct", instr_lower):
        sp_score = max(sp_score - 8, 0)
```

Update the decision logic (replace lines 257-267):

```python
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
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_sp_unit_detection.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/classifier.py backend/tests/__init__.py backend/tests/test_sp_unit_detection.py
git commit -m "feat: add SP unit detection with transformation-based scoring"
```

---

### Task 2: Add SP section & LP detection (classifier.py)

**Files:**
- Modify: `backend/classifier.py` (add new functions after PN section detection)
- Create: `backend/tests/test_sp_section_lp.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_sp_section_lp.py`:

```python
"""Tests for SP section and learning point detection."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from classifier import detect_sp_section_and_lp


class TestSPReportedSpeech:
    def test_reported_speech_statement(self):
        E, G = detect_sp_section_and_lp("Change the sentences into reported speech.", '"I am happy," she said.')
        assert E == 2
        assert G == 2  # statement

    def test_reported_speech_command(self):
        E, G = detect_sp_section_and_lp("Change the sentences into reported speech.", '"Close the door," he said.')
        assert E == 2
        assert G == 1  # command

    def test_reported_speech_question(self):
        E, G = detect_sp_section_and_lp("Change the sentences into reported speech.", '"Where are you going?" she asked.')
        assert E == 2
        assert G == 3  # question

    def test_direct_to_indirect(self):
        E, G = detect_sp_section_and_lp("Change the following from direct to indirect speech.", "")
        assert E == 2

    def test_indirect_to_direct(self):
        E, G = detect_sp_section_and_lp("Change the following from indirect to direct speech.", "")
        assert E == 2
        assert G == 7  # indirect→direct


class TestSPRelativePronouns:
    def test_join_who_which(self):
        E, G = detect_sp_section_and_lp("Join the sentences using who or which.", "")
        assert E == 1
        assert G == 1  # who, which

    def test_join_whom(self):
        E, G = detect_sp_section_and_lp("Join the sentences using who or whom.", "")
        assert E == 1
        assert G == 2  # who, whom

    def test_combine_relative_pronoun(self):
        E, G = detect_sp_section_and_lp("Combine the sentences using a relative pronoun.", "")
        assert E == 1
        assert G == 9  # mixed (no specific pronoun named)


class TestSPPassiveVoice:
    def test_rewrite_passive_present(self):
        E, G = detect_sp_section_and_lp(
            "Rewrite the sentences in passive voice.",
            "The teacher marks the homework."
        )
        assert E == 3
        assert G == 1  # present

    def test_convert_passive_past(self):
        E, G = detect_sp_section_and_lp(
            "Convert the following sentences from active to passive.",
            "The dog chased the cat."
        )
        assert E == 3
        assert G == 4  # past

    def test_rewrite_passive_conversion(self):
        E, G = detect_sp_section_and_lp(
            "Rewrite the sentences in passive voice. Change active to passive and passive to active.",
            ""
        )
        assert E == 3
        assert G == 32  # conversion


class TestSPParticiples:
    def test_participle_clause(self):
        E, G = detect_sp_section_and_lp("Rewrite the sentences using participle clauses.", "")
        assert E == 4

    def test_reduced_relative_clause(self):
        E, G = detect_sp_section_and_lp("Rewrite using reduced relative clauses.", "")
        assert E == 4
        assert G == 6  # reduced clause

    def test_feeling_participle(self):
        E, G = detect_sp_section_and_lp(
            "Fill in with the correct participle.",
            "The movie was ______ (bore). I felt ______ (bore)."
        )
        assert E == 4
        assert G == 1  # feeling


class TestSPInversion:
    def test_inversion_so_neither(self):
        E, G = detect_sp_section_and_lp(
            "Rewrite the sentences using inversion.",
            "I like pizza. So do I."
        )
        assert E == 5
        assert G == 1  # so/neither

    def test_inversion_negative_adverb(self):
        E, G = detect_sp_section_and_lp(
            "Rewrite using inversion.",
            "He never goes out. Never does he go out."
        )
        assert E == 5
        assert G == 2  # negative adverb
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_sp_section_lp.py -v`
Expected: FAIL with "cannot import name 'detect_sp_section_and_lp'"

**Step 3: Implement `detect_sp_section_and_lp()` and helpers**

Add to `backend/classifier.py` after the `detect_pn_section_and_lp()` function (after line ~822):

```python
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

    # --- E=1: Relative Pronouns & Clauses ---
    if re.search(r"(join|combine)\s+.{0,20}(who|which|whom|whose|where|that|relative|sentence)", instr_lower) or \
       re.search(r"relative\s+(pronoun|clause)", instr_lower) or \
       re.search(r"rewrite\s+.{0,20}using\s+(who|which|whom|whose|where)", instr_lower):
        return _detect_sp_relative_g(instr_lower, combined)

    # --- E=3: Passive Voice ---
    if re.search(r"(rewrite|convert|change)\s+.{0,30}(passive|active)", instr_lower) or \
       re.search(r"passive\s+.{0,10}active|active\s+.{0,10}passive", instr_lower):
        return _detect_sp_passive_g(instr_lower, combined)

    # --- E=4: Participles ---
    if re.search(r"participle|reduced\s+(relative\s+)?clause", combined):
        return _detect_sp_participle_g(instr_lower, combined)

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
    has_statement = bool(re.search(r'"\s*(i\s+(am|was|have|had|will|like|love|want|need|think)|she|he|we|they|it\s+is|there\s+is)\b', text, re.IGNORECASE))

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
    if re.search(r"feeling|bored|boring|excited|exciting|interested|interesting|tired|tiring|amazed|amazing", combined):
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
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_sp_section_lp.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/classifier.py backend/tests/test_sp_section_lp.py
git commit -m "feat: add SP section and learning point detection"
```

---

### Task 3: Add SP grade estimation (classifier.py)

**Files:**
- Modify: `backend/classifier.py` (grade estimation section, lines ~825-987)
- Create: `backend/tests/test_sp_grade.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_sp_grade.py`:

```python
"""Tests for SP grade estimation."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from classifier import estimate_grade


class TestSPGrades:
    def test_relative_basic_p4(self):
        # SP S1 basic who/which → P4
        assert estimate_grade("SP", 1, 1, "", "") == "P4"

    def test_relative_advanced_p5(self):
        # SP S1 with whom/whose → P5
        assert estimate_grade("SP", 1, 5, "", "") == "P5"

    def test_relative_with_prep_p6(self):
        # SP S1 with preposition → P6
        assert estimate_grade("SP", 1, 10, "", "") == "P6"

    def test_reported_speech_p6(self):
        assert estimate_grade("SP", 2, 2, "", "") == "P6"

    def test_passive_voice_p6(self):
        assert estimate_grade("SP", 3, 1, "", "") == "P6"

    def test_participles_p6(self):
        assert estimate_grade("SP", 4, 1, "", "") == "P6"

    def test_inversion_p6(self):
        assert estimate_grade("SP", 5, 1, "", "") == "P6"
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_sp_grade.py -v`
Expected: FAIL (estimate_grade returns None for SP)

**Step 3: Add SP grade logic**

In `backend/classifier.py`, modify `estimate_grade()` to handle SP:

```python
def estimate_grade(unit: str, E: int, G: int, instruction: str, text: str) -> str | None:
    instr_lower = instruction.lower()
    combined = f"{instr_lower} {text.lower()}"

    if unit == "VB":
        return _grade_from_vb(E, G, combined)
    elif unit == "PN":
        return _grade_from_pn(E, G, combined, instr_lower)
    elif unit == "SP":
        return _grade_from_sp(E, G, combined)
    return None
```

Add the `_grade_from_sp` function:

```python
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
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_sp_grade.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/classifier.py backend/tests/test_sp_grade.py
git commit -m "feat: add SP grade estimation"
```

---

### Task 4: Wire SP into classify_exercise() and taxonomy loading (classifier.py)

**Files:**
- Modify: `backend/classifier.py` (main function + taxonomy loading)
- Create: `backend/tests/test_sp_classify.py`

**Step 1: Write the failing test**

Create `backend/tests/test_sp_classify.py`:

```python
"""Tests for full SP classification pipeline."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from classifier import classify_exercise


class TestSPFullClassification:
    def test_rewrite_passive(self):
        result = classify_exercise(
            "Rewrite the sentences in passive voice.",
            "The teacher marks the homework."
        )
        assert result["unit"] == "SP"
        assert result["E"] == 3  # Passive voice
        assert result["grade"] == "P6"
        assert result["language"] == "EN"

    def test_join_relative(self):
        result = classify_exercise(
            "Join the sentences using who or which.",
            "The man is tall. He lives next door."
        )
        assert result["unit"] == "SP"
        assert result["E"] == 1  # Relative Pronouns

    def test_reported_speech(self):
        result = classify_exercise(
            "Change the sentences into reported speech.",
            '"I am happy," she said.'
        )
        assert result["unit"] == "SP"
        assert result["E"] == 2  # Reported Speech

    def test_vb_fill_passive_still_vb(self):
        """Passive fill-in should remain VB, not SP."""
        result = classify_exercise(
            "Fill in the blanks with the correct passive form.",
            "The cake ______ (eat) by the children."
        )
        assert result["unit"] == "VB"

    def test_pn_fill_still_pn(self):
        """Pronoun fill-in should remain PN, not SP."""
        result = classify_exercise(
            "Fill in the blanks with the correct pronoun.",
            "This is my book. It is ______."
        )
        assert result["unit"] == "PN"
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_sp_classify.py -v`
Expected: FAIL (classify_exercise returns unit=None or VB for SP exercises)

**Step 3: Update `classify_exercise()`, taxonomy loading, and section names**

In `classifier.py`, update `load_taxonomy_names()` (around line 25) to load SP:

```python
_vb_lp_names: dict[tuple[int, int], str] = {}
_pn_lp_names: dict[tuple[int, int], str] = {}
_sp_lp_names: dict[tuple[int, int], str] = {}


def load_taxonomy_names(excel_path: str) -> None:
    global _vb_lp_names, _pn_lp_names, _sp_lp_names

    df = pd.read_excel(excel_path, header=None)
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
```

Add SP section names (after `_PN_SECTIONS`):

```python
_SP_SECTIONS = {
    1: "Relative Pronouns & Relative Clauses",
    2: "Reported Speech",
    3: "Passive Voice",
    4: "Participles",
    5: "Inversion",
}
```

Update `_section_name()`:

```python
def _section_name(unit: str, E: int) -> str:
    if unit == "VB":
        return _VB_SECTIONS.get(E, f"Section {E}")
    if unit == "SP":
        return _SP_SECTIONS.get(E, f"Section {E}")
    return _PN_SECTIONS.get(E, f"Section {E}")
```

Update `_lp_name()`:

```python
def _lp_name(unit: str, E: int, G: int) -> str:
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
```

Update `classify_exercise()` main function — the decision at lines ~1024-1065:

```python
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

    # Look up names
    F = _section_name(unit, E)
    H = _lp_name(unit, E, G)

    unit_names = {"VB": "Verb Tense", "PN": "Pronouns", "SP": "Sentence Patterns"}

    return {
        "language": "EN",
        "unit": unit,
        "unit_name": unit_names.get(unit, unit),
        "E": E, "F": F,
        "G": G, "H": H,
        "I": fmt, "J": _format_name(fmt),
        "grade": grade,
        "confidence": 0.8,
        "reason": None,
    }
```

**Step 4: Run all tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/classifier.py backend/tests/test_sp_classify.py
git commit -m "feat: wire SP into full classification pipeline"
```

---

### Task 5: Update Gemini prompt with SP taxonomy (main.py)

**Files:**
- Modify: `backend/main.py:205-261` (VB_PN_TAXONOMY string)

**Step 1: No test needed** (Gemini integration is tested manually)

**Step 2: Update the taxonomy prompt**

Rename `VB_PN_TAXONOMY` to `TAXONOMY_PROMPT` and update the content in `backend/main.py`:

```python
TAXONOMY_PROMPT = """
You are classifying English grammar exercises for Primary 2-6 students.

TAXONOMY (columns A, C, E, G, I):
  A = "EN" (English)

  C = Unit code:
    VB = Verb Tense (verb FORM exercises — fill in correct tense/form)
    PN = Pronouns (pronoun SUBSTITUTION exercises — fill in correct pronoun)
    SP = Sentence Patterns (sentence TRANSFORMATION exercises — rewrite/convert/join)

  DISAMBIGUATION RULES (critical — apply these BEFORE classifying):
  - "Rewrite/convert/join/combine sentences" → SP (sentence transformation)
  - "Fill in the blank with correct form/tense" → VB (verb morphology)
  - "Fill in the blank with correct pronoun" → PN (pronoun substitution)
  - Passive voice + rewrite/convert → SP S3, NOT VB S7
  - Passive voice + fill in blank → VB S7, NOT SP S3
  - Relative pronouns + join/combine sentences → SP S1, NOT PN
  - Relative pronouns + fill in blank → PN, NOT SP S1
  - Reported speech (direct↔indirect) → always SP S2
  - Participle clauses/phrases → SP S4; gerund/infinitive form choice → VB S4
  - Inversion with so/neither/negative adverbs → SP S5; regular if-conditionals → VB S3

  VB sections (E):
    1 = Agreement
    2 = Verb Contraction
    3 = Conditionals (G: 1=type 0, 2=type 1, 3=type 2, 10=mixed types)
    4 = Gerund and Infinitives (G: 1=gerund, 2=to-infinitive, 3=both, 7=G+TI+BI mixed)
    5 = Modals (G: 1=can, 5=ability, 7=request, 12=mixed)
    6 = Tenses Actives:
        G=1 present simple, G=2 present continuous, G=3 present+present cont,
        G=4 past simple, G=5 present+past, G=6 present+present cont+past,
        G=7 future (will), G=8 future (going to), G=9 future (will+going to),
        G=12 present+past+future mixed, G=13 present perfect,
        G=14 present perfect (just/already/yet), G=15 present perfect (ever/never),
        G=17 present perfect+past, G=18 5-tense mix (present+cont+past+future+perfect),
        G=19 past continuous, G=20 past cont+past, G=21 6-tense mix (+past cont),
        G=22 past perfect, G=23 past perfect+past, G=25 all tenses,
        G=27 present+past+future+present perfect+past cont+past perfect,
        G=31 all tenses + conditionals
    7 = Tenses Passive:
        G=1 present, G=4 present cont, G=6 present+past, G=8 mixed passive, G=12 mixed

  PN sections (E):
    1 = Subject Pronouns (I, you, he, she, it, we, they)
    2 = Object Pronouns (me, you, him, her, it, us, them)
    3 = Possessive Adjectives (my, your, his, her, its, our, their)
    4 = Possessive Pronouns (mine, yours, his, hers, ours, theirs)
    5 = Reflexive Pronouns (myself, yourself, himself, herself, itself, ourselves, yourselves, themselves)
    6 = Reciprocal (each other, one another)
    7 = Indefinite (someone, anyone, everyone, nobody, something, etc.)
    8 = Demonstratives (this, that, these, those)
    9 = Mixed Pronouns (G: 1=subject+object, 2=+possessive adj, 3=+possessive pron, 4=+reflexive, 5=all)

  SP sections (E):
    1 = Relative Pronouns & Relative Clauses:
        G=1 who+which, G=2 who+whom, G=3 who+whose, G=4 who+whom+which,
        G=5 who+whom+whose, G=6 who+which+where, G=7 who+which+whose,
        G=8 who+which+where+whose, G=9 mixed relative pronouns,
        G=10 with preposition, G=11 mixed+with prep
    2 = Reported Speech:
        G=1 command, G=2 statement, G=3 question,
        G=4 command+statement, G=5 statement+question,
        G=6 command+statement+question, G=7 indirect→direct
    3 = Passive Voice (sentence transformation):
        G=1 present, G=2 present cont, G=3 present+present cont,
        G=4 past, G=5 present+past, G=7 future (will),
        G=12 present+cont+past+future, G=13 present perfect,
        G=17 present perfect+past, G=18 5-tense mix,
        G=19 past cont, G=20 past cont+past, G=21 6-tense mix,
        G=22 past perfect, G=23 past perfect+past,
        G=30 all tenses, G=31 question, G=32 conversion, G=33 causative+impersonal
    4 = Participles:
        G=1 feeling, G=2 cause and effect, G=3 active and passive,
        G=4 feeling+cause+active/passive, G=5 perfect participles,
        G=6 reduced relative clause, G=7 mixed
    5 = Inversion:
        G=1 so/neither, G=2 negative adverbs,
        G=3 so/neither+negative adverbs, G=4 conditionals, G=5 mixed

  I = Format code:
    FB = Fill in the Blanks (no words given)
    WB+FB = Word box + Fill in the Blanks (words provided to choose from)
    MC = Multiple Choice / Circle the correct answer
    SW = Sentence rewriting / Complete sentences
    SQ = Short questions / Q&A
    PR = Proofreading (find/correct errors)
    MA = Matching

  Grade estimation (for reference):
    P2: present simple, present continuous, subject pronouns, object pronouns, basic possessive adj
    P3: past simple, present+past, possessive adjectives in context
    P4: future tense (will/going to), possessive pronouns, reflexive pronouns (basic), demonstratives, present+past+future mixed, relative pronouns (basic who/which)
    P5: present perfect, past continuous, mixed 5+ tenses, reciprocal, indefinite pronouns, relative pronouns (advanced)
    P6: conditionals, passive voice, gerund/infinitives, emphatic pronouns, mixed all tenses, reported speech, participles, inversion, passive rewriting
"""
```

Also update the prompt template in `classify_exercise_with_gemini()` to use `TAXONOMY_PROMPT` and accept "SP" as a valid unit:

Change the prompt at line ~276:
```python
    prompt = f"""{TAXONOMY_PROMPT}

Now classify this exercise:

Exercise title/instruction: {exercise_title}
Sample questions:
{sample_qs}

Think step by step:
1. Is this an English exercise? If not, return language="NOT_EN"
2. Is this about Verb Tense (VB), Pronouns (PN), or Sentence Patterns (SP)? Apply the disambiguation rules. If none, return unit="SKIP"
3. Which section (E) and learning point (G) best matches?
4. What is the exercise format (I)?
5. What grade level (P2-P6) does this correspond to?

Return JSON only (no markdown):
{{"language": "EN or NOT_EN", "unit": "VB or PN or SP or SKIP", "E": number, "E_name": "section name", "G": number, "G_name": "learning point name", "format": "format code", "format_name": "format name", "grade": "P2-P6", "reasoning": "brief explanation"}}
"""
```

**Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: add SP taxonomy and disambiguation rules to Gemini prompt"
```

---

### Task 6: Update rule overrides to be format-aware (main.py)

**Files:**
- Modify: `backend/main.py:311-352` (rule override section in `classify_exercise_with_gemini`)

**Step 1: No unit test** (integration behavior — tested manually with Gemini)

**Step 2: Replace the override logic**

In `classify_exercise_with_gemini()`, replace the rule override section (lines 311-352):

```python
    # ── Rule-based overrides ──
    # Format-aware: transformation instructions protect SP from being overridden
    combined_text = " ".join(question_texts[:8])
    overrides: list[str] = []

    instr_lower = exercise_title.lower()
    llm_unit = result.get("unit")

    # Detect if instruction is a transformation task (SP territory)
    is_transformation = bool(re.search(
        r"rewrite|convert|change\s+.{0,20}(to|into)|join\s+.{0,20}sentence|combine\s+.{0,20}sentence|"
        r"direct\s+.{0,10}indirect|indirect\s+.{0,10}direct|reported\s+speech|"
        r"inversion|participle\s+clause",
        instr_lower
    ))

    # Detect if instruction is a fill-in task (VB/PN territory)
    is_fill_in = bool(re.search(
        r"fill\s+in|complete\s+the\s+blank|circle\s+the\s+correct|choose\s+the\s+correct",
        instr_lower
    ))

    rule_unit = rule_detect_unit(exercise_title, combined_text)

    # Override 1: Unit detection — format-aware
    if rule_unit and llm_unit != rule_unit:
        if is_transformation and llm_unit == "SP":
            # Gemini says SP + instruction is transformation → trust Gemini, don't override
            pass
        elif is_transformation and rule_unit == "SP" and llm_unit != "SP":
            # Rules say SP + instruction is transformation → override to SP
            result["unit"] = "SP"
            overrides.append(f"unit→SP (transformation instruction)")
        elif is_fill_in:
            # Fill-in exercise → trust rule-based VB/PN detection
            if rule_unit == "PN" and re.search(r"pronoun", instr_lower):
                result["unit"] = "PN"
                overrides.append(f"unit→PN (fill-in + instruction says 'pronoun')")
            elif rule_unit == "VB" and re.search(r"tense|verb|passive|conditional|gerund|infinitive|modal", instr_lower):
                result["unit"] = "VB"
                overrides.append(f"unit→VB (fill-in + instruction says tense/verb keyword)")
        elif not is_transformation:
            # Non-transformation, non-fill-in: use original override logic
            if rule_unit == "PN" and re.search(r"pronoun", instr_lower):
                result["unit"] = "PN"
                overrides.append(f"unit→PN (instruction says 'pronoun')")
            elif rule_unit == "VB" and re.search(r"tense|verb|passive|conditional|gerund|infinitive|modal", instr_lower):
                result["unit"] = "VB"
                overrides.append(f"unit→VB (instruction says tense/verb keyword)")

    # Override 2: Format detection — unchanged
    rule_fmt = rule_detect_format(exercise_title, combined_text)
    llm_fmt = result.get("format", "")
    if rule_fmt and rule_fmt != llm_fmt:
        if "MC" in rule_fmt and re.search(r"circle|underline\s+the\s+correct|choose\s+the\s+correct", instr_lower):
            result["format"] = rule_fmt
            overrides.append(f"format→{rule_fmt} (circle/choose instruction)")
        elif "WB+FB" in rule_fmt and re.search(r"word\s*(box|bank)|from\s+the\s+box|given\s+words", instr_lower):
            result["format"] = rule_fmt
            overrides.append(f"format→{rule_fmt} (word box detected)")
        elif "PR" in rule_fmt and re.search(r"proofread|underlined\s+words?\s+are\s+wrong|correct\s+the\s+(mistake|error)", instr_lower):
            result["format"] = rule_fmt
            overrides.append(f"format→{rule_fmt} (proofreading instruction)")
        elif "SW" in rule_fmt and re.search(r"rewrite|write\s+(the\s+)?sentence|change\s+.*?(active|passive)", instr_lower):
            result["format"] = rule_fmt
            overrides.append(f"format→{rule_fmt} (rewrite instruction)")

    if overrides:
        result["overrides"] = overrides
        logger.info(f"Rule overrides applied: {overrides}")
```

**Step 3: Update keyword map to include SP**

In `UNIT_KEYWORDS_EN` (around line 107), add SP:

```python
    "SP": ["rewrite", "convert", "reported speech", "direct speech", "indirect speech",
           "join sentences", "combine sentences", "relative clause",
           "inversion", "participle clause", "reduced clause",
           "active to passive", "passive to active"],
```

**Step 4: Update references from `VB_PN_TAXONOMY` to `TAXONOMY_PROMPT`**

Search and replace the one reference at line 276.

**Step 5: Commit**

```bash
git add backend/main.py
git commit -m "feat: format-aware rule overrides and SP keyword map"
```

---

### Task 7: Run full test suite and manual smoke test

**Step 1: Run all unit tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: ALL PASS

**Step 2: Start the server and test manually**

Run: `cd backend && uvicorn main:app --reload`

Test with a sample PDF or text input that contains:
- A passive rewrite exercise → should classify as SP S3
- A passive fill-in exercise → should classify as VB S7
- A "join sentences using who/which" → should classify as SP S1
- A "fill in the correct pronoun" → should classify as PN
- A reported speech exercise → should classify as SP S2

**Step 3: Commit any fixes**

```bash
git add -u
git commit -m "fix: address issues found in smoke testing"
```

---

### Task 8: Update classifier-architecture.md

**Files:**
- Modify: `docs/classifier-architecture.md`

**Step 1: Update the doc** to reflect the new SP support — add SP sections to unit detection, section/LP detection, grade estimation, and remove the "Key Observations for Adding SP" section (it's done now).

**Step 2: Commit**

```bash
git add docs/classifier-architecture.md
git commit -m "docs: update architecture doc with SP support"
```
