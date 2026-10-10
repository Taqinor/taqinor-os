"""Alias de C-AMET-010 (même sonde, second constat) : ce fichier n'existe que pour la colonne Sonde du dossier."""
SONDE = {
    'constat': 'C-AMET-011',
    'sha': 'f3716e3f0',
    'attendu': 'voir C-AMET-010.py (même sonde, second constat)',
}


def sonde(ctx):
    return ('STATIQUE : alias de C-AMET-010 ; rejouer `python scripts/sonde.py AMET/C-AMET-010` '
            'pour l\'observation réelle')
