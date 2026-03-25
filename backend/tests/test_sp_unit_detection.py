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
