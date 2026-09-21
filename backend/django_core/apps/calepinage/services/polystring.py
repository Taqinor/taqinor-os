"""CALX206 — PLUSIEURS ORIENTATIONS SUR UNE ENTRÉE MPPT, JAMAIS DANS UNE CHAÎNE.

CE QUI MANQUAIT
----------------
``services/chaines.py`` grave la règle de physique
:data:`~apps.calepinage.services.chaines.REGLE_UNE_ORIENTATION_PAR_CHAINE` —
« une CHAÎNE ne porte qu'une seule orientation » — et ``concevoir_par_pan``
chaîne pan par pan, puis ``_allouer_mppt`` distribue les pans sur les entrées
DISPONIBLES. Il n'existait donc aucun chemin pour raccorder DEUX pans
d'azimuts différents sur la MÊME entrée MPPT, ce que l'est/ouest résidentiel
exige tous les jours : deux versants de 8 modules, un onduleur à deux
entrées, et la moitié du champ qu'on voudrait doubler sur une seule entrée.

CE QUI EST OUVERT, ET CE QUI NE L'EST PAS
-------------------------------------------
PV*SOL nomme cela « polystring » et laisse « completely different PV modules
or strings » partager un MPP tracker, EN PARALLÈLE par défaut
(https://help.valentin-software.com/pvsol/en/pages/inverters/polystring-connection/).

C'est exactement — et uniquement — ce que ce service ouvre :

* la MISE EN PARALLÈLE de chaînes de pans différents sur une même entrée ;
* chaque pan garde SES PROPRES chaînes, calculées à SA propre orientation :
  la règle « une chaîne = une orientation » reste INTACTE, et une saisie qui
  demanderait la mise en SÉRIE de deux pans est REFUSÉE en la citant.

Sans saisie de groupe, RIEN ne bouge : les chaînes rendues sont les objets
mêmes que ``concevoir_par_pan`` a produits, entrée MPPT comprise. Le
comportement d'aujourd'hui est donc strictement conservé (D12).

LE COURANT EST RECALCULÉ PAR LE NOYAU, PAS ICI
------------------------------------------------
Mettre deux pans en parallèle sur une entrée ADDITIONNE leurs Isc et leurs
Imp — c'est précisément le contrôle de l'incident DEV-202608-0016. Le cumul
n'est donc pas recalculé dans ce module : il est demandé à
``core.electrique.chaines._verdicts_courant``, qui le prononce déjà sur les
chaînes d'une même entrée (bornes de fiche ``isc_max_mppt_a`` et
``i_max_mppt_a``, sévérités comprises). Une seconde implémentation aurait
donné deux verdicts possibles pour un même montage.

AUCUN SEUIL N'EST POSÉ ICI (D-CALX 7) : ce module ne compare rien lui-même ;
il regroupe, puis il fait prononcer le noyau sur les bornes de la fiche.
"""
from __future__ import annotations

__all__ = [
    'COUPLAGE_PARALLELE', 'COUPLAGES_ADMIS', 'MOTIF_SANS_SAISIE',
    'MOTIF_SANS_CHAINES', 'PolystringRefuse', 'grouper_polystring',
]

#: Le SEUL couplage ouvert par CALX206 : la mise en parallèle sur une entrée
#: MPPT. PV*SOL le pose comme son défaut (lien en tête de module).
COUPLAGE_PARALLELE = 'parallele'

#: L'énumération FERMÉE des couplages admis dans une saisie de groupe. Toute
#: autre valeur — « serie » au premier chef — décrirait deux orientations
#: DANS une chaîne : elle est refusée en citant la règle.
COUPLAGES_ADMIS = (COUPLAGE_PARALLELE,)

MOTIF_SANS_SAISIE = (
    "Aucun groupe polystring saisi : la répartition des chaînes sur les "
    "entrées MPPT est celle d'aujourd'hui, inchangée. Le polystring est une "
    "DÉCISION de câblage, jamais un regroupement deviné.")

MOTIF_SANS_CHAINES = (
    "Aucune chaîne calculée sur ce calepinage : il n'y a rien à regrouper "
    "sur une entrée MPPT.")


