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


#: ACAL675 — la question « coupure d'urgence DC / arrêt rapide exigé ? » : la
#: réponse est celle du DOSSIER (``protections.exigences.arret_rapide``), jamais
#: une règle écrite par le logiciel — aucune norme n'est inventée ici.
LIBELLE_ARRET_RAPIDE = "Coupure d'urgence DC / arrêt rapide exigé ?"
DESIGNATION_ARRET_RAPIDE = "Coupure d'urgence DC (arrêt rapide)"
MOTIF_EXIGE_DOSSIER = 'exigé par le dossier'
_REPONSES = {'oui': True, 'non': False, True: True, False: False}


#: ACAL1973 — par question, son libellé SEUL (l'étiquette que l'écran affiche)
#: et le champ où sa réponse s'enregistre.
_QUESTIONS = {
    'ARRET_RAPIDE': (LIBELLE_ARRET_RAPIDE, 'protections.exigences.arret_rapide'),
    'PARATONNERRE': ('Paratonnerre : distance de séparation',
                     'protections.exigences.paratonnerre')}


def _question(code, libelle, statut):
    question, champ = next(valeur for prefixe, valeur in _QUESTIONS.items()
                           if code.startswith(prefixe))
    return {'code': code, 'libelle': libelle, 'statut': statut,
            'question': question, 'champ': champ}


def questions_du_dossier(decisions, reglages=None):
    """ACAL1973 — les questions du DOSSIER (``protections.questions``),
    servies par l'évaluation électrique et reprises par la check-list.
    Lecture tolérante : une réponse illisible laisse la question posée,
    « non renseigné » (le refus nommé reste à l'enregistrement)."""
    if not isinstance(decisions, dict) or not isinstance(
            decisions.get('exigences') or {}, dict):
        decisions = None
    try:
        question = _arret_rapide(decisions, 1)[1]
    except DecisionInvalide:
        question = _arret_rapide(None, 1)[1]
    return [question] + [q for q in (_paratonnerre(decisions, reglages),) if q]


def _arret_rapide(decisions, rang):
    """ACAL675 — ``(organe ajouté ou None, question)`` de la réponse saisie.

    « oui » ajoute l'organe d'origine ``societe`` (repère ``SOC<rang>``) ;
    « non » n'ajoute rien et le dit ; absent : « non renseigné ».
    """
    brut = ((decisions or {}).get('exigences') or {}).get('arret_rapide')
    if brut in (None, ''):
        return None, _question(
            'ARRET_RAPIDE_NON_RENSEIGNE',
            '%s — non renseigné' % LIBELLE_ARRET_RAPIDE, 'non_renseigne')
    reponse = _REPONSES.get(brut.strip().lower() if isinstance(brut, str)
                            else brut)
    if reponse is None:
        raise DecisionInvalide(
            "« arret_rapide » : répondez « oui » ou « non » (reçu : « %s »)."
            % brut, champ='protections.exigences.arret_rapide')
    if not reponse:
        return None, _question(
            'ARRET_RAPIDE_NON_EXIGE',
            '%s — non exigé' % LIBELLE_ARRET_RAPIDE, 'non_exige')
    organe = _ajout({'designation': DESIGNATION_ARRET_RAPIDE,
                     'motif': MOTIF_EXIGE_DOSSIER, 'cote': 'dc'}, rang)
    return organe, _question(
        'ARRET_RAPIDE_EXIGE',
        '%s — oui (%s)' % (LIBELLE_ARRET_RAPIDE, MOTIF_EXIGE_DOSSIER),
        'exige')


#: ACAL676 — le réglage société de la distance de séparation foudre MINIMALE :
#: valeur + source, vide par défaut. Le logiciel ne fixe AUCUNE distance (règle
#: d'étude foudre) : sans valeur saisie, aucun verdict n'est inventé.
CLE_DISTANCE_FOUDRE = 'distance_separation_foudre_min_m'


def _metres(valeur):
    return ('%g' % valeur).replace('.', ',')


