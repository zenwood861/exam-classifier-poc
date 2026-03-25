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
