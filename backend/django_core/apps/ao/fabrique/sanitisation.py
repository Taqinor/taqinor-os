"""AOF143 — sanitisation à DEUX NIVEAUX, contextuelle par champ.

Pourquoi ce n'est pas un grep
=============================
Un simple « refuser le mot *maximum* » casserait deux fois : il laisserait
passer un coût de revient présenté autrement, et il refuserait la phrase que
le dossier réel a précisément besoin d'écrire —

    « capacité démontrée 314 modules · engagement porté au bordereau 288 »

Cette phrase est VOULUE : c'est l'argument de sérieux du dossier, encadré par
« marché à prix unitaires » et par la clause de réserve (AOF126). Ce qui reste
interdit, c'est le **maximum AGRÉGÉ du site** (les bases internes ≈630 puis
618 : on ne communique JAMAIS un « max » au maître d'ouvrage) et tout chiffre
qu'aucun calcul ne démontre.

La règle est donc **contextuelle par champ** :

* un champ de portée ``client`` est soumis au lexique BLOQUANT complet ;
* un champ ``interne`` ou ``directeur`` ne l'est pas — c'est leur raison
  d'être, et les y soumettre reviendrait à interdire de faire son métier ;
* l'exception « démontrée … engagé » est reconnue par MOTIF et neutralise les
  règles de capacité SUR SON SEUL EMPAN, pas sur tout le document.

Deux niveaux
------------
* **BLOQUANT** — le rendu client est REFUSÉ, avec le mot cité, le champ et
  l'extrait. Pas de « nettoyage automatique » : réécrire silencieusement un
  document contractuel serait pire que le refus.
* **AVERTISSEMENT** — le rendu passe, avec une SUBSTITUTION CANONIQUE proposée
  (« client » → « décision d'études du <date> », « croquis » → « relevé
  contradictoire du <date> », « consigne client » → « prescription »). Ce sont
  des mots justes en interne et maladroits dans un pli administratif.

Module PUR : chaînes et dicts, aucun ORM, aucune I/O.
"""
from __future__ import annotations

import re

__all__ = [
    'BLOQUANT',
    'AVERTISSEMENT',
    'PORTEES_CONTROLEES',
    'SanitisationBloquante',
    'analyser',
    'sanitiser',
    'appliquer_substitutions',
    'empans_exception',
]

BLOQUANT = 'bloquant'
AVERTISSEMENT = 'avertissement'

#: Seules ces portées sont soumises au lexique bloquant. Un champ `interne` ou
#: `directeur` a le DROIT de parler de coût de revient — c'est son objet.
PORTEES_CONTROLEES = ('client',)


class SanitisationBloquante(Exception):
    """Levée quand un rendu client porte au moins un mot bloquant."""

    def __init__(self, constats):
        self.constats = list(constats)
        details = ' ; '.join(
            "{} — champ « {} » : « {} » dans « {} »".format(
                constat['code'], constat['champ'], constat['mot'],
                constat['extrait'])
            for constat in self.constats
        )
        super().__init__(
            "Rendu client REFUSÉ par la sanitisation : {}".format(details))


#: Exception CONTRÔLÉE, explicitement codée. « démontrée … engagé » dans une
#: même phrase : la capacité est présentée AVEC son engagement, ce qui est
#: exactement l'argument voulu. L'empan reconnu est soustrait des contrôles de
#: capacité — et de ceux-là seulement.
_MOTIF_EXCEPTION = re.compile(
    r'd[ée]montr[ée]{1,2}s?\b[^.;\n]{0,120}?\bengag[ée]',
    re.IGNORECASE,
)

_REGLES_BLOQUANTES = (
    ('COUT_ACHAT', r"prix\s+d['’]?\s*achat", "prix d'achat"),
    ('COUT_REVIENT', r"co[ûu]ts?\s+de\s+revient", 'coût de revient'),
    # « marge » NUE seulement : « marge de sécurité », « de robustesse »,
    # « de manœuvre », « d'implantation », « disponible » sont du vocabulaire
    # d'ingénieur et doivent passer. Interdire le mot en bloc ferait de cette
    # porte un obstacle qu'on apprend à contourner.
    ('MARGE',
     r"\bmarges?\b(?!\s*(?:de\s+(?:s[ée]curit[ée]|robustesse|man"
     r"|recul)|d['’]implantation|disponibles?|libres?))",
     'marge'),
    ('BENEFICE', r"b[ée]n[ée]fices?\b", 'bénéfice'),
    ('COEFFICIENT', r"coefficients?\s+(?:de\s+)?(?:vente|marge|prix)",
     'coefficient de vente'),
)