def _paratonnerre(decisions, reglages):
    """ACAL676 — la question de distance de séparation, ou ``None``.

    Posée seulement quand un paratonnerre est DÉCLARÉ
    (``protections.exigences.paratonnerre = {present, distance_separation_m}``).
    """
    from .raccordement import _reglage
    from .valeurs import nombre

    brut = ((decisions or {}).get('exigences') or {}).get('paratonnerre')
    if not isinstance(brut, dict) or _REPONSES.get(
            str(brut.get('present')).strip().lower()
            if isinstance(brut.get('present'), str)
            else brut.get('present')) is not True:
        return None
    minimum, _source = _reglage(reglages, CLE_DISTANCE_FOUDRE)
    distance = nombre(brut.get('distance_separation_m'))
    if minimum is None:
        return _question(
            'PARATONNERRE_DISTANCE_NON_CONTROLEE',
            'Paratonnerre : distance non contrôlée : valeur minimale non '
            'saisie', 'non_controle')
    if distance is None:
        return _question(
            'PARATONNERRE_DISTANCE_NON_RENSEIGNEE',
            'Paratonnerre : distance de séparation non saisie',
            'non_renseigne')
    if distance < minimum:
        return _question(
            'PARATONNERRE_DISTANCE_SOUS_MINIMUM',
            'Paratonnerre : distance %s m inférieure au minimum %s m saisi '
            'par la société' % (_metres(distance), _metres(minimum)),
            'a_surveiller')
    return _question(
        'PARATONNERRE_DISTANCE_CONFORME',
        'Paratonnerre : distance %s m, au moins égale au minimum %s m saisi '
        'par la société' % (_metres(distance), _metres(minimum)), 'conforme')


def checklist_protections(conception, *, decisions=None, norme=None,
                          reglages=None):
    """CAL132 — la check-list complète, éditable, chaque ligne gardant sa source.

    Args:
        conception: la ``Conception`` de CAL124 (chaînes déjà calculées).
        decisions: ``{'ajouts': [...], 'ecartes': [{repere, motif}]}`` — les
            décisions SOCIÉTÉ, enregistrées sur le calepinage.
        reglages: la section ``electrique_societe`` des réglages société
            (ACAL676 : distance de séparation foudre minimale).
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
                'omissions': [norme.get('motif') or _sans_norme()],
                'questions': []}
    if conception.fiche_incomplete or conception.resultat is None \
            or not conception.chaines:
        return {'organes': [], 'justifications': [],
                'omissions': ["aucune chaîne calculée : il n'y a pas d'organe "
                              "de protection à décider"],
                'questions': []}

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

    # ACAL675 — les exigences du dossier : questions posées, organe ajouté.
    organe, _question_posee = _arret_rapide(
        decisions, len((decisions or {}).get('ajouts') or ()) + 1)
    if organe is not None:
        organes.append(organe)

    return {
        'organes': organes,
        'justifications': list(resultat.justifications),
        'omissions': [],
        'questions': questions_du_dossier(decisions, reglages),
    }


def resultat_protections_retenues(resultat_protections, checklist):
    """ACAL159 — le ``ResultatProtections`` du noyau RÉDUIT à la check-list.

    LA source unique de ce que le bordereau (``core.electrique.nomenclature``)
    chiffre et de ce que le schéma dessine : un organe ÉCARTÉ disparaît, un
    organe AJOUTÉ par la société s'ajoute (marqué « décision société », jamais
    normatif). Lue par :func:`organes_retenus` — aucune seconde décision.

    Une check-list SANS organe (norme absente, aucune chaîne) laisse le
    résultat du noyau inchangé : il n'y a alors rien à décider.
    """
    import dataclasses

    from core.electrique.types import Protection

    if resultat_protections is None or not isinstance(checklist, dict) \
            or not checklist.get('organes'):
        return resultat_protections
    retenus = organes_retenus(checklist)
    reperes = {ligne['repere'] for ligne in retenus
               if ligne.get('origine') != ORIGINE_SOCIETE}
    gardees = tuple(protection
                    for protection in resultat_protections.protections
                    if protection.repere in reperes)
    ajouts = tuple(
        Protection(repere=ligne['repere'], designation=ligne['designation'],
                   calibre=ligne.get('calibre') or '',
                   quantite=int(ligne.get('quantite') or 1),
                   regle_source=ligne['regle_source'],
                   cote=ligne.get('cote') or 'commun')
        for ligne in retenus if ligne.get('origine') == ORIGINE_SOCIETE)
    return dataclasses.replace(resultat_protections,
                               protections=gardees + ajouts)


def organes_retenus(checklist):
    """LA source unique du bordereau et du schéma unifilaire.

    La nomenclature et le schéma lisent CETTE liste — pas une seconde
    décision prise ailleurs. Un organe écarté n'y figure pas ; un organe
    ajouté par la société y figure, marqué comme tel.
    """
    return [ligne for ligne in (checklist or {}).get('organes') or ()
            if ligne.get('retenu')]


def _sans_norme():
    """ACAL1338 — le texte unique sans norme choisie (``norme.MOTIF_SANS_NORME``)."""
    from .norme import MOTIF_SANS_NORME

    return MOTIF_SANS_NORME % ''
