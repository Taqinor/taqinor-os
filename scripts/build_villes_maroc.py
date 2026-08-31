"""Génère ``backend/django_core/apps/parametres/villes_maroc.py`` (gazetier).

Source : l'export GeoNames du Maroc (https://download.geonames.org/export/dump/MA.zip,
licence CC-BY 4.0). Usage ::

    python scripts/build_villes_maroc.py chemin/vers/MA.txt

Filtre : lieux habités (classe ``P``) de population >= 5 000, plus les
chefs-lieux ``PPLA``/``PPLA2`` quelle que soit leur population. Les noms sont
normalisés (minuscules, sans accent, tirets/apostrophes -> espace) ; en cas de
doublon de nom, la plus grande population gagne. Pour les noms à tiret ou
apostrophe, une variante collée est aussi émise (« tan tan » ET « tantan »)
pour tolérer les deux écritures. Les ORTHOGRAPHES ALTERNATIVES latines de
GeoNames (colonne ``alternatenames``) des villes retenues comblent les trous
(« Skhirat » pour « Skhirate ») — jamais en écrasant un nom principal.

Les coordonnées sont recopiées VERBATIM de GeoNames (des FAITS, pas des
estimations) — règle « zéro chiffre inventé » respectée : le gazetier ne
contient aucun productible, seulement des positions. La résolution
productible/forme reste l'affaire de ``pvgis_profils`` (ancre la plus proche).
"""
from __future__ import annotations

import sys
import unicodedata
from datetime import date
from pathlib import Path

SORTIE = (Path(__file__).resolve().parent.parent / 'backend' / 'django_core'
          / 'apps' / 'parametres' / 'villes_maroc.py')

POPULATION_MIN = 5000
CODES_TOUJOURS = {'PPLA', 'PPLA2'}


def _normaliser(texte: str) -> str:
    txt = str(texte or '').strip().lower()
    txt = txt.replace('-', ' ').replace("'", ' ').replace('’', ' ')
    txt = unicodedata.normalize('NFKD', txt)
    txt = ''.join(c for c in txt if not unicodedata.combining(c))
    return ' '.join(txt.split())


# Mots d'adresse génériques : jamais des clés de ville (une « medina » ou une
# « plage » existent dans toutes les villes — les retenir ferait pointer un
# texte d'adresse vers une ville arbitraire).
_STOPLIST = {
    'medina', 'medine', 'plage', 'centre', 'ville', 'kasbah', 'casbah',
    'marina', 'corniche', 'sahara', 'atlas', 'maroc', 'morocco', 'marruecos',
    'marokko', 'quartier', 'gare',
}


def _alternates_latins(brut):
    """Orthographes alternatives latines exploitables (1 à 3 mots a-z).

    Minimum 5 caractères : les alternates GeoNames courts sont des codes
    aéroport (CMN, RAK…) et des abréviations, dangereux en correspondance de
    mots entiers. Les noms PRINCIPAUX courts (Tata, Assa, Zag…), eux, restent.
    """
    for alt in (brut or '').split(','):
        cle = _normaliser(alt)
        if not cle or len(cle) < 5 or len(cle.split()) > 3:
            continue
        if cle in _STOPLIST:
            continue
        if not all(c == ' ' or 'a' <= c <= 'z' for c in cle):
            continue  # ASCII seulement — pas d'écritures arabes/cyrilliques
        yield cle


