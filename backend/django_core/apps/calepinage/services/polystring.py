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
    # CALX207 — l'écart de puissance d'un groupe, et son verdict SOCIÉTÉ.
    'CODE_VERDICT_TOLERANCE', 'CLE_TOLERANCE_ACCEPTABLE',
    'CLE_TOLERANCE_BLOQUANTE', 'STATUT_OK', 'STATUT_ALERTE',
    'STATUT_BLOQUANT', 'STATUT_OMIS', 'MOTIF_SANS_SEUIL',
    'REFERENCE_TOLERANCE_PVSOL', 'ecart_de_groupe',
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


# ═══════════════════════════════════════════════════════════════════════════
# CALX207 — L'ÉCART DE PUISSANCE D'UN GROUPE, ET SON VERDICT SOCIÉTÉ
# ═══════════════════════════════════════════════════════════════════════════
#
# CE QUI MANQUAIT. Rien, ni dans ``core/electrique/`` ni dans
# ``services/chaines.py``, ne compare DEUX sous-champs entre eux : le seul
# écart mesuré est le courant par entrée. Or mettre un versant est et un
# versant ouest sur une même entrée MPPT n'a de sens que si les deux pèsent à
# peu près le même poids — le suiveur de puissance ne poursuit qu'un seul
# point, et l'écart se paie toute la journée sur la branche la plus faible.
#
# CE QUI EST MESURÉ, ET CE QUI NE L'EST PAS. L'écart porte sur la PUISSANCE
# CRÊTE de chaque branche, chacune à SON orientation — l'orientation est
# PUBLIÉE à côté du chiffre, jamais convertie en coefficient : appliquer un
# facteur d'irradiance ici reviendrait à inventer un modèle de production
# dans un module de câblage (W3 : aucun kWh dans ce lot).
#
# LES DEUX SEUILS SONT DES RÉGLAGES SOCIÉTÉ, ET ILS N'ONT AUCUN DÉFAUT.
# PV*SOL chiffre sa propre tolérance (« up to 4 % » acceptable, « exceeding
# 10 % » bloquant) ; ces chiffres restent une RÉFÉRENCE D'OUTIL affichée en
# aide à la saisie — jamais une valeur préremplie (D-CALX 7). Sans seuil
# saisi, l'écart est publié et le verdict vaut ``omis`` en nommant les deux
# clés à régler. Un seuil saisi SANS source est refusé en nommant son champ :
# un seuil dont personne ne dit d'où il sort ne peut pas fonder un refus.
#
# LES DEUX CLÉS EXISTENT DÉJÀ au registre des réglages société
# (``services/parametres_cles.py``, section ``electrique_societe``, posées
# par CALX145 avec leur référence doctrinale PV*SOL) : cette tâche les LIT,
# elle n'en déclare pas de nouvelles — deux clés pour une même grandeur
# seraient exactement ce que le registre existe pour empêcher.

#: Le CODE stable du verdict — c'est par lui qu'un test ou un écran le
#: désigne, jamais par sa position dans une liste (CALX215).
CODE_VERDICT_TOLERANCE = 'polystring_tolerance'

#: Les deux clés du registre des réglages société (section
#: ``electrique_societe``). Aucune valeur ici : le registre dit qu'elles
#: EXISTENT, jamais ce qu'elles valent.
CLE_TOLERANCE_ACCEPTABLE = 'tolerance_polystring_acceptable_pct'
CLE_TOLERANCE_BLOQUANTE = 'tolerance_polystring_bloquante_pct'

#: Les quatre statuts d'un verdict de ce module — même vocabulaire que les
#: verdicts du contrat de raccordement (``calepinage_raccordement.json``).
STATUT_OK = 'ok'
STATUT_ALERTE = 'alerte'
STATUT_BLOQUANT = 'bloquant'
STATUT_OMIS = 'omis'

MOTIF_SANS_SEUIL = (
    "aucun seuil de tolérance saisi : l'écart de puissance du groupe est "
    "publié, mais aucun verdict n'est prononcé. Réglez « %s » et/ou « %s » "
    "avec leur source dans les réglages du module."
    % (CLE_TOLERANCE_ACCEPTABLE, CLE_TOLERANCE_BLOQUANTE))

