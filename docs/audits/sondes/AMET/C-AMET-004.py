"""Alias de C-AMET-003 (même sonde, second constat) : ce fichier n'existe que pour la colonne Sonde du dossier."""
SONDE = {
    'constat': 'C-AMET-004',
    'sha': 'f3716e3f0',
    'attendu': 'voir C-AMET-003.py (même sonde, second constat)',
}


def sonde(ctx):
    return ('STATIQUE : alias de C-AMET-003 ; rejouer `python scripts/sonde.py AMET/C-AMET-003` '
            'pour l\'observation réelle')
