"""Tests for pymessage.utils module."""

import pytest

from pymessage.utils import generate_phone_variants, normalize_phone_number


class TestNormalizePhoneNumber:
    """Tests for normalize_phone_number function."""

    def test_formatted_with_plus(self):
        """Test normalizing phone number with + and formatting."""
        assert normalize_phone_number("+1 (234) 567-8900") == "+12345678900"

    def test_formatted_without_plus(self):
        """Test normalizing phone number without + and with formatting."""
        assert normalize_phone_number("(234) 567-8900") == "2345678900"

    def test_dashes_only(self):
        """Test normalizing phone number with only dashes."""
        assert normalize_phone_number("234-567-8900") == "2345678900"

    def test_spaces_only(self):
        """Test normalizing phone number with only spaces."""
        assert normalize_phone_number("234 567 8900") == "2345678900"

    def test_already_normalized(self):
        """Test that already normalized numbers pass through."""
        assert normalize_phone_number("+12345678900") == "+12345678900"
        assert normalize_phone_number("2345678900") == "2345678900"

    def test_email_address(self):
        """Test that email addresses are returned as-is."""
        assert normalize_phone_number("user@example.com") == "user@example.com"
        assert (
            normalize_phone_number("  user@example.com  ") == "user@example.com"
        )  # trimmed

    def test_international_number(self):
        """Test normalizing international phone numbers."""
        assert normalize_phone_number("+44 20 1234 5678") == "+442012345678"


class TestGeneratePhoneVariants:
    """Tests for generate_phone_variants function."""

    def test_plus_one_format(self):
        """Test generating variants for +1 formatted number."""
        variants = generate_phone_variants("+12345678900")
        assert "+12345678900" in variants
        assert "12345678900" in variants
        assert "2345678900" in variants
        assert len(variants) == 3

    def test_ten_digit_format(self):
        """Test generating variants for 10-digit number."""
        variants = generate_phone_variants("2345678900")
        assert "2345678900" in variants
        assert "+12345678900" in variants
        assert "12345678900" in variants
        assert len(variants) == 3

    def test_eleven_digit_format(self):
        """Test generating variants for 11-digit number (1 prefix)."""
        variants = generate_phone_variants("12345678900")
        assert "12345678900" in variants
        assert "+12345678900" in variants
        assert "2345678900" in variants
        assert len(variants) == 3

    def test_email_address(self):
        """Test that email addresses return single variant."""
        variants = generate_phone_variants("user@example.com")
        assert variants == ["user@example.com"]

    def test_international_number(self):
        """Test generating variants for international number."""
        variants = generate_phone_variants("+442012345678")
        # International numbers (not +1) should just have with/without + variants
        assert "+442012345678" in variants
        # May have other variants but should at least include original

    def test_no_duplicates(self):
        """Test that variants list contains no duplicates."""
        variants = generate_phone_variants("+12345678900")
        assert len(variants) == len(set(variants))