class PolystringRefuse(ValueError):
    """Refus d'une SAISIE de groupes polystring, champ fautif NOMMÉ.

    ``champ`` porte le chemin exact de la saisie à corriger
    (``groupes.0.pans``) pour que l'écran pointe la bonne case au lieu
    d'afficher un « non enregistré » générique (règle fondateur 08/09/2026).
    """

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def grouper_polystring(conception, *, groupes=None):
    """Regroupe des PANS sur des entrées MPPT, sans jamais mélanger de chaîne.

    Args:
        conception: la ``Conception`` de CAL124 (chaînes déjà calculées).
        groupes: la SAISIE ``[{mppt, pans: [...], couplage}]`` —
            ``couplage`` est optionnel et vaut ``« parallele »``, le seul
            admis. ``None`` ou liste vide = aucun regroupement.

    Returns:
        ``{applique, couplage, motif, groupes, entrees, chaines, verdicts,
        bloquants, alertes}``. ``chaines`` est la répartition RETENUE : sans
        saisie, ce sont les objets mêmes de la conception.

    Raises:
        PolystringRefuse: saisie malformée, pan inconnu, pan réclamé deux
            fois, entrée MPPT que la fiche onduleur n'a pas, ou couplage
            autre que la mise en parallèle (règle d'orientation citée).
    """
    chaines_actuelles = tuple(conception.chaines)
    saisie = _saisie_normalisee(conception, groupes)

    if not saisie:
        return _rendu(
            applique=False,
            motif=(MOTIF_SANS_CHAINES if not chaines_actuelles
                   else MOTIF_SANS_SAISIE),
            groupes=[],
            chaines=chaines_actuelles,
            entrees=_entrees(chaines_actuelles),
            verdicts=(), bloquants=(), alertes=())

    par_pan = {}
    for rang, groupe in enumerate(saisie):
        for pan in groupe['pans']:
            par_pan[pan] = groupe['mppt']
        saisie[rang] = groupe

    chaines = tuple(
        _sur_entree(chaine, par_pan[chaine.pan])
        if chaine.pan in par_pan else chaine
        for chaine in chaines_actuelles)

    alertes = []
    verdicts = []
    bloquants = _verdicts_du_courant(conception, chaines, alertes, verdicts)

    detail = [_detail_du_groupe(conception, groupe, chaines)
              for groupe in saisie]
    return _rendu(
        applique=True, motif='', groupes=detail, chaines=chaines,
        entrees=_entrees(chaines), verdicts=tuple(verdicts),
        bloquants=tuple(bloquants), alertes=tuple(alertes))


# ── la saisie, lue et REFUSÉE en nommant son champ ────────────────────────

def _saisie_normalisee(conception, groupes):
    """La saisie validée, ou ``[]`` — chaque refus NOMME son champ."""
    if groupes in (None, '', (), []):
        return []
    if not isinstance(groupes, (list, tuple)):
        raise PolystringRefuse(
            "Les groupes polystring doivent être une liste d'objets "
            "« {mppt, pans} » (reçu : %s)." % type(groupes).__name__,
            champ='groupes')
    if not conception.chaines:
        raise PolystringRefuse(MOTIF_SANS_CHAINES, champ='groupes')

    labels = {pan.label for pan in conception.pans}
    entrees_fiche = _entrees_de_la_fiche(conception)
    reclames = {}
    normalises = []
    for rang, brut in enumerate(groupes):
        chemin = 'groupes.%d' % rang
        if not isinstance(brut, dict):
            raise PolystringRefuse(
                "Le groupe polystring n° %d doit être un objet "
                "« {mppt, pans} » (reçu : %s)."
                % (rang + 1, type(brut).__name__), champ=chemin)
        mppt = _entree_mppt(brut.get('mppt'), chemin, entrees_fiche)
        pans = _pans_du_groupe(brut.get('pans'), chemin, labels, reclames,
                               mppt)
        _refuser_couplage_non_parallele(brut.get('couplage'), chemin, pans)
        normalises.append({'mppt': mppt, 'pans': pans,
                           'couplage': COUPLAGE_PARALLELE})
    return normalises


def _entree_mppt(valeur, chemin, entrees_fiche):
    """Le numéro d'entrée MPPT saisi — entier ≥ 1, et publié par la fiche."""
    champ = '%s.mppt' % chemin
    try:
        mppt = int(valeur)
    except (TypeError, ValueError):
        raise PolystringRefuse(
            "Entrée MPPT du groupe polystring manquante ou illisible "
            "(reçu : %r) : indiquez le NUMÉRO de l'entrée sur laquelle les "
            "pans sont mis en parallèle." % (valeur,), champ=champ) from None
    if mppt < 1:
        raise PolystringRefuse(
            "Entrée MPPT %d invalide : les entrées d'un onduleur sont "
            "numérotées à partir de 1." % mppt, champ=champ)
    if entrees_fiche and mppt > entrees_fiche:
        raise PolystringRefuse(
            "Entrée MPPT %d inconnue : la fiche de l'onduleur retenu publie "
            "%d entrée(s) MPPT. Choisissez une entrée existante, ou corrigez "
            "la fiche." % (mppt, entrees_fiche), champ=champ)
    return mppt


def _pans_du_groupe(valeur, chemin, labels, reclames, mppt):
    """Les pans d'un groupe : connus du document, et réclamés une seule fois."""
    champ = '%s.pans' % chemin
    if not isinstance(valeur, (list, tuple)) or not valeur:
        raise PolystringRefuse(
            "Aucun pan dans ce groupe polystring : indiquez les pans mis en "
            "parallèle sur l'entrée MPPT %d." % mppt, champ=champ)
    pans = []
    for rang, brut in enumerate(valeur):
        label = str(brut or '').strip()
        if not label or label not in labels:
            raise PolystringRefuse(
                "Pan « %s » inconnu du document de conception : les pans "
                "posés sont %s." % (label or brut,
                                    ', '.join(sorted(labels)) or 'aucun'),
                champ='%s.%d' % (champ, rang))
        if label in reclames:
            raise PolystringRefuse(
                "Pan « %s » réclamé par deux groupes polystring (entrées "
                "MPPT %d et %d) : un pan ne se câble que sur UNE entrée."
                % (label, reclames[label], mppt),
                champ='%s.%d' % (champ, rang))
        reclames[label] = mppt
        pans.append(label)
    return tuple(pans)


