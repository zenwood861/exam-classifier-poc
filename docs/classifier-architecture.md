# Classifier Architecture (as of 2026-03-25)

This documents the full classification system for English grammar exercises.
Two files handle classification: `backend/main.py` (Gemini + orchestration) and `backend/classifier.py` (rule-based).

---

## Overall Pipeline

There are **two classification paths** that run in parallel:

### Path 1: Gemini LLM (primary) — `main.py:classify_exercise_with_gemini()`
1. Sends exercise title + up to 8 sample questions to Gemini 2.0 Flash
2. Gemini classifies: language, unit, E (section), G (LP), format, grade
3. **Format-aware rule overrides** correct Gemini when high-confidence signals exist:
   - Unit override (format-aware): detects if instruction is a transformation (rewrite/convert/join → SP territory) or fill-in (VB/PN territory) before overriding
   - If transformation + Gemini says SP → trust Gemini; if transformation + rules say SP but Gemini doesn't → override to SP
   - If fill-in + "pronoun" → force PN; if fill-in + "tense/verb/passive" → force VB
   - Format override: instruction says "circle/choose" → force MC; "word box" → force WB+FB; "proofread/underlined wrong" → force PR; "rewrite/write sentence" → force SW

### Path 2: Rule-based (fallback) — `classifier.py:classify_exercise()`
Pure regex/keyword scoring, no LLM. Used as a fast fallback and for override signals.

### Path 3: Keyword-only — `main.py:classify_by_keywords()`
Loose keyword matching against all 15 English units (not just VB/PN). Returns top-10 candidate taxonomy slots with confidence scores. Used for broad unit detection.

---

## Gemini Prompt Structure (main.py)

The `TAXONOMY_PROMPT` string is a structured taxonomy reference injected into every Gemini call. It contains:
- Unit codes: VB, PN, SP with descriptions distinguishing form vs substitution vs transformation
- **Disambiguation rules** (critical): 10 rules that tell Gemini how to differentiate overlapping topics (e.g., passive voice + rewrite → SP S3, passive voice + fill in → VB S7)
- Full VB section/LP breakdown (E=1-7 with all G values)
- Full PN section/LP breakdown (E=1-9 with all G values)
- Full SP section/LP breakdown (E=1-5 with all G values)
- Format codes: FB, WB+FB, MC, SW, SQ, PR, MA
- Grade estimation guidelines (P2-P6, now including SP topics)

Gemini is asked to think step-by-step, apply disambiguation rules, and return JSON with: language, unit (VB/PN/SP/SKIP), E, E_name, G, G_name, format, format_name, grade, reasoning.

---

## Rule-Based Classifier Detail (classifier.py)

### Step 1: Language Detection (`detect_language`)
- Counts Chinese characters vs total length
- >10% Chinese → NOT_EN

### Step 2: Unit Detection (`detect_unit`) — Scoring System
Three parallel scores computed: `vb_score`, `pn_score`, and `sp_score`.

**PN scoring signals:**
| Signal | Points |
|--------|--------|
| PN keyword in instruction (pronoun, possessive pronoun, reflexive, etc.) | +3 each |
| Instruction explicitly says "pronoun" | +5 |
| 2+ distinctive pronoun words (mine, yours, hers, myself, etc.) | +4 |
| 3+ any pronoun words in text | +2 |
| 3+ distinctive pronoun words in instruction (word box) | +6 |
| 5+ any pronoun words in instruction (word box) | +6 |
| Reflexive pronoun MC options (itself/themselves) | +6 |
| Proofreading instruction + distinctive pronoun in text | +4 |
| "fill/complete/write...pronoun" in instruction | +5 |

**VB scoring signals:**
| Signal | Points |
|--------|--------|
| VB keyword in instruction (tense, past tense, passive voice, etc.) | +3 each |
| Verb form patterns in text (was+ing, has+ed, will+verb, etc.) | +1 each |
| Instruction mentions tense by name ("past simple tense") | +5 |
| "correct form of verb" in instruction | +5 |
| Conditional keywords in instruction | +5 |
| Passive/active voice in instruction | +5 |
| Gerund/infinitive in instruction | +5 |
| Conditional patterns in text (if...will, if...would) | +4 |
| Passive patterns in text (is/are + ed + by) | +4 |
| 3+ past irregular verbs in text | +3 |
| 2+ "will + verb" in text | +3 |
| 2+ present perfect patterns in text | +4 |
| just/already/yet cluster in instruction | +4 |

**VB suppression:**
- "using X and suitable verbs" → -5 (not a VB exercise)
- Bare "verb" without context (form/tense/correct) → -3

