# -*- coding: utf-8 -*-
"""BALAYAGE ADAPTATIF des tailles résidentielles — décision fondateur du
23/10/2026 (lead 1635 : « residential clients above 100 kDH must be resolved
and the sizing calculator should find the right sizing for those clients »).

Module PUR : des nombres et des listes, aucune base, aucun import de
``apps.ventes.dimensionnement`` (qui l'importe, lui — le cycle est interdit
par construction). Les deux « choisisseurs » (recommandation sans / avec
batterie) et le PLAFOND DUR (``dimensionnement.MAX_PANNEAUX_BALAYAGE``, dont
ce module-là reste propriétaire) sont REÇUS en argument, jamais importés.

CE QUE LE FONDATEUR A DÉCIDÉ, EN TROIS POINTS :

1. **120 panneaux n'est plus un plafond, c'est un SEUIL** —
   :data:`SEUIL_PANNEAUX_RESIDENTIEL`. Au-dessus, chaque taille porte
   ``hors_residentiel=True`` et :data:`MESSAGE_HORS_RESIDENTIEL`, la
   motivation de la taille retenue répète le signal
   (:data:`MOTIVATION_HORS_RESIDENTIEL`) — mais elle est RECOMMANDÉE
   (« recommend + flag », jamais un refus).
2. **Le plafond dur monte à 2 000 panneaux** (``MAX_PANNEAUX_BALAYAGE``). Ce
   n'est pas une règle métier : c'est le garde-fou du zéro de trop (1 200 000
   au lieu de 1 200). Lui seul tronque encore le balayage et retire la
   recommandation (QJR411, inchangé — :func:`message_plafond_atteint`).
3. **Le balayage est ADAPTATIF.** Jusqu'à :data:`SEUIL_BALAYAGE_DENSE` panneaux
   il évalue CHAQUE taille — byte-identique à l'historique pour tout le
   résidentiel courant (39 tailles pour 6 000 MAD/mois). Au-delà, une GRILLE
   GROSSIÈRE d'environ :data:`POINTS_GRILLE_GROSSIERE` tailles (pas =
   ⌈fin / 40⌉) décide d'abord, puis les tailles voisines des deux
   recommandations (sans / avec batterie) sont évaluées une à une
   (:func:`tailles_raffinees`) : la taille retenue est exacte AU PANNEAU, et le
   volume reste ~40 + 4 × pas évaluations quelle que soit la facture.

MESURÉ SUR PROD LE 23/10/2026 (f0dd822db) : 0,05-0,10 s par taille ; 4,1 s
pour 39 tailles (6 000 MAD/mois) ; 20 000 et 100 000 MAD/mois frappaient le
plafond de 120 et ressortaient SANS recommandation. Le catalogue compose
jusqu'à 700 panneaux (Huawei 100 / 150 kW) : le plafond n'était pas une
limite physique. Écarté : une table pré-calculée par tranche de facture —
fausse dès que la ville, le barème, le catalogue, la phase ou l'occupation
diffèrent, et 6 000 comme 6 999 MAD y recevraient la même taille.

Épinglé par ``apps/ventes/tests/test_qjr_cout_balayage.py`` (fonctions pures,
volume borné, exactitude au panneau, dense sans clé nouvelle) et
``test_qjr411_plafond_message_honnete.py`` (seuil / plafond, signal, profil à
140 panneaux dimensionné sur le catalogue seedé).
"""
import math

#: SEUIL « hors résidentiel » — l'ancien plafond dur (≈ 85 kWc en 710 Wc),
#: devenu un SIGNAL : au-dessus, taille signalée ET recommandable.
SEUIL_PANNEAUX_RESIDENTIEL = 120

#: Jusqu'à ce nombre de panneaux candidats, balayage DENSE (taille par taille,
#: byte-identique à l'historique) ; au-delà, grille grossière + raffinement.
SEUIL_BALAYAGE_DENSE = 60

#: Nombre de points visé par la grille grossière (pas = ⌈fin / 40⌉).
POINTS_GRILLE_GROSSIERE = 40

#: Avertissement porté par chaque taille au-dessus du seuil résidentiel.
MESSAGE_HORS_RESIDENTIEL = (
    'Profil au-delà du dimensionnement résidentiel (> %d panneaux) : étude '
    'sur mesure conseillée.' % SEUIL_PANNEAUX_RESIDENTIEL)

