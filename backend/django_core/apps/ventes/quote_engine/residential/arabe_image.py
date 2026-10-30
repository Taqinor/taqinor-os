"""ERR-PDF-AR-RESIDENTIEL-ANGLAIS — texte arabe dessiné DANS une image
matplotlib.

Matplotlib n'affiche pas l'arabe correctement tel quel (lettres non liées,
sens inversé). Ce module met un texte arabe en forme (formes isolée / initiale
/ médiane / finale tirées de la base Unicode, ligatures lam-alef) puis le
range en ordre visuel gauche-droite, sans dépendance ajoutée. Les chiffres et
le latin gardent leur sens. Un texte sans lettre arabe est rendu tel quel.
"""
import unicodedata

_FORMES = {}      # lettre de base -> {'isolated','final','initial','medial'}
_LIGATURES = {}   # (lam, alef…) -> {'isolated','final'}


def _construire():
    for cp in range(0xFE70, 0xFEFD):
        dec = unicodedata.decomposition(chr(cp))
        if not dec.startswith("<"):
            continue
        balise, _, reste = dec.partition(" ")
        base = tuple(chr(int(h, 16)) for h in reste.split())
        balise = balise.strip("<>")
        if len(base) == 1:
            _FORMES.setdefault(base[0], {})[balise] = chr(cp)
        elif len(base) == 2:
            _LIGATURES.setdefault(base, {})[balise] = chr(cp)


_construire()


def _est_arabe(c):
    return "؀" <= c <= "ۿ" or "ﹰ" <= c <= "ﻼ"


def _lie_suivant(c):
    return c in _FORMES and "initial" in _FORMES[c]


def _lie_precedent(c):
    return c in _FORMES and "final" in _FORMES[c]


def _former(texte):
    """Ordre logique -> ordre logique en formes de présentation."""
    sortie = []
    i, n = 0, len(texte)
    prec_lie = False          # la lettre précédente se lie à la suivante
    while i < n:
        c = texte[i]
        if c not in _FORMES:
            sortie.append(c)
            prec_lie = False
            i += 1
            continue
        if c == "ل" and i + 1 < n and (c, texte[i + 1]) in _LIGATURES:
            lig = _LIGATURES[(c, texte[i + 1])]
            sortie.append(lig["final"] if prec_lie and "final" in lig
                          else lig["isolated"])
            prec_lie = False
            i += 2
            continue
        suivant = texte[i + 1] if i + 1 < n else ""
        lie_suiv = _lie_suivant(c) and _lie_precedent(suivant)
        f = _FORMES[c]
        if prec_lie and lie_suiv and "medial" in f:
            sortie.append(f["medial"])
        elif prec_lie and "final" in f:
            sortie.append(f["final"])
        elif lie_suiv and "initial" in f:
            sortie.append(f["initial"])
        else:
            sortie.append(f.get("isolated", c))
        prec_lie = lie_suiv
        i += 1
    return "".join(sortie)


def _inverser_mot(mot):
    """Ordre visuel d'un mot : segments arabes inversés, autres inchangés,
    et ordre des segments inversé."""
    segments, cur, arabe = [], "", None
    for c in mot:
        a = _est_arabe(c)
        if arabe is None or a == arabe:
            cur += c
        else:
            segments.append((cur, arabe))
            cur = c
        arabe = a
    if cur:
        segments.append((cur, arabe))
    return "".join(s[::-1] if a else s for s, a in reversed(segments))


def mettre_en_forme(texte):
    """Texte prêt pour matplotlib ; inchangé s'il ne contient pas d'arabe."""
    if not texte or not any(_est_arabe(c) for c in texte):
        return texte
    mots = _former(texte).split(" ")
    visuel = " ".join(_inverser_mot(m) for m in reversed(mots))
    # Parenthèses : l'inversion visuelle les retourne, on les ré-échange.
    return visuel.translate(str.maketrans("()", ")("))
