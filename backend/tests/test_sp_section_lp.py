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