#: Règles de CAPACITÉ : celles que l'exception « démontrée … engagé » neutralise
#: sur son empan. Elles visent le MAXIMUM AGRÉGÉ, pas la capacité d'un bâtiment.
_REGLES_CAPACITE = (
    ('MAX_POSABLE', r"maximum\s+posables?|max(?:imum)?\s+posables?",
     'maximum posable'),
    ('MAX_AGREGE',
     r"(?:capacit[ée]\s+)?(?:maximale?|maximum|max)\s+"
     r"(?:du\s+site|de\s+l['’]ensemble|globale?|totale?)"
     r"|(?:capacit[ée]|potentiel)\s+(?:maximale?|maximum)",
     'maximum agrégé du site'),
)

_REGLES_AVERTISSEMENT = (
    ('CONSIGNE_CLIENT', r"consignes?\s+clients?", 'consigne client',
     'prescription'),
    ('CLIENT', r"\bclients?\b", 'client',
     "décision d'études du {date_decision}"),
    ('CROQUIS', r"\bcroquis\b", 'croquis',
     'relevé contradictoire du {date_releve}'),
)


_SEPARATEURS_PHRASE = '.;\n'


def _phrase_autour(texte, debut, fin):
    """Étend un empan aux bornes de SA PHRASE.

    L'exception protège l'ARGUMENT, pas deux mots : « capacité maximale
    démontrée par le calcul 314, engagement 288 » est exactement la formule
    voulue, et elle place le mot « maximale » AVANT « démontrée ». Un empan
    collé au motif refuserait la phrase qu'il existe pour autoriser. La phrase
    suivante, elle, retombe sous la règle générale.
    """
    gauche = max((texte.rfind(sep, 0, debut) for sep in _SEPARATEURS_PHRASE),
                 default=-1)
    positions = [texte.find(sep, fin) for sep in _SEPARATEURS_PHRASE]
    positions = [p for p in positions if p >= 0]
    droite = min(positions) + 1 if positions else len(texte)
    return (gauche + 1, droite)


def empans_exception(texte):
    """Empans ``(début, fin)`` couverts par l'exception démontrée/engagé.

    Un empan = la PHRASE portant la construction « démontrée … engagé ».
    """
    return [_phrase_autour(texte, m.start(), m.end())
            for m in _MOTIF_EXCEPTION.finditer(texte)]


def _dans_un_empan(position, empans):
    return any(debut <= position < fin for debut, fin in empans)


