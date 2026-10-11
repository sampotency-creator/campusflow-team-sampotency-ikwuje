import pytest

from campusflow.tickets import (
    validate_title,
    validate_category,
    validate_urgency,
    validate_affected_users,
    calculate_priority,
    generate_ticket_id,
    create_ticket,
)


# ==========================================
# 1. TEST TITLE VALIDATION
# ==========================================

def test_valid_title():
    assert validate_title("Campus internet outage") == "Campus internet outage"


def test_title_removes_extra_spaces():
    assert validate_title("  Internet outage  ") == "Internet outage"


def test_empty_title_is_rejected():
    with pytest.raises(ValueError):
        validate_title("")


# ==========================================
# 2. TEST CATEGORY VALIDATION
# ==========================================

def test_valid_category():
    assert validate_category("network") == "network"


def test_category_accepts_uppercase():
    assert validate_category("NETWORK") == "network"


def test_invalid_category_is_rejected():
    with pytest.raises(ValueError):
        validate_category("food")


# ==========================================
# 3. TEST URGENCY VALIDATION
# ==========================================

def test_valid_urgency():
    assert validate_urgency("high") == "high"


def test_urgency_accepts_uppercase():
    assert validate_urgency("HIGH") == "high"


def test_invalid_urgency_is_rejected():
    with pytest.raises(ValueError):
        validate_urgency("urgent")


# ==========================================
# 4. TEST AFFECTED USERS VALIDATION
# ==========================================

def test_valid_affected_users():
    assert validate_affected_users(12) == 12


def test_zero_affected_users_is_rejected():
    with pytest.raises(ValueError):
        validate_affected_users(0)


def test_negative_affected_users_is_rejected():
    with pytest.raises(ValueError):
        validate_affected_users(-3)


def test_decimal_affected_users_is_rejected():
    with pytest.raises(ValueError):
        validate_affected_users(2.5)


def test_boolean_affected_users_is_rejected():
    with pytest.raises(ValueError):
        validate_affected_users(True)


# ==========================================
# 5. TEST PRIORITY CALCULATION
# ==========================================

def test_critical_priority():
    assert calculate_priority("high", 12) == "critical"


def test_high_priority_from_urgency():
    assert calculate_priority("high", 2) == "high"


def test_high_priority_from_affected_users():
    assert calculate_priority("low", 10) == "high"


def test_medium_priority_from_urgency():
    assert calculate_priority("medium", 2) == "medium"


def test_medium_priority_from_affected_users():
    assert calculate_priority("low", 4) == "medium"


def test_low_priority():
    assert calculate_priority("low", 1) == "low"


# ==========================================
# 6. TEST TICKET ID GENERATION
# ==========================================

def test_first_ticket_id():
    assert generate_ticket_id(1) == "T001"


def test_second_ticket_id():
    assert generate_ticket_id(2) == "T002"


def test_ticket_id_with_two_digit_number():
    assert generate_ticket_id(12) == "T012"


def test_ticket_id_with_three_digit_number():
    assert generate_ticket_id(125) == "T125"


def test_zero_ticket_number_is_rejected():
    with pytest.raises(ValueError):
        generate_ticket_id(0)


def test_negative_ticket_number_is_rejected():
    with pytest.raises(ValueError):
        generate_ticket_id(-1)


# ==========================================
# 7. TEST COMPLETE TICKET CREATION
# ==========================================

def test_create_ticket():
    ticket = create_ticket(
        "Campus internet outage",
        "network",
        "high",
        12,
        1,
    )

    assert ticket == {
        "id": "T001",
        "title": "Campus internet outage",
        "category": "network",
        "urgency": "high",
        "affected_users": 12,
        "priority": "critical",
        "status": "open",
        "assigned_to": None,
    }


def test_create_ticket_rejects_empty_title():
    with pytest.raises(ValueError):
        create_ticket("", "network", "high", 12, 1)


def test_create_ticket_rejects_invalid_category():
    with pytest.raises(ValueError):
        create_ticket("Internet outage", "food", "high", 12, 1)


def test_create_ticket_rejects_invalid_urgency():
    with pytest.raises(ValueError):
        create_ticket("Internet outage", "network", "urgent", 12, 1)


def test_create_ticket_rejects_zero_affected_users():
    with pytest.raises(ValueError):
        create_ticket("Internet outage", "network", "high", 0, 1)