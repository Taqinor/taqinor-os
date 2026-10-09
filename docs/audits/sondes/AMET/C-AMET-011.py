# SONDE = {'constat': 'C-AMET-011', 'sha': 'f3716e3f0', 'attendu': 'voir C-AMET-010.py (même sonde, second constat)'}
# Alias : la sonde C-AMET-010.py couvre aussi ce constat ; ce fichier n'existe que pour la colonne Sonde du dossier.
from importlib import import_module


def sonde(ctx):
    return import_module('docs.audits.sondes.AMET.C_AMET_010').sonde(ctx)
