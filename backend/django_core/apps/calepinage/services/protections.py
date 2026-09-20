"""CAL132 — la check-list de protections, PARAMÉTRABLE et traçable.

LE DÉFAUT CORRIGÉ
-----------------
``core/electrique/protections.py::concevoir_protections`` décide déjà chaque
organe en CITANT sa règle (``regle_source``) — fusibles de chaîne à partir de
3 chaînes en parallèle (IEC 62548 §7.3.3), parafoudre DC au-delà de 10 m
(UTE C 15-712-1), sectionneur DC toujours, DDR 300 mA en régime TT
(NF C 15-100 §411.5)… Mais la décision est BINAIRE et non révisable : un
bureau d'études qui IMPOSE un parafoudre malgré une liaison courte n'a aucun
moyen de l'ajouter sans mentir sur la règle.

LA FORME PUBLIÉE : UNE LIGNE, UNE ORIGINE
------------------------------------------
Chaque organe porte son ``origine`` :

* ``regle``   — retenu par le moteur, avec sa règle normative citée ;
* ``societe`` — AJOUTÉ à la main : marqué « décision société », et JAMAIS
  présenté comme normatif (c'est le mensonge que cette tâche empêche) ;
* ``ecarte``  — écarté, avec le MOTIF ÉCRIT exigé (un organe exigé par une
  règle ne disparaît pas en silence : il reste dans la liste, barré, avec la
  raison).

SOURCE UNIQUE : la nomenclature et le schéma unifilaire lisent CETTE liste
(``organes_retenus``), jamais une seconde décision prise ailleurs — sinon le
schéma dessinerait un organe que le bordereau ne chiffre pas (c'est exactement
l'incident du 24/08/2026 sur les côtés DC/AC).

RÈGLE D5 (CAL130) : sans norme électrique sélectionnée, la check-list est
OMISE. Toutes ses règles sont normatives et françaises ; les appliquer à une
société qui n'a choisi aucune norme les imprimerait sans mandat.
"""
from __future__ import annotations

__all__ = [
    'ORIGINE_REGLE', 'ORIGINE_SOCIETE', 'ORIGINE_ECARTE',
    'DecisionInvalide', 'checklist_protections', 'organes_retenus',
]

ORIGINE_REGLE = 'regle'
ORIGINE_SOCIETE = 'societe'
ORIGINE_ECARTE = 'ecarte'

#: La mention portée par un organe ajouté à la main. Elle n'est PAS une
#: référence normative, et c'est tout l'intérêt : un lecteur doit pouvoir
#: distinguer « la règle l'exige » de « nous avons choisi de le poser ».
MENTION_SOCIETE = 'décision société'


