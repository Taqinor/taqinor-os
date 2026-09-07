"""Génère ``backend/django_core/apps/parametres/villes_canoniques.py``.

Source : les exports GeoNames MA.txt (+ EH.txt pour le Sahara — Laâyoune,
Dakhla, Boujdour…), licence CC-BY 4.0. Usage ::

    python scripts/build_villes_canoniques.py chemin/MA.txt [chemin/EH.txt]

Pour chaque clé du gazetier ``villes_maroc.VILLES_MAROC`` (1 clé = une
graphie normalisée, plusieurs clés partagent les coordonnées d'une même
ville), retrouve la ligne GeoNames de MÊMES coordonnées (arrondies 4
décimales, VERBATIM des deux côtés) et retient son nom PRINCIPAL comme nom
canonique d'affichage. Exonymes français appliqués par-dessus (Marrakech,
Tanger, Fès…). Une clé sans ligne GeoNames appariée retombe sur son propre
``title()`` — jamais de nom inventé.

Le module généré ajoute aussi les villes du SUPPLÉMENT Sahara (celles de
``transport_bareme.VILLES_SUPPLEMENT``) comme entrées canoniques à part
entière : un client de Laâyoune doit se résoudre comme les autres.
"""
from __future__ import annotations

import sys
import unicodedata
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SORTIE = (RACINE / 'backend' / 'django_core' / 'apps' / 'parametres'
          / 'villes_canoniques.py')
# Import par PAQUET (``apps.parametres.…``) : ``transport_bareme`` fait un
# import relatif et exige son contexte de paquet.
sys.path.insert(0, str(RACINE / 'backend' / 'django_core'))

#: Exonymes français (mêmes choix que le barème transport).
EXONYMES = {
    'marrakesh': 'Marrakech', 'tangier': 'Tanger', 'fes': 'Fès',
    'zawyat an nwacer': 'Nouaceur', 'sale': 'Salé', 'tetouan': 'Tétouan',
    'meknes': 'Meknès', 'temara': 'Témara', 'kenitra': 'Kénitra',
}


def _norm(t):
    t = str(t or '').strip().lower().replace('-', ' ').replace("'", ' ')
    t = unicodedata.normalize('NFKD', t)
    t = ''.join(c for c in t if not unicodedata.combining(c))
    return ' '.join(t.split())


def lire_geonames(chemins):
    """(lat, lon) arrondis 4 décimales -> (nom principal, population)."""
    par_coords = {}
    for chemin in chemins:
        with open(chemin, encoding='utf-8') as fh:
            for ligne in fh:
                c = ligne.rstrip('\n').split('\t')
                if len(c) < 15 or c[6] != 'P':
                    continue
                try:
                    pop = int(c[14] or 0)
                except ValueError:
                    pop = 0
                coords = (round(float(c[4]), 4), round(float(c[5]), 4))
                nom = c[1] or c[2]
                if coords not in par_coords or pop > par_coords[coords][1]:
                    par_coords[coords] = (nom, pop)
    return par_coords


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    from apps.parametres.transport_bareme import VILLES_SUPPLEMENT
    from apps.parametres.villes_maroc import VILLES_MAROC

    geonames = lire_geonames(sys.argv[1:])
    lignes_dict = {}
    for cle, coords in VILLES_MAROC.items():
        nom, _pop = geonames.get(tuple(coords), (None, 0))
        cle_nom = _norm(nom) if nom else ''
        canon = EXONYMES.get(cle_nom) or (nom if nom else cle.title())
        lignes_dict[cle] = canon
    for cle, _coords in VILLES_SUPPLEMENT.items():
        if cle not in lignes_dict:
            lignes_dict[cle] = EXONYMES.get(cle, cle.title())
    # Exonymes appliqués aussi quand la clé ELLE-MÊME est l'exonyme.
    for cle in list(lignes_dict):
        if cle in EXONYMES:
            lignes_dict[cle] = EXONYMES[cle]

    tete = [
        '"""Nom CANONIQUE d\'affichage par clé du gazetier — GÉNÉRÉ.',
        '',
        'Généré par ``scripts/build_villes_canoniques.py`` le %s depuis'
        % date.today().isoformat(),
        "les exports GeoNames MA+EH (licence CC-BY 4.0), apparié par",
        'coordonnées au gazetier ``villes_maroc`` ; exonymes français',
        'appliqués (Marrakech, Fès, Tanger…). Aucun nom inventé : une clé',
        'sans ligne GeoNames appariée porte son propre ``title()``.',
        '"""',
        '',
        'VILLES_CANONIQUES = {',
    ]
    corps = ["    '%s': %r," % (cle, lignes_dict[cle])
             for cle in sorted(lignes_dict)]
    contenu = '\n'.join(tete + corps + ['}', ''])
    SORTIE.write_text(contenu, encoding='utf-8')
    print('écrit %s (%d clés)' % (SORTIE, len(lignes_dict)))


if __name__ == '__main__':
    main()
