from unittest.mock import Mock
from backend.pdf_service import _guarded_table
from backend.pdf_service import _quote_item_sort


def test_long_group_can_use_remaining_page_space():
    table = Mock()
    assert _guarded_table(table, True) == [table]
    table.wrap.assert_not_called()


def test_short_group_can_split_naturally_without_leaving_a_blank_page():
    table = Mock()
    assert _guarded_table(table, True) == [table]
    table.wrap.assert_not_called()


def test_unrestricted_group_does_not_force_break():
    table = Mock()
    assert _guarded_table(table, False) == [table]
    table.wrap.assert_not_called()


def test_legacy_category_order_matches_current_field():
    rows = [
        {"kind": "option", "code": "A", "device_sequence": 1, "catalog_category_sort_order": 20},
        {"kind": "option", "code": "B", "device_sequence": 1, "catalog_category_sort_order": 10},
    ]
    assert [row["code"] for row in _quote_item_sort(rows)] == ["B", "A"]
    assert "category_sort_order" not in rows[0]
