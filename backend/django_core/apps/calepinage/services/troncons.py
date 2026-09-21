"""CALX224-226 — le MÉTRÉ et la CHUTE, tronçon par tronçon.

LE DÉFAUT CORRIGÉ
-----------------
La seule longueur mesurée aujourd'hui est une distance à VOL D'OISEAU du
module le plus éloigné vers un point de collecte saisi
(``services/cables.py``), et la descente comme la liaison vers le TGBT sont
des scalaires « qui ne se lisent sur aucun plan ». Un tronçon coudé de 40 m
est donc compté comme sa corde, et l'installateur commande trop court. Pire :
``dimensionner_cables`` ne dimensionne que DEUX liaisons (``W1`` DC, ``W2``
AC), donc une seule section par côté — un tronçon de forte intensité et un
tronçon terminal reçoivent la même.

CE QUE CE SERVICE FAIT
----------------------
Il lit les CHEMINEMENTS du document (``electrical.cheminements[]``, clé
racine optionnelle posée par CALX202) et, pour chaque entrée :

* **CALX224 — la longueur.** Somme des distances entre points consécutifs de
  la polyligne, dénivelé compris quand les DEUX extrémités d'un segment
  portent leur ``altitudeM`` ; plus la ``longueurSaisieM`` quand il y en a
  une. Chaque tronçon publie ``longueur_m`` ET ``longueur_origine``
  (``plan`` / ``saisie`` / ``mixte``) — jamais un nombre nu. C'est la
  discipline ``Longueur`` de ``services/cables.py`` ÉTENDUE au tracé : la
  dataclasse y est importée telle quelle, jamais redéfinie.
* **CALX225 — la section et la chute.** ``proposer_section``
  (``core/electrique/cables.py``) est appelée UNE FOIS PAR TRONÇON, avec le
  courant qui traverse CE tronçon, le barème de son côté et la cible de la
  NORME applicable. Le critère dimensionnant et la référence de la règle
  sortent tels quels.
* **CALX226 — le cumul, et UN seul verdict par côté.** ``chute_cumulee_pct``
  remonte la chaîne d'amont en aval (``de`` → ``vers``) ; les deux cumuls
  bout en bout (DC, AC) sont verdictés UNE FOIS chacun contre la cible et le
  maximum DÉJÀ cités par le noyau. Avec plusieurs tronçons en série, chacun
  peut tenir sa cible pendant que leur SOMME dépasse le maximum : sans ce
  verdict, personne ne le voit.

D'OÙ VIENNENT LES CHIFFRES (aucun n'est posé ici)
--------------------------------------------------
* **la longueur** — du DOCUMENT (tracé) et/ou de la SAISIE ;
* **les cibles, maximums et le plancher DC** — de la NORME applicable
  (``services/norme.py::norme_applicable`` → ``coefficients_publies``), qui
  les LIT sur le noyau et les laisse écraser par un réglage société sourcé.
  Rien n'est recopié en valeur dans ce module ;
* **les barèmes d'ampacité** — du noyau pur (``AMPACITE_H1Z2Z2K``,
  ``AMPACITE_U1000R2V_MONO``/``_TRI``), avec leurs sources ;
* **le courant** — de la conception électrique du calepinage
  (``services/electrique.py::conception_du_calepinage``, LECTURE SEULE), ou
  du rattachement par tronçon quand il existe (``contexte['courants']``).

CE QU'IL NE FAIT JAMAIS
-----------------------
Aucune longueur, aucune section, aucun seuil par défaut. ``pays = ma`` sans
norme choisie ⇒ le DIMENSIONNEMENT s'omet en le disant (D1), la LONGUEUR
reste publiée. Toute grandeur non calculable vaut ``null`` (jamais ``0``, qui
se lirait « calculé, et nul ») et porte une entrée dans ``omissions[]`` qui
NOMME le tronçon, le champ et le motif en français — règle fondateur « zéro
chiffre inventé » (D-CALX 7).

FORME PUBLIÉE
-------------
``contract_samples/calepinage_troncons.json`` (CALX203) : ``troncons[]`` (14
champs), ``totaux{dc_chute_pct, ac_chute_pct, metre_par_section[]}``,
``omissions[{troncon, champ, motif}]`` — épinglés clé pour clé par les tests.

CALX226 AJOUTE une quatrième clé racine, ``verdicts[]``, que l'échantillon
committé ne porte pas encore : un verdict par côté calculable
(``{code, libelle, cote, conforme, bloquant, valeur_pct, cible_pct,
maximum_pct, troncons[], source, detail}``). Elle est signalée à la lane qui
possède ``contract_samples/`` pour y être décrite — jamais ajoutée ici.
"""
from __future__ import annotations

