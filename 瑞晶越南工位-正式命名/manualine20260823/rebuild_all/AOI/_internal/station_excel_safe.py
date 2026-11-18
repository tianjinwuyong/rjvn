"""Read an Excel workbook safely, including a workbook open in Excel."""
from pathlib import Path

from openpyxl import load_workbook as _openpyxl_load_workbook


class _Cell:
    def __init__(self, value):
        self.value = value


class _Sheet:
    def __init__(self, title, rows):
        self.title = title
        self._rows = rows
        self.max_row = len(rows)
        self.max_column = max((len(row) for row in rows), default=0)

    def cell(self, row, column):
        try:
            return _Cell(self._rows[row - 1][column - 1])
        except IndexError:
            return _Cell(None)

    def iter_rows(self, min_row=1, max_row=None, values_only=False):
        end = min(max_row or self.max_row, self.max_row)
        for row in self._rows[max(0, min_row - 1):end]:
            values = tuple(row)
            yield values if values_only else tuple(_Cell(value) for value in values)


class _Workbook:
    def __init__(self, sheets):
        self.worksheets = sheets
        self.active = sheets[0]
        self.sheetnames = [sheet.title for sheet in sheets]

    def close(self):
        return None


def _load_from_running_excel(path):
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    workbook = None
    try:
        workbook = win32com.client.GetObject(str(Path(path).resolve()))
        sheets = []
        for index in range(1, workbook.Worksheets.Count + 1):
            sheet = workbook.Worksheets(index)
            values = sheet.UsedRange.Value
            if values is None:
                rows = []
            elif not isinstance(values, tuple):
                rows = [[values]]
            elif values and not isinstance(values[0], tuple):
                rows = [list(values)]
            else:
                rows = [list(row) for row in values]
            sheets.append(_Sheet(str(sheet.Name), rows))
        if not sheets:
            sheets.append(_Sheet("Sheet1", []))
        return _Workbook(sheets)
    finally:
        workbook = None
        pythoncom.CoUninitialize()


def load_workbook(filename, *args, **kwargs):
    try:
        return _openpyxl_load_workbook(filename, *args, **kwargs)
    except (PermissionError, OSError):
        if kwargs.get("read_only") is False:
            raise
        return _load_from_running_excel(filename)
