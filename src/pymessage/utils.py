"""Utility functions for phone number normalization and validation.

This module provides utilities for normalizing phone numbers in various
formats to match against iMessage database contact identifiers.
"""


def normalize_phone_number(phone: str) -> str:
    """Normalize phone number to digits-only format.

    Strips all non-digit characters except leading '+'. Email addresses
    (containing '@') are returned as-is.

    Args:
        phone: Phone number in any format, or email address.

    Returns:
        Normalized phone number or email address.

    Examples:
        >>> normalize_phone_number("+1 (234) 567-8900")
        '+12345678900'
        >>> normalize_phone_number("(234) 567-8900")
        '2345678900'
        >>> normalize_phone_number("234-567-8900")
        '2345678900'
        >>> normalize_phone_number("user@example.com")
        'user@example.com'
    """
    # If email, return as-is (trimmed)
    if "@" in phone:
        return phone.strip()

    # Keep leading +, remove all other non-digits
    if phone.startswith("+"):
        return "+" + "".join(c for c in phone[1:] if c.isdigit())
    else:
        return "".join(c for c in phone if c.isdigit())


def generate_phone_variants(phone: str) -> list[str]:
    """Generate lookup variants for phone number matching.

    Creates multiple representations to match against database, handling
    variations in how iMessage stores contact identifiers. Special handling
    for US +1 country code.

    Args:
        phone: Normalized phone number or email address.

    Returns:
        List of variants to try for lookup. Email addresses return
        single-item list.

    Examples:
        >>> variants = generate_phone_variants("+12345678900")
        >>> set(variants) == {"+12345678900", "12345678900", "2345678900"}
        True
        >>> variants = generate_phone_variants("2345678900")
        >>> "+12345678900" in variants
        True
        >>> "12345678900" in variants
        True
        >>> generate_phone_variants("user@example.com")
        ['user@example.com']
    """
    if "@" in phone:
        return [phone]  # Email - no variants needed

    variants = [phone]

    # Add/remove +1 variants for US numbers
    if phone.startswith("+1"):
        # +12345678900 → 12345678900, 2345678900
        variants.append(phone[1:])  # Without +
        if len(phone) == 12:  # +1 + 10 digits
            variants.append(phone[2:])  # Without +1
    elif phone.startswith("1") and len(phone) == 11:
        # 12345678900 → +12345678900, 2345678900
        variants.append("+" + phone)
        variants.append(phone[1:])
    elif len(phone) == 10:
        # 2345678900 → +12345678900, 12345678900
        variants.append("+1" + phone)
        variants.append("1" + phone)

    # Deduplicate while preserving order
    seen = set()
    result = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            result.append(v)

    return result