def _refuser_couplage_non_parallele(couplage, chemin, pans):
    """Tout couplage autre que le parallèle mélangerait DEUX orientations."""
    from .chaines import REGLE_UNE_ORIENTATION_PAR_CHAINE

    if couplage in (None, ''):
        return
    valeur = str(couplage).strip().lower()
    if valeur in COUPLAGES_ADMIS:
        return
    raise PolystringRefuse(
        "Couplage « %s » REFUSÉ pour les pans %s : %s. CALX206 n'ouvre que "
        "la mise en parallèle sur une entrée MPPT — chaque pan garde ses "
        "propres chaînes, calculées à sa propre orientation."
        % (couplage, ', '.join(pans), REGLE_UNE_ORIENTATION_PAR_CHAINE),
        champ='%s.couplage' % chemin)


# ── la répartition retenue, et ce que le noyau en dit ─────────────────────

def _sur_entree(chaine, mppt):
    """La MÊME chaîne, posée sur une autre entrée MPPT (copie pure)."""
    import dataclasses

    return dataclasses.replace(chaine, mppt=mppt)


def _verdicts_du_courant(conception, chaines, alertes, verdicts):
    """Le cumul d'Isc et d'Imp par entrée, prononcé PAR LE NOYAU.

    ``_verdicts_courant`` est privé au noyau parce qu'il n'a qu'un appelant
    (``concevoir_chaines``) ; il en a désormais deux, et l'appeler est le
    seul moyen de ne pas écrire une deuxième fois la comparaison qui a
    motivé l'incident DEV-202608-0016.
    """
    from core.electrique.chaines import _verdicts_courant

    onduleur = getattr(conception.entree, 'onduleur', None)
    if onduleur is None or not chaines:
        return []
    return _verdicts_courant(tuple(chaines), onduleur, alertes, verdicts)


def _entrees(chaines):
    """Le cumul PAR ENTRÉE MPPT : chaînes, pans, Isc et Imp additionnés."""
    par_mppt = {}
    for chaine in chaines:
        par_mppt.setdefault(chaine.mppt, []).append(chaine)
    return [{
        'mppt': mppt,
        'chaines': [c.repere for c in lot],
        'pans': sorted({c.pan for c in lot}),
        'isc_cumule_a': round(sum(c.isc_a for c in lot), 3),
        'imp_cumule_a': round(sum(c.imp_a for c in lot), 3),
    } for mppt, lot in sorted(par_mppt.items())]


def _detail_du_groupe(conception, groupe, chaines):
    """Un groupe PUBLIÉ : ses branches, une par pan, à leur orientation."""
    orientations = {pan.label: pan for pan in conception.pans}
    branches = []
    for label in groupe['pans']:
        lot = [c for c in chaines if c.pan == label]
        pan = orientations.get(label)
        branches.append({
            'pan': label,
            'chaines': [c.repere for c in lot],
            'modules': sum(c.nb_modules for c in lot),
            'puissance_kwc': round(sum(c.puissance_kwc for c in lot), 3),
            'azimut_deg': getattr(pan, 'azimut_deg', None),
            'inclinaison_deg': getattr(pan, 'inclinaison_deg', None),
            'source_orientation': getattr(pan, 'source_orientation', None),
            'isc_a': round(sum(c.isc_a for c in lot), 3) if lot else None,
            'imp_a': round(sum(c.imp_a for c in lot), 3) if lot else None,
        })
    lot_groupe = [c for c in chaines if c.pan in groupe['pans']]
    return {
        'mppt': groupe['mppt'],
        'couplage': groupe['couplage'],
        'pans': list(groupe['pans']),
        'branches': branches,
        'isc_cumule_a': round(sum(c.isc_a for c in lot_groupe), 3),
        'imp_cumule_a': round(sum(c.imp_a for c in lot_groupe), 3),
    }


def _entrees_de_la_fiche(conception):
    """Le nombre d'entrées MPPT PUBLIÉ par la fiche, ou ``0`` (non publié)."""
    onduleur = getattr(conception.entree, 'onduleur', None)
    try:
        return int(getattr(onduleur, 'n_mppt', 0) or 0)
    except (TypeError, ValueError):
        return 0


def _rendu(*, applique, motif, groupes, chaines, entrees, verdicts,
           bloquants, alertes):
    """La forme publiée — les neuf clés TOUJOURS présentes."""
    return {
        'applique': applique,
        'couplage': COUPLAGE_PARALLELE,
        'motif': motif,
        'groupes': groupes,
        'entrees': entrees,
        'chaines': chaines,
        'verdicts': tuple(verdicts),
        'bloquants': list(bloquants),
        'alertes': list(alertes),
    }