import math

from .cables import ORIGINE_PLAN, ORIGINE_SAISIE, Longueur
from .zones import projeteur_local

__all__ = [
    'ORIGINE_MIXTE', 'COTE_DC', 'COTE_AC', 'COTE_TERRE',
    'troncons_du_calepinage',
]

#: Le vocabulaire d'origine PUBLIÉ est celui du DOCUMENT (CALX202,
#: ``electrical.cheminements[].origine`` : ``plan`` | ``saisie`` | ``mixte``),
#: repris tel quel par le contrat CALX203 (``longueur_origine``).
#: ``services/cables.py`` publie sa propre prose (« plan et saisie ») pour ses
#: deux liaisons forfaitaires : ses deux premiers termes sont IMPORTÉS
#: ci-dessus, seul le troisième diffère et c'est le document qui fait foi ici.
ORIGINE_MIXTE = 'mixte'

COTE_DC = 'dc'
COTE_AC = 'ac'
COTE_TERRE = 'terre'

#: Le chemin JSON de la clé racine lue — il sert à NOMMER le champ absent
#: dans les omissions, jamais à deviner quoi que ce soit.
CHAMP_CHEMINEMENTS = 'electrical.cheminements'

# Nombre de conducteurs d'un tronçon, par côté. Convention de schéma d'une
# installation BT (NF C 15-100) : une paire descendante + et − côté DC,
# P + N + PE en monophasé, 3P + N + PE en triphasé, et un conducteur unique
# pour une liaison équipotentielle de terre.
NB_CONDUCTEURS_DC = 2
NB_CONDUCTEURS_AC_MONO = 3
NB_CONDUCTEURS_AC_TRI = 5
NB_CONDUCTEURS_TERRE = 1

#: Les clés du registre de coefficients de ``services/norme.py`` dont ce
#: module a besoin, par côté. Les VALEURS ne sont jamais recopiées ici : la
#: norme les publie avec leur référence et leur source.
CLE_CIBLE = {COTE_DC: 'chute_dc_cible_pct', COTE_AC: 'chute_ac_cible_pct'}
CLE_MAXIMUM = {COTE_DC: 'chute_dc_max_pct', COTE_AC: 'chute_ac_max_pct'}
CLE_PLANCHER_DC = 'section_min_dc_mm2'
CLE_COEFF_ISC = 'coeff_isc_dimensionnement'


def _nombre(valeur):
    """``float`` ou ``None`` — un booléen n'est jamais une mesure."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


# ───────────────────────────────────────────── CALX224 : la longueur mesurée
def _point(brut):
    """``(lng, lat, altitude_m | None)`` d'un point du document, ou ``None``.

    Une altitude absente vaut ``None``, jamais ``0`` : « altitudeM absente ne
    veut pas dire au sol » (CALX202).
    """
    if not isinstance(brut, dict):
        return None
    lng = _nombre(brut.get('lng'))
    lat = _nombre(brut.get('lat'))
    if lng is None or lat is None:
        return None
    return (lng, lat, _nombre(brut.get('altitudeM')))


def _points_du_cheminement(cheminement):
    """Les points EXPLOITABLES du tracé, dans l'ordre du document."""
    bruts = (cheminement or {}).get('points')
    if not isinstance(bruts, (list, tuple)):
        return []
    retenus = []
    for brut in bruts:
        point = _point(brut)
        if point is not None:
            retenus.append(point)
    return retenus


