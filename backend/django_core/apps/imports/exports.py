"""Export .xlsx réutilisable et standardisé pour toutes les listes.

Un seul constructeur openpyxl (`build_xlsx_response`) + un mixin DRF
(`XlsxExportMixin`) que les ViewSets exposent via une action `export`. L'export
RESPECTE les filtres courants (il consomme `self.filter_queryset(get_queryset())`,
donc les mêmes query params que la liste) et reste scopé société par le viewset.

RÈGLE : aucun prix d'achat / marge dans un export (déjà imposé par le choix des
colonnes — `prix_achat` n'est jamais listé).
"""
from io import BytesIO

from django.http import HttpResponse
from rest_framework.decorators import action

XLSX_CONTENT_TYPE = (
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


def build_xlsx_response(filename, sheet_title, columns, rows):
    """Construit une réponse HTTP .xlsx.

    columns : liste de (key, label). rows : itérable d'objets ; chaque colonne
    est résolue via `row_value(obj, key)` (fournie par l'appelant) — ici on
    attend des dicts {key: value} déjà aplatis.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31] or 'Export'
    ws.append([label for _, label in columns])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in rows:
        ws.append([row.get(key, '') for key, _ in columns])
    buf = BytesIO()
    wb.save(buf)
    resp = HttpResponse(buf.getvalue(), content_type=XLSX_CONTENT_TYPE)
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


class XlsxExportMixin:
    """Ajoute une action GET `export` à un ModelViewSet.

    Le ViewSet doit définir :
      - `export_columns` : liste de (key, label) ;
      - `export_filename` : nom de fichier (.xlsx) ;
      - `export_sheet_title` (optionnel, défaut = filename) ;
      - `get_export_row(self, obj)` : renvoie un dict {key: cellule}.

    L'action réutilise `filter_queryset(get_queryset())` : mêmes filtres et
    même scope société que la liste.
    """

    export_columns = []
    export_filename = 'export.xlsx'
    export_sheet_title = None

    def get_export_row(self, obj):  # pragma: no cover - overridden
        raise NotImplementedError

    def get_export_queryset(self):
        return self.filter_queryset(self.get_queryset())

    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request, *args, **kwargs):
        qs = self.get_export_queryset()
        rows = (self.get_export_row(obj) for obj in qs)
        return build_xlsx_response(
            self.export_filename,
            self.export_sheet_title or self.export_filename,
            self.export_columns,
            rows,
        )
