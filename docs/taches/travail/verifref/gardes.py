"""Applique les vraies gardes du dépôt (fonctions check_file) à faux_models.py. Jetable."""
import ast, sys, pathlib
ici = pathlib.Path(__file__).resolve().parent
racine = ici.parents[3]
sys.path.insert(0, str(racine / 'scripts'))
import check_unique_scoping as cus
import check_on_delete as cod
import check_naive_datetime as cnd
f = ici / 'faux_models.py'
sites, find = cus.check_file(f)
print('check_unique_scoping : unique=True =', sites, '; constats =', find)
rows, find2, debt = cod.check_file(f)
print('check_on_delete : constats =', find2)
tree = ast.parse(f.read_text(encoding='utf-8'))
hits = [(m, fld) for m, fld, node in cnd._iter_field_assignments(tree)
        if cnd._call_name(node) == 'DateField' and cnd.TIMESTAMP_NAME_RE.search(fld)]
print('check_naive_datetime (DateField nommé comme un horodatage) :', hits)