def _longueur_polyligne(points):
    """Somme des distances entre points consécutifs (m), ou ``None``.

    Le repère plan est celui de ``services/zones.py::projeteur_local``, le
    seul projeteur local du module : deux services qui fabriqueraient deux
    repères du même site mesureraient deux longueurs du même câble.

    Le dénivelé n'entre QUE lorsque les DEUX extrémités d'un segment portent
    leur ``altitudeM`` ; sinon le segment est compté à plat et aucun dénivelé
    n'est deviné.
    """
    if len(points) < 2:
        return None
    projeter = projeteur_local((points[0][0], points[0][1]))
    total = 0.0
    for amont, aval in zip(points, points[1:]):
        x_amont, y_amont = projeter((amont[0], amont[1]))
        x_aval, y_aval = projeter((aval[0], aval[1]))
        a_plat = math.hypot(x_aval - x_amont, y_aval - y_amont)
        if amont[2] is None or aval[2] is None:
            total += a_plat
        else:
            total += math.hypot(a_plat, aval[2] - amont[2])
    return total


def _repere(cheminement, rang):
    """Le nom du tronçon tel qu'un poseur le lit : son ``id``, sinon son rang."""
    identifiant = (cheminement or {}).get('id')
    texte = str(identifiant).strip() if identifiant is not None else ''
    return texte or ('cheminement n° %d' % rang)


def _longueur_du_troncon(cheminement, rang=1):
    """``(Longueur | None, motif | None)`` — la longueur d'UN cheminement.

    Trois cas, exactement ceux de l'exemple committé de CALX202 : polyligne
    seule (``plan``), longueur saisie seule (``saisie``), et les deux
    (``mixte`` — un tracé plus une descente que le plan ne porte pas).
    """
    cheminement = cheminement or {}
    nom = _repere(cheminement, rang)
    tracee = _longueur_polyligne(_points_du_cheminement(cheminement))
    saisie = _nombre(cheminement.get('longueurSaisieM'))

    if saisie is not None and saisie < 0:
        return (None,
                "le tronçon « %s » porte une longueur saisie négative "
                "(« longueurSaisieM » = %s) : une longueur de câble ne peut "
                "pas être négative — corrigez la saisie, elle n'est pas "
                "réinterprétée." % (nom, saisie))

    composantes = []
    if tracee is not None:
        composantes.append(('tracé relevé sur le plan', tracee, ORIGINE_PLAN))
    if saisie is not None:
        composantes.append(('longueur saisie', saisie, ORIGINE_SAISIE))

    if not composantes:
        return (None,
                "le tronçon « %s » n'a ni tracé exploitable (« points », deux "
                "points minimum) ni longueur saisie (« longueurSaisieM ») : "
                "tracez-le dans l'atelier, ou saisissez sa longueur en "
                "mètres — elle ne peut pas être devinée, et aucune longueur "
                "par défaut n'est substituée." % nom)

    if tracee is not None and saisie is not None:
        origine = ORIGINE_MIXTE
        detail = ("tracé relevé sur le plan (%.2f m) plus une longueur saisie "
                  "(%.2f m)" % (tracee, saisie))
    elif tracee is not None:
        origine = ORIGINE_PLAN
        detail = 'tracé relevé sur le plan, point à point'
    else:
        origine = ORIGINE_SAISIE
        detail = "longueur saisie : ce passage n'est pas tracé sur le plan"

    return (Longueur(
        valeur_m=sum(valeur for _poste, valeur, _origine in composantes),
        origine=origine, detail=detail,
        composantes=tuple(composantes)), None)


def _troncon_publie(cheminement, longueur, rang):
    """Les champs du tronçon que la MESURE seule permet de remplir."""
    return {
        'id': _repere(cheminement, rang),
        'cote': (cheminement or {}).get('cote'),
        'de': (cheminement or {}).get('de'),
        'vers': (cheminement or {}).get('vers'),
        'longueur_m': (None if longueur is None
                       else round(longueur.valeur_m, 2)),
        'longueur_origine': None if longueur is None else longueur.origine,
    }


def _omission(troncon, champ, motif):
    """Une omission NOMMÉE : le tronçon, le champ, et pourquoi en français."""
    return {'troncon': troncon, 'champ': champ, 'motif': motif}


def _cheminements(document):
    """``electrical.cheminements[]`` du document, ou une liste vide."""
    electrique = (document or {}).get('electrical')
    if not isinstance(electrique, dict):
        return []
    cheminements = electrique.get('cheminements')
    if not isinstance(cheminements, (list, tuple)):
        return []
    return [c for c in cheminements if isinstance(c, dict)]