MOTIF_SANS_MESURE = (
    "écart non mesurable : il faut au moins DEUX branches dont la puissance "
    "crête est connue pour comparer un groupe à lui-même.")

LIBELLE_VERDICT_TOLERANCE = (
    "Écart de puissance entre les branches du groupe polystring")

REFERENCE_TOLERANCE_PVSOL = (
    "PV*SOL — Polystring connection : le logiciel tient un écart « up to "
    "4 % » pour acceptable et « exceeding 10 % » pour bloquant "
    "(https://help.valentin-software.com/pvsol/en/pages/inverters/"
    "polystring-connection/). Ces chiffres sont AFFICHÉS EN AIDE à la "
    "saisie des deux réglages société, jamais préremplis.")


def ecart_de_groupe(groupe, *, reglages=None):
    """CALX207 — l'écart de puissance crête d'un groupe, et son verdict.

    Args:
        groupe: un groupe publié par :func:`grouper_polystring` (il porte
            ``branches``, une par pan, avec sa ``puissance_kwc`` et son
            orientation).
        reglages: la section ``electrique_societe`` des réglages société,
            ``{clé: {valeur, source, reference}}``. Absente, les deux seuils
            sont non saisis et le verdict vaut ``omis``.

    Returns:
        ``{ecart_pct, base, detail, verdict}``. ``ecart_pct`` vaut ``None``
        quand moins de deux branches publient une puissance : aucun écart
        n'est alors inventé, et ``base`` dit pourquoi.

    Raises:
        PolystringRefuse: un seuil saisi SANS ``source`` — champ fautif NOMMÉ.
    """
    mesures = _mesures_des_branches(groupe)
    acceptable = _seuil(reglages, CLE_TOLERANCE_ACCEPTABLE)
    bloquante = _seuil(reglages, CLE_TOLERANCE_BLOQUANTE)

    if len(mesures) < 2:
        return {
            'ecart_pct': None,
            'base': MOTIF_SANS_MESURE,
            'detail': mesures,
            'verdict': _verdict_tolerance(None, acceptable, bloquante),
        }

    haute = max(mesures, key=lambda m: m['puissance_kwc'])
    basse = min(mesures, key=lambda m: m['puissance_kwc'])
    ecart_pct = round(
        (haute['puissance_kwc'] - basse['puissance_kwc'])
        * 100.0 / haute['puissance_kwc'], 3)
    for mesure in mesures:
        mesure['ecart_a_la_branche_haute_pct'] = round(
            (haute['puissance_kwc'] - mesure['puissance_kwc'])
            * 100.0 / haute['puissance_kwc'], 3)
    base = ("puissance crête la plus élevée du groupe : %s kWc sur le pan "
            "« %s » ; la plus faible : %s kWc sur le pan « %s ». Chaque "
            "branche est mesurée À SON ORIENTATION, publiée à côté du "
            "chiffre — aucun coefficient d'irradiance n'est appliqué ici."
            % (haute['puissance_kwc'], haute['pan'],
               basse['puissance_kwc'], basse['pan']))
    return {
        'ecart_pct': ecart_pct,
        'base': base,
        'detail': mesures,
        'verdict': _verdict_tolerance(ecart_pct, acceptable, bloquante),
    }


def _mesures_des_branches(groupe):
    """Les branches dont la puissance crête est CONNUE, et leur orientation."""
    mesures = []
    for branche in (groupe or {}).get('branches') or ():
        if not isinstance(branche, dict):
            continue
        puissance = branche.get('puissance_kwc')
        if puissance is None or isinstance(puissance, bool):
            continue
        try:
            valeur = float(puissance)
        except (TypeError, ValueError):
            continue
        if valeur <= 0:
            continue
        mesures.append({
            'pan': branche.get('pan'),
            'puissance_kwc': valeur,
            'modules': branche.get('modules'),
            'azimut_deg': branche.get('azimut_deg'),
            'inclinaison_deg': branche.get('inclinaison_deg'),
            'source_orientation': branche.get('source_orientation'),
        })
    return mesures