def _extrait(texte, position, largeur=60):
    debut = max(0, position - largeur // 2)
    return texte[debut:debut + largeur].replace('\n', ' ').strip()


def _constat(code, niveau, champ, mot, texte, position, fin,
             suggestion=''):
    return {
        'code': code,
        'niveau': niveau,
        'champ': champ,
        'mot': mot,
        'position': position,
        'fin': fin,
        'extrait': _extrait(texte, position),
        'suggestion': suggestion,
    }


def analyser(champs, *, marque_blanche=False, bureau='',
             valeurs_interdites=(), substitutions=None):
    """Analyse une liste de champs et renvoie la liste des constats.

    ``champs`` : ``[{'champ': 'memoire.4.2', 'valeur': '…',
    'portee': 'client'|'interne'|'directeur'}]``. La portée par défaut est
    ``client`` — le défaut le plus sévère, sinon un champ mal étiqueté
    passerait au travers.

    ``valeurs_interdites`` : nombres qu'on ne communique jamais (le maximum
    agrégé du site, par exemple), cités tels quels par le constat.
    """
    substitutions = dict(substitutions or {})
    constats = []
    for entree in champs or ():
        champ = entree.get('champ') or ''
        texte = str(entree.get('valeur') or '')
        portee = entree.get('portee') or 'client'
        if not texte:
            continue
        controle = portee in PORTEES_CONTROLEES
        empans = empans_exception(texte)

        if controle:
            for code, motif, mot in _REGLES_BLOQUANTES:
                for occurrence in re.finditer(motif, texte, re.IGNORECASE):
                    constats.append(_constat(code, BLOQUANT, champ, mot,
                                             texte, occurrence.start(),
                                             occurrence.end()))
            for code, motif, mot in _REGLES_CAPACITE:
                for occurrence in re.finditer(motif, texte, re.IGNORECASE):
                    if _dans_un_empan(occurrence.start(), empans):
                        continue  # « démontrée … engagé » : argument voulu
                    constats.append(_constat(code, BLOQUANT, champ, mot,
                                             texte, occurrence.start(),
                                             occurrence.end()))
            for valeur in valeurs_interdites or ():
                motif = r'(?<![\d,.])' + _motif_nombre(valeur) + r'(?![\d,.])'
                for occurrence in re.finditer(motif, texte):
                    if _dans_un_empan(occurrence.start(), empans):
                        continue
                    constats.append(_constat(
                        'VALEUR_INTERNE', BLOQUANT, champ, str(valeur), texte,
                        occurrence.start(), occurrence.end(),
                        "valeur de base interne — ne se communique pas"))
            if marque_blanche and bureau:
                for occurrence in re.finditer(re.escape(bureau), texte,
                                              re.IGNORECASE):
                    constats.append(_constat(
                        'MARQUE_BLANCHE', BLOQUANT, champ, bureau, texte,
                        occurrence.start(), occurrence.end(),
                        "seul le soumissionnaire apparaît sur un rendu "
                        "client"))

        # Avertissements : sur TOUTES les portées — un mot maladroit dans un
        # champ interne finira tôt ou tard recopié dans une pièce remise.
        couverts = []
        for code, motif, mot, remplacement in _REGLES_AVERTISSEMENT:
            for occurrence in re.finditer(motif, texte, re.IGNORECASE):
                if _dans_un_empan(occurrence.start(), couverts):
                    continue  # déjà couvert par une règle plus spécifique
                couverts.append((occurrence.start(), occurrence.end()))
                constats.append(_constat(
                    code, AVERTISSEMENT, champ, mot, texte,
                    occurrence.start(), occurrence.end(),
                    remplacement.format(**{
                        'date_decision': substitutions.get('date_decision',
                                                           '<date>'),
                        'date_releve': substitutions.get('date_releve',
                                                         '<date>'),
                    })))
    return constats


def _motif_nombre(valeur):
    """Motif tolérant aux séparateurs de milliers pour un entier donné."""
    chiffres = re.sub(r'\D', '', str(valeur))
    if len(chiffres) <= 3:
        return re.escape(chiffres)
    morceaux = []
    reste = chiffres
    tete = len(reste) % 3 or 3
    morceaux.append(re.escape(reste[:tete]))
    reste = reste[tete:]
    while reste:
        morceaux.append(re.escape(reste[:3]))
        reste = reste[3:]
    return r"[\u202f\u00a0\u2009 .]?".join(morceaux)


def sanitiser(champs, **options):
    """Porte de sanitisation : lève si un constat BLOQUANT existe.

    Renvoie la liste des AVERTISSEMENTS quand le rendu peut sortir. Ne réécrit
    jamais le texte : la substitution canonique est PROPOSÉE, l'auteur tranche.
    """
    constats = analyser(champs, **options)
    bloquants = [c for c in constats if c['niveau'] == BLOQUANT]
    if bloquants:
        raise SanitisationBloquante(bloquants)
    return [c for c in constats if c['niveau'] == AVERTISSEMENT]


def appliquer_substitutions(texte, constats):
    """Applique les substitutions proposées — opération EXPLICITE.

    Volontairement séparée de ``sanitiser`` : une réécriture automatique d'un
    document contractuel doit être demandée, jamais subie. Les remplacements
    sont appliqués de la FIN vers le DÉBUT, sans quoi la première coupe
    décalerait toutes les positions relevées ensuite.
    """
    remplacements = sorted(
        [c for c in constats
         if c['niveau'] == AVERTISSEMENT and c['suggestion']],
        key=lambda c: c['position'], reverse=True,
    )
    resultat = texte
    for constat in remplacements:
        debut, fin = constat['position'], constat['fin']
        if fin > len(resultat):
            continue
        resultat = resultat[:debut] + constat['suggestion'] + resultat[fin:]
    return resultat