def _omission_aucun_cheminement():
    """L'état vide : PAS de chute nulle, PAS de chute calculable."""
    return _omission(
        None, CHAMP_CHEMINEMENTS,
        "aucun cheminement n'est tracé sur ce plan : il n'y a pas de tronçon "
        "à mesurer. Tracez les liaisons dans l'atelier, ou saisissez leurs "
        "longueurs — un calepinage sans tracé n'a pas 0 % de chute, il n'a "
        "PAS de chute calculable.")


# ──────────────────────────────────── CALX225 : la section et la chute par tronçon
def _coefficient(norme, cle):
    """``(valeur | None, référence)`` d'un coefficient publié par la norme.

    La valeur vient du registre de ``services/norme.py`` — noyau, ou réglage
    société sourcé qui l'écrase. Absente, elle n'est JAMAIS remplacée.
    """
    entree = ((norme or {}).get('coefficients') or {}).get(cle)
    if not isinstance(entree, dict):
        return (None, '')
    return (_nombre(entree.get('valeur')), str(entree.get('reference') or ''))


def _nb_conducteurs(cote, phases=None):
    """Le nombre de conducteurs du tronçon, ou ``None`` si le côté est muet."""
    if cote == COTE_DC:
        return NB_CONDUCTEURS_DC
    if cote == COTE_TERRE:
        return NB_CONDUCTEURS_TERRE
    if cote == COTE_AC:
        if phases == 3:
            return NB_CONDUCTEURS_AC_TRI
        if phases == 1:
            return NB_CONDUCTEURS_AC_MONO
    return None


def _dimensionnement_vide(nb_conducteurs=None):
    """Les huit champs de dimensionnement, tous ``null`` — jamais ``0``."""
    return {
        'nb_conducteurs': nb_conducteurs, 'section_mm2': None, 'ib_a': None,
        'iz_a': None, 'chute_pct': None, 'chute_cumulee_pct': None,
        'critere_dimensionnant': None, 'regle_source': None,
    }


def _courant_du_troncon(troncon, contexte):
    """``(spec | None, motif | None)`` — le courant qui traverse CE tronçon.

    Deux sources, dans cet ordre :

    1. ``contexte['courants'][<id>]`` — le rattachement des chaînes/branches
       à CE tronçon. C'est le crochet de CALX228 : lui seul sait qu'un
       tronçon amont porte l'Isc cumulé de trois chaînes quand son tronçon
       terminal n'en porte qu'une ;
    2. ``contexte['dc']`` / ``contexte['ac']`` — le courant du CÔTÉ, publié
       par la conception électrique du calepinage (lecture seule).

    Aucune des deux ⇒ ``None`` et un motif qui NOMME le champ absent : le
    dimensionnement est OMIS, jamais estimé.
    """
    contexte = contexte or {}
    nom = troncon.get('id')
    spec = (contexte.get('courants') or {}).get(nom)
    if isinstance(spec, dict):
        return (spec, None)
    cote = troncon.get('cote')
    if cote in (COTE_DC, COTE_AC):
        spec = contexte.get(cote)
        if isinstance(spec, dict):
            return (spec, None)
    manque = contexte.get('manque') or (
        "la conception électrique de ce calepinage ne publie aucun courant "
        "pour le côté « %s »" % (cote or 'inconnu'))
    return (None,
            "le courant qui traverse le tronçon « %s » n'est publié ni par "
            "le rattachement des chaînes (« courants.%s.ib_a ») ni par la "
            "conception électrique du calepinage (%s) : section et chute de "
            "tension OMISES." % (nom, nom, manque))


def _regle_source(cote, triphase, reference_chute, reference_plancher):
    """La RÉFÉRENCE de la règle appliquée — jamais un nombre recopié."""
    if cote == COTE_DC:
        morceaux = [
            "EN 50618 — intensité admissible du câble solaire H1Z2Z2-K",
            "IEC 62548 §7.3 — courant de dimensionnement des câbles DC",
            "NF C 15-100 §433.1 — Ib ≤ In ≤ Iz",
        ]
    else:
        morceaux = [
            "IEC 60364-5-52 tableau B.52.4 méthode C — ampacité U-1000 R2V "
            "(%s)" % ('triphasé' if triphase else 'monophasé'),
            "NF C 15-100 §433.1 — Ib ≤ In ≤ Iz",
        ]
    for reference in (reference_chute, reference_plancher):
        if reference:
            morceaux.append(reference)
    return ' ; '.join(morceaux)


