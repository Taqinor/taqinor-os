"""CALX172 — ÉTAPE « écrêtage » : le calcul horaire qui existait sans série.

CE QUI EXISTAIT, ET POURQUOI IL NE SERVAIT À RIEN
--------------------------------------------------
``services/electrique.py::ecretage_depuis_serie`` calcule la perte
d'écrêtage HEURE PAR HEURE depuis CAL127 — mais son unique appelant,
``bloc_ratio_dc_ac``, était invoqué sans ``serie_dc_kw``. ``ecretage_pct``
valait donc TOUJOURS ``null``, avec le motif « la perte d'écrêtage exige la
série horaire ». Le calcul était là, la série aussi (la chaîne de pertes la
produit) : les deux ne se rencontraient jamais.

Cette étape est la rencontre. Elle plafonne la série à la puissance que
l'onduleur peut réellement injecter, RETIRE l'énergie écrêtée heure par
heure, et écrit ``ecretage_kw`` sur chaque point (colonne du contrat
CALX142, que ``services/export_csv.py`` publie déjà).

LA BORNE D'ÉCRÊTAGE, ET SES DEUX CAS (D-CALX 7)
-------------------------------------------------
* ``cos φ`` SAISI au raccordement (CALX205, ``cos_phi_impose`` +
  ``source_cos_phi``) ⇒ la borne vaut ``min(puissance_ac_kw,
  s_max_kva × cos_phi_impose)`` : un onduleur bridé en puissance APPARENTE
  n'injecte pas davantage parce qu'on le lui demande ;
* ``cos φ`` NON saisi ⇒ la borne reste ``puissance_ac_kw``, avec la mention
  « cos φ non saisi ». Jamais un 1,0 supposé : supposer cos φ = 1 revient à
  affirmer que l'installation n'échange aucune puissance réactive, ce que
  personne n'a mesuré.

``s_max_kva`` non publiée par la fiche ⇒ la borne reste ``puissance_ac_kw``
et la mention nomme le champ absent.

CE QUI FAIT OMETTRE L'ÉTAPE
-----------------------------
La puissance AC de l'onduleur. Sans elle il n'y a pas de plafond, donc pas
d'écrêtage : l'étape S'OMET en publiant TEL QUEL le motif de refus que le
dépôt prononce déjà pour cette perte (``electrique.MOTIF_ECRETAGE_SANS_SERIE``
— une seule phrase pour une seule raison), en nommant le champ de fiche qui
manque. Une série sans colonne d'énergie lisible omet de la même façon.

LE PORTEUR D'ÉNERGIE
----------------------
L'étape lit la colonne que la série DÉCLARE : l'alternatif quand l'étape
« onduleur » (CALX170) a déjà converti, le continu sinon. Elle ne change pas
de porteur — elle plafonne celui qu'elle reçoit, et c'est la même borne dans
les deux cas puisque c'est l'onduleur qui plafonne.
"""
from __future__ import annotations

from apps.calepinage.services import etapes

LIBELLE = 'Écrêtage'

#: La colonne ÉCRITE sur chaque point (contrat CALX142, déjà exportée).
COLONNE_ECRETAGE = 'ecretage_kw'

#: Les champs de fiche et de saisie que l'étape lit, nommés comme l'écran
#: les affiche — ce sont eux que les omissions et les mentions prononcent.
CHAMP_PUISSANCE_AC = 'fiche_onduleur.ac_kw'
CHAMP_S_MAX = 'fiche_onduleur.s_max_kva'
CHAMP_COS_PHI = 'raccordement.cos_phi_impose'
CHAMP_SOURCE_COS_PHI = 'raccordement.source_cos_phi'

MENTION_COS_PHI_ABSENT = (
    "cos φ non saisi : la borne d'écrêtage reste la puissance ACTIVE de "
    "l'onduleur. Aucun cos φ n'est supposé — saisissez « %s » et sa source "
    "« %s » au raccordement pour borner l'injection sur la puissance "
    "apparente." % (CHAMP_COS_PHI, CHAMP_SOURCE_COS_PHI))