def _seuil(reglages, cle):
    """``{valeur, source, reference, cle}`` d'un seuil SAISI, ou ``None``.

    Une saisie sans ``source`` n'est pas « non saisie » : elle est FAUTIVE, et
    l'utilisateur doit l'apprendre SUR le champ concerné plutôt que de voir
    son seuil ignoré en silence (règle fondateur 08/09/2026).
    """
    saisie = (reglages or {}).get(cle)
    if saisie is None:
        return None
    if not isinstance(saisie, dict):
        raise PolystringRefuse(
            "Le seuil de tolérance « %s » doit être saisi sous la forme "
            "« {valeur, source} » (reçu : %s)."
            % (cle, type(saisie).__name__), champ=cle)
    valeur = saisie.get('valeur')
    if valeur is None:
        return None
    if not saisie.get('source'):
        raise PolystringRefuse(
            "Le seuil de tolérance « %s » est saisi sans source : un seuil "
            "dont personne ne dit d'où il sort ne peut pas fonder un refus. "
            "Renseignez sa provenance (société, mesure, saisie ou texte "
            "cité)." % cle, champ='%s.source' % cle)
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        raise PolystringRefuse(
            "Le seuil de tolérance « %s » n'est pas un nombre (reçu : %r)."
            % (cle, valeur), champ=cle) from None
    return {'valeur': nombre, 'source': str(saisie['source']),
            'reference': saisie.get('reference') or '', 'cle': cle}


def _verdict_tolerance(ecart_pct, acceptable, bloquante):
    """Le verdict de tolérance — ``omis`` tant qu'aucun seuil n'est saisi."""
    if acceptable is None and bloquante is None:
        return _verdict(STATUT_OMIS, MOTIF_SANS_SEUIL, source=None,
                        borne=None, valeur=ecart_pct)
    if ecart_pct is None:
        return _verdict(STATUT_OMIS, MOTIF_SANS_MESURE, source=None,
                        borne=None, valeur=None)
    if bloquante is not None and ecart_pct > bloquante['valeur'] + 1e-9:
        return _verdict(
            STATUT_BLOQUANT,
            "écart de %s %% au-dessus du seuil BLOQUANT de %s %% : les deux "
            "branches sont trop dissemblables pour partager une entrée MPPT."
            % (ecart_pct, bloquante['valeur']),
            source=bloquante, borne=bloquante['valeur'], valeur=ecart_pct)
    if acceptable is not None and ecart_pct > acceptable['valeur'] + 1e-9:
        plafond = bloquante['valeur'] if bloquante is not None else None
        return _verdict(
            STATUT_ALERTE,
            "écart de %s %% au-dessus du seuil ACCEPTABLE de %s %%%s : le "
            "montage tient, c'est la branche la plus faible qui sera suivie."
            % (ecart_pct, acceptable['valeur'],
               (', sous le seuil bloquant de %s %%' % plafond)
               if plafond is not None else ''),
            source=acceptable, borne=acceptable['valeur'], valeur=ecart_pct)
    retenu = acceptable if acceptable is not None else bloquante
    return _verdict(
        STATUT_OK,
        "écart de %s %% sous le seuil de %s %% saisi par la société."
        % (ecart_pct, retenu['valeur']),
        source=retenu, borne=retenu['valeur'], valeur=ecart_pct)


def _verdict(statut, detail, *, source, borne, valeur):
    """La forme publiée d'un verdict — les huit clés TOUJOURS présentes."""
    return {
        'code': CODE_VERDICT_TOLERANCE,
        'libelle': LIBELLE_VERDICT_TOLERANCE,
        'statut': statut,
        'detail': detail,
        'valeur': valeur,
        'borne': borne,
        'source': (None if source is None
                   else '%s — %s' % (source['cle'], source['source'])),
        'reference': ((source or {}).get('reference')
                      or REFERENCE_TOLERANCE_PVSOL),
    }