def _motif_norme_absente(norme):
    """Le motif D1, tel que ``norme_applicable`` le rédige — jamais un barème
    supposé à la place."""
    motif = (norme or {}).get('motif') or ''
    return ("section et chute de tension OMISES : %s "
            "(services/norme.py::norme_applicable)."
            % (motif or "aucune norme électrique n'est applicable"))


def _dimensionner_troncon(troncon, contexte):
    """``(champs, omission | None)`` — la section et la chute de CE tronçon.

    Une seule omission par CAUSE RACINE : quand la longueur manque, c'est
    elle qui est déjà nommée (CALX224) et rien n'est répété ici.
    """
    contexte = contexte or {}
    nom = troncon.get('id')
    cote = troncon.get('cote')
    spec, motif_courant = _courant_du_troncon(troncon, contexte)
    phases = int(_nombre((spec or {}).get('phases')) or 0) or None
    champs = _dimensionnement_vide(_nb_conducteurs(cote, phases))

    if troncon.get('longueur_m') is None:
        return (champs, None)

    norme = contexte.get('norme') or {}
    if not norme.get('applicable', False):
        return (champs, _omission(nom, 'section_mm2',
                                  _motif_norme_absente(norme)))

    if cote == COTE_TERRE:
        return (champs, _omission(
            nom, 'section_mm2',
            "la section du conducteur de terre ne se dimensionne pas sur la "
            "chute de tension : elle relève de la check-list de terre "
            "(services/terre.py) et de la norme applicable. La longueur du "
            "tronçon, elle, reste publiée et entre au métré."))

    if cote not in (COTE_DC, COTE_AC):
        return (champs, _omission(
            nom, 'cote',
            "le tronçon « %s » ne déclare pas son côté (« cote » attendu : "
            "dc, ac ou terre) : sans lui, ni barème d'ampacité ni cible de "
            "chute ne sont applicables." % nom))

    if spec is None:
        return (champs, _omission(nom, 'ib_a', motif_courant))

    courant = _nombre(spec.get('ib_a'))
    tension = _nombre(spec.get('tension_v'))
    if courant is None or courant <= 0:
        return (champs, _omission(
            nom, 'ib_a',
            "le courant d'emploi du tronçon « %s » n'est pas publié "
            "(« ib_a ») : section et chute de tension OMISES." % nom))
    if tension is None or tension <= 0:
        return (champs, _omission(
            nom, 'chute_pct',
            "la tension de service du tronçon « %s » n'est pas publiée "
            "(« tension_v ») : une chute de tension en pourcentage n'a pas "
            "de sens sans elle." % nom))

    from core.electrique import cables as noyau

    triphase = phases == 3
    if cote == COTE_DC:
        bareme = noyau.AMPACITE_H1Z2Z2K
        # Continu : le facteur 2 porte le trajet ALLER-RETOUR de la formule
        # u = 2 × rho × L × I / S (core/electrique/cables.py).
        coefficient = 2.0
        plancher, reference_plancher = _coefficient(norme, CLE_PLANCHER_DC)
    else:
        if phases not in (1, 3):
            return (champs, _omission(
                nom, 'nb_conducteurs',
                "le nombre de phases du tronçon AC « %s » n'est pas publié "
                "(« phases ») : ni le barème d'ampacité ni le coefficient de "
                "la formule de chute ne sont déterminés." % nom))
        bareme = (noyau.AMPACITE_U1000R2V_TRI if triphase
                  else noyau.AMPACITE_U1000R2V_MONO)
        # Triphasé : les trois phases se compensent, d'où le facteur √3 de
        # u = √3 × rho × L × I / S (core/electrique/cables.py).
        coefficient = math.sqrt(3.0) if triphase else 2.0
        plancher, reference_plancher = (None, '')

    cible, reference_chute = _coefficient(norme, CLE_CIBLE[cote])
    if cible is None:
        return (champs, _omission(
            nom, 'section_mm2',
            "la cible de chute de tension « %s » n'est pas publiée par la "
            "norme applicable : aucune section n'est proposée sans elle."
            % CLE_CIBLE[cote]))

    proposee = noyau.proposer_section(
        courant_ib_a=courant, longueur_m=troncon['longueur_m'],
        tension_v=tension, cible_pct=cible, bareme=bareme,
        coefficient=coefficient,
        calibre_in_a=_nombre(spec.get('calibre_in_a')),
        courant_service_a=_nombre(spec.get('i_service_a')),
        section_min_mm2=plancher)

    champs.update({
        'section_mm2': proposee.section_mm2,
        'ib_a': round(courant, 2),
        'iz_a': round(proposee.iz_a, 2),
        'chute_pct': round(proposee.chute_pct, 3),
        'critere_dimensionnant': proposee.critere,
        'regle_source': _regle_source(cote, triphase, reference_chute,
                                      reference_plancher),
    })
    return (champs, None)


