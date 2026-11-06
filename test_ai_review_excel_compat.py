from pathlib import Path
import tempfile,shutil,unittest
from datetime import datetime,time
from io import BytesIO
from openpyxl import Workbook
from term_extractor_app.ai_review.readers import build_default_registry
from term_extractor_app.ai_review.excel_reader import read_excel_headers,read_excel_items_by_mapping
from term_extractor_app.ai_review.excel_compat import open_review_workbook,ExcelCompatibilityError
from term_extractor_app.ai_review.file_reader import detect_file_type

FIXTURE=Path(__file__).parent/'tests'/'fixtures'/'legacy_review.xls'

class ExcelCompatibilityTests(unittest.TestCase):
    def test_legacy_content_reads_with_legacy_modern_and_opaque_filenames(self):
        baseline=None
        with tempfile.TemporaryDirectory() as folder:
            for filename in ('review.xls','review.xlsx','private-cache'):
                path=Path(folder)/filename;shutil.copy2(FIXTURE,path)
                doc=build_default_registry().read(path,'review.xlsx' if filename=='private-cache' else filename)
                normalized=[(b.pointer,b.text) for b in doc.blocks]
                if baseline is None:baseline=normalized
                self.assertEqual(normalized,baseline)
                self.assertEqual(doc.structure['sheets'][0]['row_count'],4)
                self.assertEqual(len(doc.structure['sheets']),2)
                headers=read_excel_headers(path)
                self.assertEqual(headers['sheet_names'],['日语','空表'])
                mapping={'sheets':[{'sheet_name':'日语','mappings':[{'source_column':0,'target_column':1,'info_columns':[{'column':2,'category':'备注'}]}]}]}
                items=read_excel_items_by_mapping(path,mapping,'review.xlsx')
                self.assertEqual(len(items),3)
                self.assertEqual(items[0]['source_text'],'Hello\n{player}')
                self.assertEqual(items[0]['target_text'],'こんにちは\n{player}')
                self.assertEqual(items[0]['info'][0]['value'],'<b>tag</b>')
                self.assertEqual(items[1]['source_text'],'123')
                self.assertEqual(items[2]['source_text'],'2026-11-06 00:00:00')
                self.assertEqual(items[2]['target_text'],'12:00:00')
                self.assertEqual(detect_file_type(FIXTURE),'excel')

    def test_modern_content_reads_even_with_legacy_suffix(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'modern.xls';b=Workbook();b.active.append(['Source','Target']);b.active.append(['Hello','你好']);b.save(path);b.close()
            doc=build_default_registry().read(path)
            self.assertEqual([b.text for b in doc.blocks],['Hello','你好'])

    def test_legacy_bytes_stream_and_missing_mapped_cells(self):
        stream=BytesIO(FIXTURE.read_bytes())
        with open_review_workbook(stream) as book:
            row=list(book.worksheets[0].iter_rows(min_row=3,max_row=3,max_col=5,values_only=True))[0]
            self.assertEqual(row,(123,True,'number and boolean',None,None))
        self.assertFalse(stream.closed)

    def test_legacy_term_table_has_same_language_and_entry_semantics(self):
        from term_extractor_app.ai_review.term_base_service import _parse_term_table_workbook
        parsed=_parse_term_table_workbook((FIXTURE.parent/'legacy_terms.xls').read_bytes())
        self.assertEqual(parsed['languages'],['English','简体中文'])
        self.assertEqual(parsed['entries'][0]['entry_id'],'term-1')
        self.assertEqual(parsed['entries'][0]['terms']['简体中文'],['护盾'])

    def test_invalid_and_truncated_containers_are_reported_without_modification(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'bad.xlsx';data=b'not a workbook';path.write_bytes(data)
            with self.assertRaises(ExcelCompatibilityError):open_review_workbook(path)
            self.assertEqual(path.read_bytes(),data)
            path.write_bytes(FIXTURE.read_bytes()[:100])
            with self.assertRaises(ExcelCompatibilityError):open_review_workbook(path)

if __name__=='__main__':unittest.main()
