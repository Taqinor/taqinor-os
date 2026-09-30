#!/usr/bin/env python3
"""Garde : deux apps ne doivent JAMAIS définir une commande de gestion du même nom.

Django résout ``manage.py <nom>`` vers UNE seule app (la plus haute dans
INSTALLED_APPS) : l'autre commande est masquée en silence, sans erreur ni
avertissement. Incident du 30/09/2026 (PR #743) : l'``export_anonymise`` de la
QA de nuit (``authentication``) était masqué par celui de ``core`` (YHARD10) —
en prod, la commande documentée aurait lancé l'AUTRE export. Seul un test qui
appelait la commande avec ses propres options l'a révélé.

Échoue si un même nom de fichier de commande apparaît dans deux dossiers
``management/commands`` du backend.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent / 'backend' / 'django_core'


def collisions(racine: Path = RACINE) -> dict[str, list[str]]:
    """``{nom de commande: [apps qui la définissent]}`` pour les noms en double."""
    par_nom: dict[str, list[str]] = defaultdict(list)
    for fichier in sorted(racine.rglob('management/commands/*.py')):
        if fichier.name.startswith('_'):
            continue
        app = fichier.parent.parent.parent.relative_to(racine).as_posix()
        par_nom[fichier.stem].append(app)
    return {nom: apps for nom, apps in par_nom.items() if len(apps) > 1}


def main() -> int:
    trouvees = collisions()
    if not trouvees:
        print('OK : aucun nom de commande de gestion partagé entre deux apps.')
        return 0
    print("ÉCHEC : commandes de gestion définies dans plusieurs apps "
          "(Django n'en exécute qu'une, l'autre est masquée) :")
    for nom, apps in sorted(trouvees.items()):
        print(f'  - {nom} : {", ".join(apps)}')
    return 1


if __name__ == '__main__':
    sys.exit(main())