MENTION_S_MAX_ABSENTE = (
    "puissance apparente non publiée par la fiche (« %s ») : la borne "
    "d'écrêtage reste la puissance ACTIVE, même avec un cos φ saisi."
    % CHAMP_S_MAX)

MOTIF_SERIE_ILLISIBLE = (
    "Aucune colonne d'énergie lisible sur la série : il n'y a pas de "
    "puissance à plafonner. Étape OMISE.")

MOTIF_SANS_ONDULEUR = (
    "Aucun onduleur au bloc « electrique.onduleurs » : ni puissance, ni "
    "nombre d'appareils, donc aucune borne d'écrêtage. Étape OMISE.")

REFERENCE_ECRETAGE = (
    'HelioScope — Understanding DC/AC Ratio : table chiffrée de la perte '
    'par écrêtage selon le ratio (1,18 → 0,1 % ; 1,50 → 2,2 %) '
    '(https://help-center.helioscope.com/hc/en-us/articles/'
    '8198321934867-Understanding-DC-AC-Ratio) ; Aurora publie l\'énergie '
    'écrêtée dans son diagramme de pertes (https://aurorasolar.com/blog/'
    'choosing-the-right-size-inverter-for-your-solar-design-a-primer-on-'
    'inverter-clipping/). Chiffres CITÉS, jamais repris : la perte publiée '
    'ici est celle de CETTE série.')

__all__ = ['appliquer', 'LIBELLE', 'COLONNE_ECRETAGE', 'CHAMP_PUISSANCE_AC',
           'CHAMP_S_MAX', 'CHAMP_COS_PHI', 'MENTION_COS_PHI_ABSENT',
           'MENTION_S_MAX_ABSENTE']


def appliquer(serie, contexte):
    """``(serie, etape)`` — la série plafonnée, l'énergie écrêtée retirée."""
    from apps.calepinage.services.electrique import (
        MOTIF_ECRETAGE_SANS_SERIE, ecretage_depuis_serie,
    )

    contexte = contexte if isinstance(contexte, dict) else {}
    colonne = etapes.colonne_energie(serie)
    if colonne is None:
        return serie, etapes.etape_omise(LIBELLE, MOTIF_SERIE_ILLISIBLE)

    nombre = _nombre_d_onduleurs(contexte)
    if nombre is None:
        return serie, etapes.etape_omise(LIBELLE, MOTIF_SANS_ONDULEUR,
                                         champ='electrique.onduleurs')

    fiche = contexte.get('fiche_onduleur') or {}
    puissance_ac_kw = _puissance_ac_kw(contexte, fiche, nombre)
    if puissance_ac_kw is None:
        # LE motif de refus que le dépôt prononce déjà pour cette perte —
        # publié tel quel, et le champ absent est NOMMÉ à côté.
        return serie, etapes.etape_omise(LIBELLE, MOTIF_ECRETAGE_SANS_SERIE,
                                         champ=CHAMP_PUISSANCE_AC)

    borne_kw, base, mention = _borne_kw(contexte, fiche, nombre,
                                        puissance_ac_kw)
    facteur_kw = etapes.FACTEURS_KW[colonne]
    points = []
    puissances_kw = []
    for point in serie.get('points') or []:
        copie = dict(point)
        puissance_kw = _puissance_kw(point.get(colonne), facteur_kw)
        if puissance_kw is None:
            copie[COLONNE_ECRETAGE] = None
            points.append(copie)
            continue
        puissances_kw.append(puissance_kw)
        perdu = max(0.0, puissance_kw - borne_kw)
        copie[COLONNE_ECRETAGE] = perdu
        copie[colonne] = (puissance_kw - perdu) / facteur_kw
        points.append(copie)

    suite = dict(serie)
    suite['points'] = points
    suite['colonne_energie'] = colonne
    return suite, etapes.etape_appliquee(
        LIBELLE, source='fiche',
        entree={
            'borne_kw': round(borne_kw, 3),
            'base_borne': base,
            'mention': mention,
            'puissance_ac_kw': round(puissance_ac_kw, 3),
            'nombre_onduleurs': nombre,
            'colonne_plafonnee': colonne,
            'colonne_ecretage': COLONNE_ECRETAGE,
            # Le POURCENTAGE est celui de ``ecretage_depuis_serie`` (CAL127) :
            # une seule formule d'écrêtage dans le dépôt, deux lecteurs.
            'ecretage_pct': ecretage_depuis_serie(puissances_kw, borne_kw),
            'heures_ecretees': sum(1 for valeur in puissances_kw
                                   if valeur > borne_kw + 1e-9),
        },
        reference=REFERENCE_ECRETAGE)


