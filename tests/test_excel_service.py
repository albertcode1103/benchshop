import io
import zipfile
import unittest

from backend.excel_service import catalog_template, parse_xlsx


class ExcelTemplateTests(unittest.TestCase):
    def test_four_sheets_round_trip(self):
        data = catalog_template(
            [{"id": "CR1", "name": "设备", "name_en": "Bench", "base_price": 1, "price_usd": 2, "enabled": True}],
            [],
            [{"product_id": "CR1", "motor_option_id": "motor-a", "base_price_cny": 10, "base_price_usd": 2}],
            [{"product_id": "CR1", "id": "spec-a", "label": "功率", "label_en": "Power", "value": "5kW", "value_en": "5kW", "sort_order": 0}],
        )
        sheets = parse_xlsx(data)
        self.assertEqual(4, len(sheets))
        self.assertEqual(["CR1", "motor-a", "10", "2"], sheets[2][1])
        self.assertEqual(["CR1", "spec-a", "功率", "Power", "5kW", "5kW", "0"], sheets[3][1])
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertIn("xl/worksheets/sheet4.xml", archive.namelist())

    def test_reads_shared_strings_numeric_and_empty_columns(self):
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as archive:
            archive.writestr("xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>设备型号</t></si><si><t>CR1</t></si></sst>')
            sheet = '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="C1"><v>12</v></c></row><row r="2"><c r="A2" t="s"><v>1</v></c><c r="C2" t="b"><v>1</v></c></row></sheetData></worksheet>'
            for index in range(1, 5):
                archive.writestr(f"xl/worksheets/sheet{index}.xml", sheet)
        self.assertEqual(["设备型号", "", "12"], parse_xlsx(payload.getvalue())[0][0])
        self.assertEqual(["CR1", "", True], parse_xlsx(payload.getvalue())[0][1])


if __name__ == "__main__":
    unittest.main()
