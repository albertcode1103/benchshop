import io
import zipfile
import unittest

from backend.excel_service import catalog_template, parse_xlsx


class ExcelTemplateTests(unittest.TestCase):
    def test_four_sheets_round_trip(self):
        data = catalog_template([{"id": "CR1", "name": "设备", "name_en": "Bench", "base_price": 1, "price_usd": 2, "enabled": True}], [])
        self.assertEqual(4, len(parse_xlsx(data)))
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertIn("xl/worksheets/sheet4.xml", archive.namelist())


if __name__ == "__main__":
    unittest.main()
