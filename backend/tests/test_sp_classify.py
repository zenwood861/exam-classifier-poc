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
