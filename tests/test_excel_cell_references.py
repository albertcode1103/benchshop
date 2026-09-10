import pytest
from xml.etree import ElementTree as ET
from backend.excel_service import _cell_value, _column_index, _row_values


@pytest.mark.parametrize('index', ['-1', '2', '', 'bad', '1.5'])
def test_invalid_shared_string_reference_is_rejected(index):
    cell = ET.fromstring('<c t="s"><v>{}</v></c>'.format(index))
    with pytest.raises(ValueError):
        _cell_value(cell, ['first', 'last'])


@pytest.mark.parametrize('index,expected', [('0', 'first'), ('1', 'last')])
def test_valid_shared_string_reference_preserved(index, expected):
    cell = ET.fromstring('<c t="s"><v>{}</v></c>'.format(index))
    assert _cell_value(cell, ['first', 'last']) == expected


@pytest.mark.parametrize('reference', ['A1B2', 'A0', 'A-1', '1A', '', '列1', 'A1:Z2'])
def test_malformed_coordinates_are_not_reinterpreted(reference):
    with pytest.raises(ValueError):
        _column_index(reference)


@pytest.mark.parametrize('reference,column', [('A1', 1), ('Z2', 26), ('AA30', 27), ('dx10000', 128)])
def test_valid_coordinates_keep_column(reference, column):
    assert _column_index(reference) == column


def test_out_of_order_cells_preserve_columns_and_gaps():
    row = ET.fromstring('<row><c r="C1"><v>price</v></c><c r="A1"><v>code</v></c></row>')
    assert _row_values(row, []) == ['code', '', 'price']


def test_duplicate_column_is_rejected_not_shifted():
    row = ET.fromstring('<row><c r="A1"><v>one</v></c><c r="A1"><v>two</v></c></row>')
    with pytest.raises(ValueError, match='Duplicate'):
        _row_values(row, [])


def test_implicit_coordinates_follow_previous_cell():
    row = ET.fromstring('<row><c><v>one</v></c><c><v>two</v></c></row>')
    assert _row_values(row, []) == ['one', 'two']