#: Suffixe de motivation quand la taille RETENUE est au-dessus du seuil.
MOTIVATION_HORS_RESIDENTIEL = (
    'profil au-delà du dimensionnement résidentiel (> %d panneaux) : taille '
    'recommandée sur le catalogue, étude sur mesure conseillée (décision '
    'fondateur du 23/10/2026)' % SEUIL_PANNEAUX_RESIDENTIEL)


def message_plafond_atteint(plafond):
    """QJR411 (DR4, 31/08/2026) — le message d'un balayage TRONQUÉ par le
    plafond dur : il nomme l'étude sur mesure, jamais une facture douteuse."""
    return ('Balayage plafonné à %d panneaux : profil au-delà du '
            'dimensionnement résidentiel — étude sur mesure.' % int(plafond))


def pas_balayage(fin):
    """Le PAS de la grille grossière pour une borne haute de ``fin`` panneaux.

    ``1`` jusqu'à :data:`SEUIL_BALAYAGE_DENSE` (balayage dense, historique),
    sinon ``⌈fin / POINTS_GRILLE_GROSSIERE⌉`` — environ quarante points quelle
    que soit la taille du profil.
    """
    fin = int(fin or 0)
    if fin <= SEUIL_BALAYAGE_DENSE:
        return 1
    return max(1, int(math.ceil(fin / float(POINTS_GRILLE_GROSSIERE))))


def tailles_grille(debut, fin, pas=1):
    """Les tailles de ``debut`` à ``fin`` par ``pas`` — ``fin`` TOUJOURS incluse
    (la parité + 1 est la borne qui PROUVE le retournement du payback)."""
    debut, fin, pas = int(debut), int(fin), max(1, int(pas or 1))
    if fin < debut:
        return []
    tailles = list(range(debut, fin + 1, pas))
    if tailles[-1] != fin:
        tailles.append(fin)
    return tailles


def tailles_raffinees(tailles, centres, pas, debut, fin):
    """La grille PLUS chaque taille à moins d'un pas des ``centres`` — les deux
    recommandations grossières (sans / avec batterie). Rend une liste triée,
    sans doublon, bornée à ``[debut, fin]``."""
    retenues = {int(t) for t in (tailles or ())}
    debut, fin, pas = int(debut), int(fin), max(1, int(pas or 1))
    for centre in (centres or ()):
        bas = max(debut, int(centre) - pas + 1)
        haut = min(fin, int(centre) + pas - 1)
        retenues.update(range(bas, haut + 1))
    return sorted(retenues)


def tailles_max_evaluees(plafond):
    """Le PIRE CAS du balayage adaptatif, en tailles évaluées : la grille sur
    tout le plafond dur plus les deux voisinages de raffinement. Chiffre LU par
    la note de résidu QJR112 (``test_qjr_cout_balayage``)."""
    pas = pas_balayage(plafond)
    grille = len(tailles_grille(1, plafond, pas))
    return grille + 2 * (2 * pas - 2)


def plafond_montee_ve(fin, plafond):
    """Jusqu'où le champ peut MONTER pour remplir une banque VE nocturne
    (QJR612) : le seuil résidentiel ou le double de la borne, jamais plus que
    le plafond dur — identique à l'historique (120) sous le seuil dense."""
    return min(int(plafond), max(SEUIL_PANNEAUX_RESIDENTIEL, 2 * int(fin)))


def motivation_hors_residentiel(ligne, motivation):
    """La motivation d'une taille au-dessus du seuil résidentiel porte le
    signal « étude sur mesure conseillée » ; sous le seuil, texte inchangé à
    l'octet."""
    if not (ligne or {}).get('hors_residentiel'):
        return motivation
    return '%s — %s' % (motivation, MOTIVATION_HORS_RESIDENTIEL)


