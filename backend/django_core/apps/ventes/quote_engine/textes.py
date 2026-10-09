"""Helpers de texte client du moteur de devis (stdlib seulement).

AMOT46 : ``tronquer_au_mot`` vivait dans ``montants.py``, réservé au formateur
monétaire (``decimal`` seul, gardé par test) — il déménage ici."""
import html as _html


def tronquer_au_mot(texte, longueur):
    """AMOT46 (C-AMOT-059) — LE helper de troncature des textes du document.

    Le texte rendu est DÉJÀ échappé (``builder.echapper_textes_client``) :
    le couper au caractère tranchait une entité HTML (« l&#x2 » → « l\x00 »
    au PDF). On tronque le texte BRUT (entités décodées), AU MOT, on ajoute
    « … », puis on ré-échappe. Un texte assez court est rendu tel quel."""
    brut = _html.unescape(str(texte or ""))
    if len(brut) <= longueur:
        return texte
    coupe = brut[:longueur].rsplit(" ", 1)[0] or brut[:longueur]
    return _html.escape(coupe.rstrip(" ,;:"), quote=False) + "&#8230;"
