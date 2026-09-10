from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from backend.catalog_refactor_repository import CatalogValidationError, update_catalog_item


def test_lost_compare_and_swap_is_a_conflict_not_success():
    current = dict(version=1, deleted_at=None, catalog_type='optional',
                   name='Original', name_en='Original', description='',
                   description_en='', notes='', note_en='')
    database = MagicMock()
    database.execute.return_value.fetchone.return_value = None
    database.execute.return_value.rowcount = 0
    rolled_back = []

    @contextmanager
    def connection():
        try:
            yield database
        except Exception:
            rolled_back.append(True)
            raise

    with patch('backend.catalog_refactor_repository.get_connection', connection), \
         patch('backend.catalog_refactor_repository._catalog_item_row', return_value=current), \
         patch('backend.catalog_refactor_repository._item_category', return_value={'catalog_type': 'optional'}):
        with pytest.raises(CatalogValidationError) as failure:
            update_catalog_item('test-item', version=1, category_id='test-category',
                                code='BTK-1001', name_zh='Updated', name_en='Updated')
    assert 'CATALOG_VERSION_CONFLICT' in str(failure.value)
    assert rolled_back == [True]