def construire_tableau_tailles(evaluer, tailles, plafond_atteint, pas=1,
                               plafond=None):
    """Les lignes du balayage pour EXACTEMENT ces tailles, dans cet ordre.

    ``evaluer(panneaux)`` rend la ligne (ou ``None``) ; elle est mémoïsée par
    l'appelant, donc une taille déjà vue ne coûte rien. Chaque ligne au-dessus
    de :data:`SEUIL_PANNEAUX_RESIDENTIEL` est SIGNALÉE (clé structurée
    ``hors_residentiel`` + avertissement, jamais un texte à reconnaître) ;
    ``pas > 1`` est noté sur chaque ligne ; un balayage TRONQUÉ par le plafond
    dur (``plafond_atteint``, ``plafond`` = sa valeur) garde le marquage QJR411
    (``plafond_panneaux_atteint``, message en tête) que
    ``dimensionnement.choisir_recommandation`` lit pour ne plus étiqueter ce
    résultat « recommandé ».
    """
    tableau = []
    for panneaux in tailles:
        ligne = evaluer(panneaux)
        if ligne is None:
            continue
        if panneaux > SEUIL_PANNEAUX_RESIDENTIEL:
            if MESSAGE_HORS_RESIDENTIEL not in ligne['avertissements']:
                ligne['avertissements'].append(MESSAGE_HORS_RESIDENTIEL)
            ligne['hors_residentiel'] = True
        if pas > 1:
            ligne['pas_balayage'] = pas
        if plafond_atteint:
            message = message_plafond_atteint(plafond or 0)
            if message not in ligne['avertissements']:
                ligne['avertissements'].insert(0, message)
            ligne['plafond_panneaux_atteint'] = True
        tableau.append(ligne)
    return tableau


def construire_tableau(evaluer, debut, fin, plafond_atteint, pas=1,
                       plafond=None):
    """Les lignes du balayage, de ``debut`` à ``fin`` panneaux inclus (par
    ``pas``, ``fin`` toujours incluse)."""
    return construire_tableau_tailles(
        evaluer, tailles_grille(debut, fin, pas), plafond_atteint, pas, plafond)


def tableau_adaptatif(evaluer, debut, fin, plafond_atteint, choisirs,
                      plafond=None):
    """LE TABLEAU : dense si ``pas_balayage(fin) == 1`` (historique) ; sinon la
    grille grossière, puis le RAFFINEMENT autour des deux recommandations
    grossières pour que la taille retenue soit exacte au panneau.

    ``choisirs`` = ``(choisir_recommandation, choisir_recommandation_avec)``
    — chacun rend ``(ligne | None, motivation)`` ; reçus en argument, jamais
    importés (anti-cycle). ``plafond`` = le plafond dur, pour le message QJR411
    d'un balayage tronqué. ``evaluer`` est mémoïsé par l'appelant : les tailles
    de la grille ne sont jamais recalculées au second passage.
    """
    pas = pas_balayage(fin)
    tableau = construire_tableau(evaluer, debut, fin, plafond_atteint, pas,
                                 plafond)
    if pas <= 1 or not tableau:
        return tableau
    centres = [int(retenu['panneaux']) for retenu, _motivation
               in (choisir(tableau) for choisir in choisirs)
               if retenu is not None]
    if not centres:
        return tableau
    tailles = tailles_raffinees(
        [ligne['panneaux'] for ligne in tableau], centres, pas, debut, fin)
    return construire_tableau_tailles(evaluer, tailles, plafond_atteint, pas,
                                      plafond)


def monter_champ_ve(evaluer, tableau, debut, fin, plafond_atteint, choisirs,
                    plafond):
    """QJR612 — « add more panels so battery is always charged » : la borne
    haute (parité + 1, falaise) ignore le plancher VE nocturne, si bien
    qu'aucune taille balayée ne remplissait la banque relevée. Le CHAMP MONTE
    donc, pas par pas au-delà de ``fin``, jusqu'à la première taille où une
    banque ≥ plancher se remplit chaque jour (+ un panneau de marge, comme la
    parité), bornée par :func:`plafond_montee_ve`. Rend le tableau étendu, ou
    ``tableau`` tel quel si aucune taille n'y parvient."""
    pas, borne = pas_balayage(fin), plafond_montee_ve(fin, plafond)
    taille = int(fin)
    while taille < borne:
        taille = min(taille + pas, borne)
        ligne = evaluer(taille)
        if ligne is not None and ligne.get('balayage_stockage'):
            return tableau_adaptatif(
                evaluer, debut, min(taille + 1, int(plafond)),
                plafond_atteint, choisirs, plafond)
    return tableau