# ─────────────── CALX226 : la chute cumulée bout en bout, verdictée UNE fois
#: Le code de chaque verdict, par côté — un test lit un verdict par son CODE,
#: jamais par sa position dans une liste.
CODE_VERDICT = {COTE_DC: 'chute_cumulee_dc', COTE_AC: 'chute_cumulee_ac'}
LIBELLE_COTE = {COTE_DC: 'Chute de tension cumulée DC (champ → onduleur)',
                COTE_AC: 'Chute de tension cumulée AC (onduleur → tableau)'}


def _cumul_du_troncon(troncon, arrivants, memo, en_cours):
    """La chute cumulée DEPUIS LA SOURCE au bout de CE tronçon, ou ``None``.

    On remonte la chaîne d'amont en aval : le cumul d'un tronçon est sa
    propre chute PLUS le pire cumul des tronçons qui arrivent à son extrémité
    amont — quand deux branches se rejoignent, c'est le chemin le plus
    défavorable qui décide, jamais une moyenne.

    Une chute manquante en amont, ou une boucle dans le tracé, rend ``None``
    (jamais un cumul partiel : il se lirait comme un budget de chute encore
    disponible).
    """
    nom = troncon['id']
    if nom in memo:
        return memo[nom]
    chute = troncon.get('chute_pct')
    if chute is None:
        memo[nom] = None
        return None
    if nom in en_cours:
        return None
    en_cours.add(nom)
    amont = 0.0
    cle = (troncon.get('cote'), troncon.get('de'))
    for precedent in arrivants.get(cle) or ():
        if precedent['id'] == nom:
            continue
        valeur = _cumul_du_troncon(precedent, arrivants, memo, en_cours)
        if valeur is None:
            en_cours.discard(nom)
            memo[nom] = None
            return None
        amont = max(amont, valeur)
    en_cours.discard(nom)
    memo[nom] = amont + chute
    return memo[nom]


def _cumuler_les_chutes(troncons):
    """Pose ``chute_cumulee_pct`` sur chaque tronçon ; rend le pire par côté.

    Le « pire » est la chute cumulée BOUT EN BOUT : celle du tronçon le plus
    aval de la chaîne la plus défavorable. C'est elle, et elle seule, que le
    verdict de CALX226 compare aux bornes de la norme.
    """
    arrivants = {}
    for troncon in troncons:
        cote = troncon.get('cote')
        if cote in (COTE_DC, COTE_AC):
            arrivants.setdefault((cote, troncon.get('vers')),
                                 []).append(troncon)
    memo = {}
    pires = {}
    for troncon in troncons:
        cote = troncon.get('cote')
        if cote not in (COTE_DC, COTE_AC):
            continue
        cumul = _cumul_du_troncon(troncon, arrivants, memo, set())
        troncon['chute_cumulee_pct'] = (None if cumul is None
                                        else round(cumul, 3))
        if cumul is not None and cumul > pires.get(cote, -1.0):
            pires[cote] = cumul
    return pires