def lire_villes(chemin):
    villes = {}
    alternates = {}
    with open(chemin, encoding='utf-8') as fh:
        for ligne in fh:
            cols = ligne.rstrip('\n').split('\t')
            if len(cols) < 15 or cols[6] != 'P':
                continue
            code = cols[7]
            try:
                pop = int(cols[14] or 0)
            except ValueError:
                pop = 0
            if pop < POPULATION_MIN and code not in CODES_TOUJOURS:
                continue
            nom = cols[2] or cols[1]  # asciiname, sinon name
            cle = _normaliser(nom)
            if not cle:
                continue
            lat, lon = round(float(cols[4]), 4), round(float(cols[5]), 4)
            candidats = {cle}
            colle = cle.replace(' ', '')
            if colle != cle and ('-' in nom or "'" in nom):
                candidats.add(colle)
            for c in candidats:
                if c not in villes or pop > villes[c][2]:
                    villes[c] = (lat, lon, pop)
            for alt in _alternates_latins(cols[3]):
                if alt not in alternates or pop > alternates[alt][2]:
                    alternates[alt] = (lat, lon, pop)
    # Les alternates COMBLENT les trous, jamais n'écrasent un nom principal.
    for cle, val in alternates.items():
        if cle not in villes:
            villes[cle] = val
    return villes


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    villes = lire_villes(sys.argv[1])
    lignes = [
        '"""Gazetier des villes du Maroc — GÉNÉRÉ, ne pas éditer à la main.',
        '',
        'Généré par ``scripts/build_villes_maroc.py`` le %s à partir de'
        % date.today().isoformat(),
        "l'export GeoNames du Maroc (download.geonames.org/export/dump/MA.zip,",
        'licence CC-BY 4.0) : lieux habités de population >= 5 000 + '
        'chefs-lieux.',
        '',
        'Contenu : nom normalisé -> (lat, lon), coordonnées GeoNames VERBATIM.',
        'Aucun productible ici — la résolution solaire (ancre PVGIS la plus',
        'proche) vit dans ``pvgis_profils`` ; ce module ne connaît que des',
        'positions, des FAITS (règle « zéro chiffre inventé »).',
        '"""',
        'from __future__ import annotations',
        '',
        'import unicodedata',
        '',
        'VILLES_MAROC = {',
    ]
    for cle in sorted(villes):
        lat, lon, _pop = villes[cle]
        lignes.append("    '%s': (%.4f, %.4f)," % (cle, lat, lon))
    lignes += [
        '}',
        '',
        '',
        'def _normaliser(texte) -> str:',
        '    """Même normalisation que la génération : minuscules, sans accent,',
        '    tirets/apostrophes -> espace, espaces compactés."""',
        "    txt = str(texte or '').strip().lower()",
        "    txt = txt.replace('-', ' ').replace(\"'\", ' ')"
        ".replace('\\u2019', ' ')",
        "    txt = unicodedata.normalize('NFKD', txt)",
        "    txt = ''.join(c for c in txt if not unicodedata.combining(c))",
        "    return ' '.join(txt.split())",
        '',
        '',
        'def coordonnees_ville(texte):',
        '    """``(lat, lon)`` de la ville nommée dans ``texte``, ou ``None``.',
        '',
        '    Correspondance exacte d\'abord, puis recherche du nom de ville',
        '    comme séquence de MOTS ENTIERS dans le texte (virgules =',
        '    séparateurs, candidats multi-mots d\'abord) — même discipline que',
        '    ``pvgis_profils._cle_ville_tolerante`` : un texte sans ville du',
        '    gazetier rend ``None``, jamais une position devinée.',
        '    """',
        '    cle = _normaliser(texte)',
        '    if not cle:',
        '        return None',
        '    exact = VILLES_MAROC.get(cle)',
        '    if exact:',
        '        return exact',
        "    colle = VILLES_MAROC.get(cle.replace(' ', ''))",
        '    if colle:',
        "        return colle  # « M diq » -> « mdiq »",
        "    mots = cle.replace(',', ' ').split()",
        '    if not mots:',
        '        return None',
        '    for candidat in _CANDIDATS_TRIES:',
        '        mots_candidat = candidat.split()',
        '        n = len(mots_candidat)',
        '        for i in range(len(mots) - n + 1):',
        '            if mots[i:i + n] == mots_candidat:',
        '                return VILLES_MAROC[candidat]',
        '    return None',
        '',
        '',
        '# Candidats triés une fois : multi-mots avant mono-mots (jamais un mot',
        '# isolé ne doit chevaucher un nom composé), puis alphabétique (stable).',
        '_CANDIDATS_TRIES = sorted(',
        '    VILLES_MAROC, key=lambda c: (-len(c.split()), c))',
        '',
    ]
    SORTIE.write_text('\n'.join(lignes), encoding='utf-8')
    print('écrit %s (%d villes)' % (SORTIE, len(villes)))


if __name__ == '__main__':
    main()
