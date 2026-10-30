"""Sonde AANA, rejouable par scripts/sonde.py : lecture seule du code, aucune écriture. Jamais contre la prod.
Rejoue C-AANA-035 (audit analyse du 05/10, §6) : littéraux d'étape (NEW, CONTACTED, QUOTE_SENT, FOLLOW_UP, SIGNED, COLD) dans apps/reporting.
"""
SONDE = {
    'constat': 'C-AANA-035',
    'sha': '5908d43bb',
    'attendu': "défaut absent (STATIQUE) : 0 littéral d'étape entre guillemets dans les fichiers non-test de apps/reporting",
}


def sonde(ctx):
    import re
    from pathlib import Path
    import apps.reporting as pkg
    racine = Path(pkg.__file__).resolve().parent
    rx = re.compile(r"""['"](NEW|CONTACTED|QUOTE_SENT|FOLLOW_UP|SIGNED|COLD)['"]""")
    n_fichiers, hits = 0, []
    for f in sorted(racine.rglob('*.py')):
        rel = f.relative_to(racine).as_posix()
        if ('/migrations/' in '/' + rel or 'tests' in f.name or '/tests/' in '/' + rel
                or f.name.startswith('test_') or f.name == 'conftest.py'):
            continue
        n_fichiers += 1
        for i, ligne in enumerate(f.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
            if rx.search(ligne):
                hits.append('%s:%d' % (rel, i))
    msg = "STATIQUE — %d littéral d'étape dans apps/reporting (%d fichiers lus)" % (len(hits), n_fichiers)
    if hits:
        msg += ' : ' + ', '.join(hits[:10])
    print(msg)
    return msg