def _verdict_de_chute(cote, cumul, contributeurs, norme):
    """UN verdict pour CE côté — jamais un verdict par tronçon.

    Les bornes sont celles que le noyau porte déjà, LUES par la norme
    applicable avec leur référence (UTE C 15-712-1 pour les cibles ; la
    référence du maximum AC rappelle que NF C 15-100 §525 plafonne
    l'installation entière). Aucune borne neuve n'est créée ici.
    """
    from core.electrique.types import fr

    cible, reference_cible = _coefficient(norme, CLE_CIBLE[cote])
    maximum, reference_max = _coefficient(norme, CLE_MAXIMUM[cote])
    verdict = {
        'code': CODE_VERDICT[cote], 'libelle': LIBELLE_COTE[cote],
        'cote': cote, 'conforme': None, 'bloquant': False,
        'valeur_pct': round(cumul, 3), 'cible_pct': cible,
        'maximum_pct': maximum, 'troncons': list(contributeurs),
        'source': None, 'detail': '',
    }
    noms = ', '.join('« %s »' % nom for nom in contributeurs)
    if cible is None or maximum is None:
        verdict['detail'] = (
            "chute cumulée de %s %% mesurée sur %s, mais la cible ou le "
            "maximum ne sont pas publiés par la norme applicable : le "
            "contrôle n'est PAS vérifiable, et aucune borne n'est supposée à "
            "leur place." % (fr(cumul, 2), noms))
        return verdict

    verdict['source'] = 'norme'
    if cumul > maximum + 1e-9:
        verdict['conforme'] = False
        verdict['bloquant'] = True
        verdict['detail'] = (
            "chute cumulée de %s %% bout en bout, au-dessus du maximum "
            "admissible de %s %% (%s). Pris isolément, un tronçon peut tenir "
            "sa cible ; c'est leur SOMME qui déborde. Tronçons "
            "contributeurs : %s — raccourcir la liaison, rapprocher "
            "l'organe, ou monter en section."
            % (fr(cumul, 2), fr(maximum, 1), reference_max, noms))
    elif cumul > cible + 1e-9:
        verdict['conforme'] = False
        verdict['detail'] = (
            "chute cumulée de %s %% bout en bout, au-dessus de la cible de "
            "%s %% (%s) mais sous le maximum de %s %%. Tronçons "
            "contributeurs : %s."
            % (fr(cumul, 2), fr(cible, 1), reference_cible, fr(maximum, 1),
               noms))
    else:
        verdict['conforme'] = True
        verdict['detail'] = (
            "chute cumulée de %s %% bout en bout, sous la cible de %s %% "
            "(%s). Tronçons contributeurs : %s."
            % (fr(cumul, 2), fr(cible, 1), reference_cible, noms))
    return verdict


def _verdicts_des_cumuls(troncons, pires, norme):
    """Un verdict par côté CALCULABLE — aucun verdict sur un cumul absent.

    Un côté dont la chute n'est pas calculable n'a pas de verdict : un vert
    prononcé sur une absence serait le pire des faux verts. Les omissions
    par tronçon en disent déjà la cause.
    """
    verdicts = []
    for cote in (COTE_DC, COTE_AC):
        if cote not in pires:
            continue
        contributeurs = [t['id'] for t in troncons
                         if t.get('cote') == cote
                         and t.get('chute_pct') is not None]
        verdicts.append(_verdict_de_chute(cote, pires[cote], contributeurs,
                                          norme))
    return verdicts


def _metre_par_section(troncons):
    """Le métré à commander : une ligne par section, la section OMISE comprise.

    Fondre la ligne ``section_mm2: null`` dans une autre ferait DISPARAÎTRE
    une longueur réelle du bon de commande.
    """
    cumul = {}
    for troncon in troncons:
        longueur = troncon.get('longueur_m')
        if longueur is None:
            continue
        section = troncon.get('section_mm2')
        cumul[section] = cumul.get(section, 0.0) + longueur
    lignes = [{'section_mm2': section, 'longueur_m': round(valeur, 2)}
              for section, valeur in cumul.items()]
    lignes.sort(key=lambda ligne: (ligne['section_mm2'] is None,
                                   ligne['section_mm2'] or 0.0))
    return lignes