class DecisionInvalide(ValueError):
    """Refus d'une décision de check-list — champ fautif NOMMÉ."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def _ligne(protection):
    """Un organe du moteur, publié avec son origine et sa règle citée."""
    return {
        'repere': protection.repere,
        'designation': protection.designation,
        'calibre': protection.calibre,
        'quantite': protection.quantite,
        'cote': protection.cote,
        'origine': ORIGINE_REGLE,
        'regle_source': protection.regle_source,
        'motif': '',
        'retenu': True,
    }


def _ajout(brut, rang):
    """Un organe AJOUTÉ par la société — jamais présenté comme normatif."""
    if not isinstance(brut, dict):
        raise DecisionInvalide(
            "Chaque organe ajouté doit être un objet "
            "{repere, designation, calibre, quantite, motif}.",
            champ='protections.ajouts')
    designation = (brut.get('designation') or '').strip()
    motif = (brut.get('motif') or '').strip()
    if not designation:
        raise DecisionInvalide(
            "Organe ajouté sans désignation : renseignez « Désignation » "
            "pour savoir ce qui est posé.",
            champ='protections.ajouts.designation')
    if not motif:
        raise DecisionInvalide(
            "Organe ajouté sans motif : un organe posé hors règle doit dire "
            "POURQUOI (il sera marqué « %s », jamais comme une exigence "
            "normative)." % MENTION_SOCIETE,
            champ='protections.ajouts.motif')
    try:
        quantite = int(brut.get('quantite') or 1)
    except (TypeError, ValueError):
        raise DecisionInvalide(
            "Organe ajouté « %s » : quantité illisible." % designation,
            champ='protections.ajouts.quantite')
    return {
        'repere': (brut.get('repere') or 'SOC%d' % rang).strip(),
        'designation': designation,
        'calibre': (brut.get('calibre') or '').strip(),
        'quantite': max(1, quantite),
        'cote': (brut.get('cote') or 'commun').strip().lower(),
        'origine': ORIGINE_SOCIETE,
        # AUCUNE référence normative n'est acceptée d'un corps de requête :
        # la source d'un organe ajouté est la décision elle-même.
        'regle_source': '%s — %s' % (MENTION_SOCIETE, motif),
        'motif': motif,
        'retenu': True,
    }


def _ecarts(decisions):
    """``{repere: motif}`` — un écart sans motif écrit est REFUSÉ."""
    ecartes = {}
    for brut in (decisions or {}).get('ecartes') or ():
        if not isinstance(brut, dict):
            raise DecisionInvalide(
                "Chaque organe écarté doit être un objet {repere, motif}.",
                champ='protections.ecartes')
        repere = (brut.get('repere') or '').strip()
        motif = (brut.get('motif') or '').strip()
        if not repere:
            raise DecisionInvalide(
                "Organe écarté sans repère : indiquez LEQUEL est écarté.",
                champ='protections.ecartes.repere')
        if not motif:
            raise DecisionInvalide(
                "Organe « %s » écarté sans motif : écarter un organe exigé "
                "par une règle demande une justification écrite." % repere,
                champ='protections.ecartes.motif')
        ecartes[repere] = motif
    return ecartes


def checklist_protections(conception, *, decisions=None, norme=None):
    """CAL132 — la check-list complète, éditable, chaque ligne gardant sa source.

    Args:
        conception: la ``Conception`` de CAL124 (chaînes déjà calculées).
        decisions: ``{'ajouts': [...], 'ecartes': [{repere, motif}]}`` — les
            décisions SOCIÉTÉ, enregistrées sur le calepinage.
        norme: le verdict de ``services.norme.norme_applicable``.

    Returns:
        ``{organes, omissions, justifications}``. Un organe écarté reste dans
        la liste avec ``retenu: False`` et son motif : barré, jamais effacé.

    Raises:
        DecisionInvalide: décision incomplète (ajout sans motif, écart sans
            motif ou sans repère…), champ fautif nommé, message français.
    """
    from core.electrique.protections import concevoir_protections

    from .chaines import evaluer_onduleurs

    if norme is not None and not norme.get('applicable', False):
        return {'organes': [], 'justifications': [],
                'omissions': [norme.get('motif') or
                              "aucune norme électrique sélectionnée : "
                              "check-list de protections OMISE"]}
    if conception.fiche_incomplete or conception.resultat is None \
            or not conception.chaines:
        return {'organes': [], 'justifications': [],
                'omissions': ["aucune chaîne calculée : il n'y a pas d'organe "
                              "de protection à décider"]}

    resultat = concevoir_protections(conception.entree, conception.resultat,
                                     evaluer_onduleurs(conception))
    ecartes = _ecarts(decisions)
    organes = []
    for protection in resultat.protections:
        ligne = _ligne(protection)
        if ligne['repere'] in ecartes:
            ligne['retenu'] = False
            ligne['origine'] = ORIGINE_ECARTE
            ligne['motif'] = ecartes[ligne['repere']]
        organes.append(ligne)

    reperes_connus = {ligne['repere'] for ligne in organes}
    inconnus = sorted(set(ecartes) - reperes_connus)
    if inconnus:
        raise DecisionInvalide(
            "Organe(s) écarté(s) inconnu(s) : « %s ». La check-list ne "
            "contient que : %s."
            % (', '.join(inconnus), ', '.join(sorted(reperes_connus))),
            champ='protections.ecartes.repere')

    for rang, brut in enumerate((decisions or {}).get('ajouts') or (),
                                start=1):
        organes.append(_ajout(brut, rang))

    return {
        'organes': organes,
        'justifications': list(resultat.justifications),
        'omissions': [],
    }


def organes_retenus(checklist):
    """LA source unique du bordereau et du schéma unifilaire.

    La nomenclature et le schéma lisent CETTE liste — pas une seconde
    décision prise ailleurs. Un organe écarté n'y figure pas ; un organe
    ajouté par la société y figure, marqué comme tel.
    """
    return [ligne for ligne in (checklist or {}).get('organes') or ()
            if ligne.get('retenu')]