**SP scoring signals:**
| Signal | Points |
|--------|--------|
| SP instruction keyword (reported speech, direct/indirect, inversion, participle clause, reduced clause) | +5 each |
| SP transformation pattern (rewrite/convert/change + passive/active/reported speech; join/combine + sentence/relative pronouns) | +6 each |
| Generic "rewrite/convert/change...sentence" | +3 |
| "join/combine...relative pronoun" (to beat PN's "pronoun" boost) | +5 |

**SP suppression:**
- "fill in" / "complete the blank" / "circle the correct" → -8

**Decision:**
- All three < 3 → None
- Highest score wins (SP > VB > PN in case of three-way tie)
- SP-VB tie: transformation instruction → SP, otherwise VB
- SP-PN tie: transformation instruction → SP, otherwise PN
- VB-PN tie → VB

### Step 3: Format Detection (`detect_format`)
Priority-ordered pattern matching:
1. MA: "match" in instruction
2. PR: "proofread/correct mistake/underlined wrong/find mistake"
3. MC: "circle the correct/underline the correct/choose the correct"
4. SW: "rewrite sentence/change to active-passive/make sentence/write sentences with"
5. WB+FB: "fill in" + word box detected (via `_has_word_box()`)
6. FB: "fill in" without word box
7. SQ: "answer the question" (only if nothing else matched)
8. Default: FB

**Word box detection (`_has_word_box`):**
- Explicit mention: "word box/bank", "words in the box", "given words"
- Pronoun word list in instruction (4+ distinctive or 5+ any)
- Text line scan: 3-20 short words, no sentence structure, <30% common words

### Step 4: Section & Learning Point Detection

#### VB: `detect_vb_section_and_lp()` — checked in this order:
1. **E=3 Conditionals**: if...will/would patterns (unless instruction says "future tense")
   - Type 0: if+present, +present (no will/would)
   - Type 1: if+present, will
   - Type 2: if+were/was, would
   - Mixed: type 1+2, or with other tenses
2. **E=7 Passive**: "passive voice/form", "active to passive", "is made of", "being+ed", "been+ed", or "is/are/was/were + irregular PP + by"
   - Sub-detection by tense: present/past/future/continuous/perfect → maps to G=1-12
3. **E=4 Gerund/Infinitive**: explicit "gerund/infinitive" in instruction, or enjoy+ing/want+to patterns (only if no explicit tense mentioned)
   - G=1 gerund, G=2 to-infinitive, G=3 bare infinitive, G=4-7 combos
4. **E=5 Modals**: "modal", "would you like to", "can I", "may I", etc.
   - G mapped by modal type: can→ability, should→advice, must→obligation, etc.
5. **E=1 Agreement**: "agreement/countable/uncountable"
6. **E=2 Contraction**: "contraction/shorten/short form"
7. **E=6 Tenses Active (default)**: falls through to tense detection
   - `_detect_tenses_in_text()`: regex patterns for present/past/future/present_cont/past_cont/present_perfect/past_perfect
   - `_tenses_to_g()`: maps tense combinations to G values (1-31)
   - Special handling: present perfect with just/already/yet → G=14; ever/never → G=15; since/for → G=16

#### PN: `detect_pn_section_and_lp()` — checked in this order:
1. **Word box detection**: counts pronoun types in instruction
   - 4+ subject pronouns only → E=1
   - 3+ object pronouns only → E=2
   - 4+ possessive adjectives only → E=3
   - 3+ reflexive pronouns → E=5
2. **Explicit section from instruction**: "subject pronoun" → E=1, "object pronoun" → E=2, etc.
3. **Answer content detection**: which pronoun types appear in combined text
   - Reflexive dominant → E=5
   - Possessive pronouns dominant → E=4
   - Demonstrative in instruction → E=8
4. **Mixed detection**: count pronoun types present
   - 4+ types → E=9 G=4 (includes reflexive) or G=3
   - 3 types → E=9 G=3
   - 2 types → E=9 G=1 (subj+obj) or G=2 (poss adj+pron)
5. **Single type fallback**: object → E=2, poss adj → E=3
6. **Default**: E=9 G=5 (all mixed)

#### SP: `detect_sp_section_and_lp()` — checked in this order:
1. **E=2 Reported Speech**: "reported speech", "direct/indirect", "she said/he said"
   - G by type: command(1), statement(2), question(3), combos(4-6), indirect→direct(7)
2. **E=4 Participles** (checked before E=1 so "reduced relative clause" routes here): "participle clause", "reduced clause", feeling words (bored/boring/excited/exciting)
   - G=1 feeling, G=2 cause/effect, G=3 active/passive, G=5 perfect, G=6 reduced clause, G=7 mixed
3. **E=1 Relative Pronouns & Clauses**: "join/combine...who/which/whom/whose/where/relative/sentence"
   - G by which pronouns: who+which(1), who+whom(2), ..., mixed(9), with prep(10-11)
4. **E=3 Passive Voice**: "rewrite/convert/change...passive/active"
   - Tense detection maps to G=1-30, G=31 question, G=32 conversion
5. **E=5 Inversion**: "inversion", "so do I", "neither do", negative adverbs
   - G=1 so/neither, G=2 negative adverbs, G=4 conditionals, G=5 mixed
6. **Default**: E=3 G=0 (passive, most common SP)

### Step 5: Grade Estimation (`estimate_grade`)

#### VB grades:
| Section | Grade |
|---------|-------|
| E=3 Conditionals | P6 |
| E=7 Passive | P6 |
| E=4 Gerund/Infinitive | P6 (except like+gerund → P2) |
| E=5 Modals (can/ability) | P4 |
| E=5 Modals (other) | P6 |
| E=6 G=2 present continuous | P2 |
| E=6 G=1 present simple | P3 |
| E=6 G=3 present+cont | P3 |
| E=6 G=4-6 past/mixed | P3 |
| E=6 G=7-12 future/mixed | P4 |
| E=6 G=13-17 present perfect | P5 |
| E=6 G=19-21 past continuous | P5 |
| E=6 G=18,25,27,31 complex mix | P5-P6 |

#### PN grades:
| Section | Grade |
|---------|-------|
| E=1 Subject | P2 |
| E=2 Object | P2 |
| E=3 Possessive Adj | P2-P3 |
| E=4 Possessive Pron | P4-P5 |
| E=5 Reflexive | P4-P5 (word box=P4, no box=P5) |
| E=6 Reciprocal | P5 |
| E=7 Indefinite | P5 |
| E=8 Demonstrative | P4 |
| E=9 Mixed G≥4 | P6 |
| E=9 Mixed G=2-3 | P5 |
| E=9 Mixed G=1 | P4 |

#### SP grades:
| Section | Grade |
|---------|-------|
| E=1 Relative Pronouns G=1-2 (basic who/which, who/whom) | P4 |
| E=1 Relative Pronouns G=3-9 (advanced combos) | P5 |
| E=1 Relative Pronouns G=10-11 (with preposition) | P6 |
| E=2 Reported Speech | P6 |
| E=3 Passive Voice | P6 |
| E=4 Participles | P6 |
| E=5 Inversion | P6 |

---

## Keyword Map (main.py) — Broad Unit Detection

`UNIT_KEYWORDS_EN` maps keywords to 11 English unit codes:
- **SP**: rewrite, convert, reported speech, direct/indirect speech, join/combine sentences, relative clause, inversion, participle clause, active to/from passive
- **PN**: pronoun words, relative pronouns (who/whom/whose/which), demonstratives, indefinites
- **VB**: verb/tense words, auxiliaries, modals, "going to"
- **AJ**: adjective, comparative, superlative
- **DT**: article, determiner, quantifiers
- **PP**: preposition, phrasal verb, spatial words
- **CJ**: conjunction, linking words
- **NS**: noun, plural, singular, countable/uncountable
- **AV**: adverb, frequency words
- **MS**: proofread, spelling, punctuation, comprehension
- **PS**: part of speech, prefix, suffix

---

## SP-VB-PN Disambiguation (implemented)

The core disambiguation principle: **instruction task type determines unit**.

| Instruction pattern | Unit | Why |
|---|---|---|
| Rewrite/convert/join/combine sentences | SP | Sentence-level transformation |
| Fill in blank with correct form/tense | VB | Word-level verb morphology |
| Fill in blank with correct pronoun | PN | Word-level pronoun substitution |

### Overlap zones and how they're resolved:
- **Passive voice**: "rewrite in passive" → SP S3; "fill in passive form" → VB S7
- **Relative pronouns**: "join sentences using who/which" → SP S1; "fill in who/which" → PN
- **Participles**: "rewrite using participle clauses" → SP S4; "gerund or infinitive?" → VB S4
- **Reported speech**: always SP S2 (unique transformation type)
- **Inversion + conditionals**: "rewrite using inversion" → SP S5; "if...will" → VB S3

This is enforced at three levels:
1. **Gemini prompt**: disambiguation rules tell the LLM what to look for
2. **Rule-based scoring**: SP suppressed by -8 for fill-in instructions
3. **Format-aware overrides**: transformation instructions protect SP from VB/PN override

---

## File Locations

| File | Purpose | Lines |
|------|---------|-------|
| `backend/main.py` | FastAPI app, Gemini calls, keyword map, rule overrides, PDF/OCR pipeline | ~770 |
| `backend/classifier.py` | Rule-based: unit detection (VB/PN/SP), format detection, section/LP detection, grade estimation | ~1200 |
| `backend/english index table.xlsx` | Full taxonomy (15 units, ~10K rows) |
| `backend/tests/test_sp_*.py` | SP unit tests (unit detection, section/LP, grade, full pipeline) | 43 tests |
| `docs/plans/2026-03-22-vb-pn-classifier.md` | Original VB/PN implementation plan |
| `docs/plans/2026-03-25-add-sp-unit.md` | SP implementation plan |