def _troncons_du_document(document, contexte=None):
    """Le NOYAU de calcul : ``{troncons, totaux, omissions}``.

    Il ne connaît ni modèle ni requête — seulement ``layout['electrical']``
    et un ``contexte`` (norme, courants du calepinage) PASSÉS en argument.
    C'est ce qui le rend testable sans base de données.
    """
    cheminements = _cheminements(document)
    if not cheminements:
        return {'troncons': [],
                'totaux': {'dc_chute_pct': None, 'ac_chute_pct': None,
                           'metre_par_section': []},
                'omissions': [_omission_aucun_cheminement()],
                'verdicts': []}

    troncons = []
    omissions = []
    for rang, cheminement in enumerate(cheminements, start=1):
        longueur, motif = _longueur_du_troncon(cheminement, rang)
        publie = _troncon_publie(cheminement, longueur, rang)
        if motif:
            omissions.append(_omission(publie['id'], 'longueur_m', motif))
        champs, omission = _dimensionner_troncon(publie, contexte)
        publie.update(champs)
        if omission is not None:
            omissions.append(omission)
        troncons.append(publie)

    pires = _cumuler_les_chutes(troncons)
    return {
        'troncons': troncons,
        'totaux': {
            'dc_chute_pct': (None if COTE_DC not in pires
                             else round(pires[COTE_DC], 3)),
            'ac_chute_pct': (None if COTE_AC not in pires
                             else round(pires[COTE_AC], 3)),
            'metre_par_section': _metre_par_section(troncons),
        },
        'omissions': omissions,
        'verdicts': _verdicts_des_cumuls(troncons, pires,
                                         (contexte or {}).get('norme')),
    }


def _contexte_electrique(conception, norme):
    """Le contexte de dimensionnement LU sur la conception, jamais inventé.

    Côté DC le courant d'échauffement est celui du noyau (le coefficient
    d'Isc vient de la norme, pas d'ici) et le courant de service est l'Imp
    réellement transporté ; côté AC ce sont le courant d'emploi et le calibre
    que ``concevoir_protections`` a retenus. Conception muette ⇒ aucun
    courant, et ``manque`` dit POURQUOI.
    """
    from core.electrique.protections import concevoir_protections

    from .chaines import evaluer_onduleurs

    contexte = {'norme': norme, 'dc': None, 'ac': None, 'courants': {}}
    if conception is None or conception.entree is None \
            or conception.resultat is None or not conception.chaines:
        contexte['manque'] = (
            "aucune chaîne n'est calculée pour ce calepinage : il n'y a pas "
            "de courant à faire passer dans un tronçon")
        return contexte
    if conception.fiche_incomplete:
        contexte['manque'] = (
            "fiche produit incomplète — %s"
            % ', '.join(conception.manquantes))
        return contexte

    entree = conception.entree
    protections = concevoir_protections(entree, conception.resultat,
                                        evaluer_onduleurs(conception))
    module = entree.module
    coefficient_isc, _reference = _coefficient(norme, CLE_COEFF_ISC)
    if coefficient_isc is not None:
        contexte[COTE_DC] = {
            'ib_a': module.isc_a * coefficient_isc,
            'i_service_a': module.imp_a or module.isc_a,
            'tension_v': min(c.vmp_stc_v for c in conception.chaines),
            'calibre_in_a': protections.calibre_fusible_a,
        }
    courant_ac = _nombre(protections.courant_ac_ib_a)
    if courant_ac and courant_ac > 0:
        contexte[COTE_AC] = {
            'ib_a': courant_ac,
            'tension_v': entree.tension_reseau_v,
            'phases': int(entree.phases or 1),
            'calibre_in_a': protections.calibre_ac_a,
        }
    return contexte


def troncons_du_calepinage(calepinage):
    """CALX224-226 — le métré et la chute, tronçon par tronçon, de CE
    calepinage.

    Enveloppe MINCE : elle lit le document enregistré
    (``Calepinage.roof_layout``), la norme applicable et la conception
    électrique (toutes trois en LECTURE SEULE), puis passe la main au noyau
    de calcul. Aucune écriture, aucun effet de bord.
    """
    from .electrique import conception_du_calepinage, parametres_societe
    from .norme import norme_applicable

    norme = norme_applicable(parametres_societe(calepinage))
    conception, _materiel, _donnees, document = conception_du_calepinage(
        calepinage)
    return _troncons_du_document(document,
                                 _contexte_electrique(conception, norme))