# ── la borne, et d'où vient chacun de ses deux termes ────────────────────

def _borne_kw(contexte, fiche, nombre, puissance_ac_kw):
    """``(borne_kw, base, mention)`` — jamais un cos φ supposé."""
    cos_phi, source_cos_phi = _cos_phi_impose(contexte)
    if cos_phi is None:
        return (puissance_ac_kw, CHAMP_PUISSANCE_AC, MENTION_COS_PHI_ABSENT)

    s_max_kva = _nombre(fiche.get('s_max_kva'))
    if s_max_kva is None or s_max_kva <= 0:
        return (puissance_ac_kw, CHAMP_PUISSANCE_AC, MENTION_S_MAX_ABSENTE)

    apparente_kw = s_max_kva * nombre * cos_phi
    if apparente_kw < puissance_ac_kw:
        return (apparente_kw,
                '%s × %s' % (CHAMP_S_MAX, CHAMP_COS_PHI),
                "borne apparente retenue : %s kVA × cos φ %s (source : %s) "
                "sous la puissance active de l'onduleur"
                % (s_max_kva * nombre, cos_phi, source_cos_phi))
    return (puissance_ac_kw, CHAMP_PUISSANCE_AC,
            "cos φ %s saisi (source : %s) : la puissance apparente bornée "
            "reste au-dessus de la puissance active, qui plafonne donc "
            "l'injection" % (cos_phi, source_cos_phi))


def _cos_phi_impose(contexte):
    """``(cos_phi, source)`` du raccordement SAISI, ou ``(None, '')``.

    Le cos φ n'existe que SAISI **et** SOURCÉ (contrat CALX205 : une valeur
    sans ``source_cos_phi`` est refusée). Hors de [0 ; 1], il n'est pas un
    cos φ : l'étape le traite comme non saisi plutôt que de l'appliquer.
    """
    saisie = contexte.get('raccordement')
    if isinstance(saisie, dict) and isinstance(saisie.get('saisie'), dict):
        saisie = saisie['saisie']
    if not isinstance(saisie, dict):
        return (None, '')
    valeur = _nombre(saisie.get('cos_phi_impose'))
    source = str(saisie.get('source_cos_phi') or '').strip()
    if valeur is None or not source or valeur <= 0.0 or valeur > 1.0:
        return (None, '')
    return (valeur, source)


def _puissance_ac_kw(contexte, fiche, nombre):
    """La puissance ACTIVE réellement installée, ou ``None`` si la fiche se tait."""
    for onduleur in _onduleurs(contexte):
        taille = _nombre(onduleur.get('taille_kw'))
        if taille and taille > 0:
            return taille * nombre
    unitaire = _nombre(fiche.get('ac_kw'))
    if unitaire and unitaire > 0:
        return unitaire * nombre
    return None


def _nombre_d_onduleurs(contexte):
    """Le nombre d'onduleurs retenus, ou ``None`` si le bloc ne le dit pas."""
    for onduleur in _onduleurs(contexte):
        nombre = _nombre(onduleur.get('nombre'))
        if nombre and nombre > 0:
            return int(nombre)
    return None


def _onduleurs(contexte):
    electrique = contexte.get('electrique')
    if not isinstance(electrique, dict):
        return ()
    return tuple(onduleur for onduleur in electrique.get('onduleurs') or ()
                 if isinstance(onduleur, dict))


def _puissance_kw(valeur, facteur_kw):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur) * facteur_kw
    except (TypeError, ValueError):
        return None


def _nombre(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None
