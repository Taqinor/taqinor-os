"""CALX190 — LE BLOC « autoconsommation » et le plafond d'injection réel.

CE QUE CE MODULE EST
----------------------
Un PRODUCTEUR DE BLOC POST-CHAÎNE, comme ``etapes/batterie.py`` : le croisement
production ÷ consommation n'est pas une perte de production, c'est une lecture
du point de livraison. ``autoconsommation`` ne figure donc pas dans
``chaine_pertes.ORDRE_ETAPES`` ; ``services/simulation.py`` (CALX5) appelle ce
module APRÈS la chaîne et APRÈS la batterie, et publie ce qu'il rend sous
``resultat['autoconsommation']``.

UN SEUL MOTEUR DE CROISEMENT
------------------------------
``services/autoconsommation.py::bilan_autoconsommation`` (CAL150/CAL151) porte
déjà la règle fondateur COUV-AUTO — la couverture est la part AUTOCONSOMMÉE de
la consommation, JAMAIS production ÷ consommation — et applique le plafond
d'injection heure par heure. Il est appelé TEL QUEL ; aucune seconde
arithmétique n'est écrite ici.

Parité citée : PVsyst — l'autoconsommation exige un profil de charge « car les
échanges d'énergie sont instantanés », et publie E_Avail / E_User / E_Solar /
SolFrac :
https://www.pvsyst.com/help/project-design/grid-connected-system-definition/self-consumption.html

LA PRODUCTION QUE VOIT LE POINT DE LIVRAISON
----------------------------------------------
Quand la batterie a été dispatchée (CALX188), ce n'est plus la production du
champ qui se présente au compteur : c'est ce qui en reste après stockage, plus
ce que la batterie restitue. Cette production EFFECTIVE se relit sur les
colonnes que CALX188 a posées sur la série, sans redispatcher quoi que ce
soit : ``production_effective = charge − import + export``. Sans batterie,
elle est la production de la série. Les DEUX énergies sont publiées
(``production_kwh``, celle du point de livraison, et ``production_brute_kwh``,
celle du champ) pour qu'aucun taux ne se lise sur le mauvais dénominateur.

LE PLAFOND D'INJECTION (CALX190)
----------------------------------
Il est SAISI sur le RACCORDEMENT du site, avec sa justification (contrat de
raccordement, autorisation) : un plafond d'injection se négocie point de
livraison par point de livraison, il n'est ni un réglage société ni une
constante du dépôt. Aucun kW n'est codé en dur ici, et aucun plafond ONEE
n'est supposé : plafond non saisi ⇒ rien n'est écrêté et RIEN n'est affiché
(un « 0 kWh écrêté » se lirait comme un plafond vérifié). Un plafond SAISI
SANS justification OMET le bloc en nommant le champ — on ne peut ni ignorer
un plafond déclaré, ni appliquer un plafond que personne ne peut défendre
devant l'ONEE.

L'énergie écrêtée par le plafond est publiée comme une étape DÉCLARÉE
(``etape_plafond``, les six clés de ``etapes.CLES_ETAPE``, ``gain: False``,
``source`` = la justification saisie), prête à être versée à la cascade par
l'orchestrateur.
"""
from __future__ import annotations

from apps.calepinage.services import etapes
from apps.calepinage.services.autoconsommation import (BilanInvalide,
                                                       MOTIF_SANS_COURBE,
                                                       bilan_autoconsommation)
from apps.calepinage.services.etapes import batterie as bloc_batterie
from .. import limites_livraison as _limites
from ..valeurs import nombre as _nombre

LIBELLE = "Plafond d'injection au point de livraison"

#: La clé du contexte qui déclare un calepinage HORS RÉSEAU. CALX191 la relit
#: ici : le mode est déclaré à UN endroit, et les deux blocs en tirent des
#: conclusions opposées sans jamais se contredire.
CLE_HORS_RESEAU = 'hors_reseau'

#: La clé du contexte qui porte le RACCORDEMENT du site, posée par
#: ``services/simulation.py`` (CALX5) : ``{plafond_injection_kw,
#: plafond_injection_justification}``. Les deux sont SAISIS — un plafond
#: d'injection se négocie point de livraison par point de livraison.
CLE_RACCORDEMENT = 'raccordement'

#: Les deux champs du raccordement, nommés ici sous la forme que l'écran
#: affiche : un refus qui dit « plafond » sans dire OÙ le saisir ne sert à
#: rien.
CHAMP_PLAFOND = 'plafond_injection_kw'
CHAMP_JUSTIFICATION = 'plafond_injection_justification'

#: ACAL829 — le plafond de SOUTIRAGE (kW) et sa justification, saisis sur le
#: même raccordement : une limite du réseau à l'import, pas à l'injection.
CHAMP_SOUTIRAGE = 'plafond_soutirage_kw'
CHAMP_JUSTIFICATION_SOUTIRAGE = 'plafond_soutirage_justification'

#: Les colonnes de points que ce bloc écrit (contrat CALX142).
COLONNES_POSEES = ('charge_kwh', 'reseau_import_kwh', 'reseau_export_kwh')

#: ACAL828 — une plage horaire se lit heure par heure : un autre pas est omis.
MOTIF_PLAGES_PAS_NON_HORAIRE = (
    "Les plages horaires du plafond d'injection se lisent heure par heure : "
    "la série n'est pas au pas de 60 min, le bloc « autoconsommation » est "
    'omis plutôt que de fabriquer des heures.')

REFERENCE_PVSYST = (
    'PVsyst — Self-consumption : les échanges d’énergie sont instantanés, le '
    'croisement exige un profil de charge '
    '(https://www.pvsyst.com/help/project-design/grid-connected-system-'
    'definition/self-consumption.html)')

MOTIF_HORS_RESEAU = (
    'Ce calepinage est déclaré hors réseau : il n’y a ni import ni injection, '
    'donc aucun taux d’autoconsommation réseau à publier. Le bloc '
    '« autoconsommation » est omis — c’est le bloc « hors_reseau » '
    'qui décrit ce mode.')

MOTIF_SANS_PRODUCTION = (
    "Aucune colonne d'énergie n'est lisible sur la série sortie de chaîne : "
    'le croisement se joue heure par heure contre une production, et '
    "celle-ci n'est pas calculée. Le bloc « autoconsommation » est omis.")

DEFINITION_TAUX = (
    "Taux d'autoconsommation = énergie autoconsommée ÷ production vue au "
    'point de livraison. Couverture = énergie autoconsommée ÷ CONSOMMATION '
    '(règle COUV-AUTO) — jamais production ÷ consommation. Autonomie = 1 − '
    'énergie importée ÷ consommation.')


#: ACAL2024 (D-ACAL-97) — la clé du contexte qui porte, pour un calepinage DE LEAD, les deux
#: taux de la conception rangée (:func:`taux_de_la_conception`), posée par ``simulation.py``.
CLE_TAUX_CONCEPTION = 'taux_conception_lead'

#: ACAL2024 — la définition publiée quand les deux taux viennent de la conception du lead.
DEFINITION_TAUX_CONCEPTION = (
    "Taux d'autoconsommation et couverture lus sur la conception du lead (version {version}, "
    '{panneaux} panneaux) : les mêmes que la fiche du lead et le devis, jamais recalculés ici. '
    'Les énergies et le tableau mensuel sont ceux de la pose simulée. ' + DEFINITION_TAUX)

#: T4-X7-002 — la conception décrit une AUTRE installation que la pose simulée (autre puissance,
#: ou batterie d'un côté seulement) : ses taux ne se lisent pas à côté des énergies de cette pose.
DEFINITION_TAUX_AUTRE_POSE = (
    "Taux d'autoconsommation et couverture calculés sur la pose simulée : la conception du lead "
    '(version {version}, {panneaux} panneaux{ecart}) décrit une autre installation, ses taux ne '
    "s'appliquent pas à cette pose. " + DEFINITION_TAUX)

#: T4-X7-002 — ``taux_source`` du bloc : d'où viennent ``taux_autoconsommation`` et ``taux_couverture``.
#: ``conception`` : ceux de la conception du lead (ACAL2024) ; ``pose`` : aucun taux de conception
#: (pas de lead, conception incomplète, agricole, taux absent) — le bilan propre de toujours ;
#: ``autre_installation`` : SEUL signal d'un écart réel (``_ecart_conception_pose``) — les taux de
#: la pose, et les écrans taisent la part servie de la conception. Un résultat rangé sans la clé
#: se lit comme avant.
TAUX_DE_LA_CONCEPTION, TAUX_DE_LA_POSE, TAUX_AUTRE_INSTALLATION = 'conception', 'pose', 'autre_installation'

#: Écart d'ÉGALITÉ de deux puissances (kWc) : l'arrondi d'affichage, comme l'atelier (tailleConception.ts).
_ECART_KWC = 0.005


def _kwc_de_la_pose(contexte):
    """La puissance des panneaux POSÉS (``plans_poses``, raccordés ou non), ou ``None``."""
    plans = (contexte or {}).get('plans_poses')
    if not isinstance(plans, list) or not plans:
        return None
    total = sum(_nombre(plan.get('kwc')) or 0.0 for plan in plans if isinstance(plan, dict))
    return round(total, 3) if total > 0 else None


def _ecart_conception_pose(conception, kwc_pose, apres_batterie):
    """T4-X7-002 — ce qui sépare la conception de la pose simulée (``''`` : rien de connu) :
    la puissance (quand les deux sont connues) et la batterie (quand la conception la dit)."""
    morceaux = []
    kwc_conception = _nombre((conception or {}).get('kwc'))
    if kwc_conception is not None and kwc_pose is not None and abs(kwc_conception - kwc_pose) >= _ECART_KWC:
        morceaux.append(('%.2f kWc' % kwc_conception).replace('.', ','))
    batterie = (conception or {}).get('batterie')
    if isinstance(batterie, bool) and batterie != bool(apres_batterie):
        morceaux.append('avec batterie' if batterie else 'sans batterie')
    return ', '.join(morceaux)


def taux_de_la_conception(calepinage):
    """ACAL2024 — ``{taux_autoconsommation, taux_couverture, version, panneaux, kwc, batterie}`` de l'option
    retenue de la conception COURANTE d'un calepinage DE LEAD (``devis_retenu``, porte de
    ventes), ou ``None`` : sans lead (le calepinage garde son bilan propre), conception non
    complète, agricole, ou taux absent. Lecture pure."""
    if not getattr(calepinage, 'lead_id', None):
        return None
    from ..devis_retenu import conception_du_calepinage

    conception = conception_du_calepinage(calepinage)
    if not conception or conception.get('etat') != 'complet' or conception.get('marche') == 'agricole':
        return None
    valeurs = (conception.get('valeurs') or {}).get(conception.get('option_retenue')) or {}
    lus = {cle: _nombre((valeurs.get(nom) or {}).get('valeur')) for cle, nom in (
        ('taux_autoconsommation', 'autoconsommation'), ('taux_couverture', 'couverture'))}
    if None in lus.values():
        return None
    # T4-X7-002 — la puissance et la batterie de cette option : de quoi dire si elle décrit la pose.
    return dict(lus, version=conception.get('version'),
                panneaux=(valeurs.get('nb_panneaux') or {}).get('valeur'),
                kwc=_nombre((valeurs.get('puissance_kwc') or {}).get('valeur')),
                batterie=conception.get('option_retenue') == 'avec')


def mode_hors_reseau(contexte):
    """Le calepinage est-il DÉCLARÉ hors réseau ? (relu par CALX191)

    Un mode déclaré nulle part n'est pas un mode deviné : en l'absence de
    déclaration, l'installation est raccordée — c'est le cas de tous les
    calepinages existants, et le comportement d'aujourd'hui ne change pas.
    """
    declaration = (contexte or {}).get(CLE_HORS_RESEAU)
    if not isinstance(declaration, dict):
        return False
    return bool(declaration.get('actif'))


def _colonne(serie, nom):
    """La colonne ``nom`` de la série, ou ``None`` si un point ne l'a pas."""
    valeurs = []
    for point in (serie or {}).get('points') or []:
        brut = _nombre(point.get(nom))
        if brut is None:
            return None
        valeurs.append(brut)
    return valeurs or None


def _production_au_compteur(serie, production, courbe):
    """La production vue au point de livraison — ``(valeurs, apres_batterie)``.

    Les colonnes de CALX188 (``reseau_import_kwh``, ``reseau_export_kwh``)
    disent ce que la batterie a déjà déplacé : ``charge − import + export``.
    Sans elles, la production du champ se présente telle quelle.
    """
    imports = _colonne(serie, 'reseau_import_kwh')
    exports = _colonne(serie, 'reseau_export_kwh')
    if imports is None or exports is None:
        return list(production), False
    longueur = min(len(courbe), len(imports), len(exports))
    return ([max(0.0, courbe[rang] - imports[rang] + exports[rang])
             for rang in range(longueur)], True)


def _plafond_saisi(contexte):
    """Le plafond SAISI et sa justification — ``(kw, justification)``.

    Les deux se lisent sur le raccordement du site ; non saisis, ils rendent
    ``None`` et rien n'est supposé. La justification saisie SEULE (sans
    plafond) n'écrête rien : il n'y a pas de plafond à défendre.
    """
    declaration = (contexte or {}).get(CLE_RACCORDEMENT)
    if not isinstance(declaration, dict):
        return None, ''
    plafond = _nombre(declaration.get(CHAMP_PLAFOND))
    if plafond is None and not _plages_saisies(contexte):
        return None, ''
    justification = str(declaration.get(CHAMP_JUSTIFICATION) or '').strip()
    return plafond, justification


def _plages_saisies(contexte):
    """ACAL828 — les plages horaires saisies sur le raccordement, ou ``None``
    (déjà validées par ``limites_livraison.plages_saisies`` à la saisie)."""
    declaration = (contexte or {}).get(CLE_RACCORDEMENT)
    plages = (declaration.get(_limites.CHAMP_PLAGES)
              if isinstance(declaration, dict) else None)
    return plages if isinstance(plages, list) and plages else None


def _soutirage_saisi(contexte):
    """ACAL829 — ``(plafond kW, justification)`` du soutirage, ou
    ``(None, '')`` : non saisi, rien n'est publié (jamais « 0 heure »)."""
    declaration = (contexte or {}).get(CLE_RACCORDEMENT)
    if not isinstance(declaration, dict):
        return None, ''
    plafond = _nombre(declaration.get(CHAMP_SOUTIRAGE))
    if plafond is None:
        return None, ''
    return plafond, str(
        declaration.get(CHAMP_JUSTIFICATION_SOUTIRAGE) or '').strip()


def _etape_du_plafond(bloc_plafond):
    """L'étape DÉCLARÉE de l'écrêtage d'injection (six clés de CALX147).

    ``gain: False`` — le plafond retranche bien de l'énergie livrée ; la
    ``source`` est la justification SAISIE, jamais le module.
    """
    return etapes.etape_appliquee(
        LIBELLE,
        source=bloc_plafond['justification'],
        entree={'plafond_kw': bloc_plafond['plafond_kw'],
                'heures_ecretees': bloc_plafond['heures_ecretees'],
                'energie_ecretee_kwh': bloc_plafond['energie_ecretee_kwh']},
        reference=REFERENCE_PVSYST,
        gain=False)


def _omission(motif, *, champ=''):
    texte = motif.strip()
    if champ:
        texte = f'{texte} Champ manquant : « {champ} ».'
    return {
        'taux_autoconsommation': None, 'taux_couverture': None,
        'taux_autonomie': None, 'heures_sans_import': None,
        'energie': None, 'par_mois': None, 'plafond': None,
        'soutirage': None, 'etape_plafond': None, 'definition': '', 'motif_absence': texte,
    }


COLONNES_PAR_MOIS = ('consommation_kwh', 'production_kwh',
                     'autoconsomme_kwh', 'import_reseau_kwh',
                     'export_reseau_kwh')


def _par_mois(serie, courbe, au_compteur, imports, exports, annees):
    """ACAL445 — les 12 lignes mensuelles, sommes des pas du mois.

    Les tableaux sont ceux déjà calculés (courbe, production au compteur,
    imports, exports) ; ``autoconsomme = consommation − import``, la même
    identité que le bilan horaire. Un mois sans aucun pas vaut ``None`` (jamais
    0) ; les énergies sont ramenées à l'année moyenne comme ``_par_an``.
    """
    points = (serie or {}).get('points') or []
    sommes = {mois: None for mois in range(1, 13)}
    for rang in range(min(len(points), len(courbe), len(au_compteur),
                          len(imports), len(exports))):
        mois = _nombre(points[rang].get('mois'))
        if mois is None or int(mois) not in sommes:
            continue
        ligne = sommes[int(mois)] or dict.fromkeys(COLONNES_PAR_MOIS, 0.0)
        ligne['consommation_kwh'] += courbe[rang]
        ligne['production_kwh'] += au_compteur[rang]
        ligne['autoconsomme_kwh'] += courbe[rang] - imports[rang]
        ligne['import_reseau_kwh'] += imports[rang]
        ligne['export_reseau_kwh'] += exports[rang]
        sommes[int(mois)] = ligne
    lignes = []
    for mois, ligne in sommes.items():
        lignes.append({'mois': mois, **{
            colonne: (None if ligne is None
                      else _par_an(round(ligne[colonne], 3), annees))
            for colonne in COLONNES_PAR_MOIS}})
    return lignes


# ── l'entrée unique, appelée par services/simulation.py (CALX5) ──────────

def bloc_autoconsommation(serie, contexte=None, *, charge=None):
    """Le bloc ``resultat['autoconsommation']`` et la série enrichie.

    Args:
        serie: la série sortie de chaîne, ENRICHIE par CALX188 quand une
            batterie a été dispatchée (ses colonnes disent ce qui a été
            déplacé ; elles ne sont jamais redispatchées ici).
        contexte: le contexte de simulation (CALX5).
        charge: la courbe de charge de CALX189, déjà assemblée.

    Returns:
        ``(serie, bloc)``. Le bloc OMIS porte ``energie: None`` et son motif,
        et la série ressort INCHANGÉE.
    """
    contexte = contexte or {}

    possible, motif_fuseau = bloc_batterie.verdict_horaire(contexte)
    if not possible:
        return serie, _omission(motif_fuseau)

    if mode_hors_reseau(contexte):
        return serie, _omission(MOTIF_HORS_RESEAU)

    bloc_charge = bloc_batterie.courbe_de_charge(serie, contexte,
                                                 charge=charge)
    courbe = bloc_charge.get('courbe')
    if not courbe:
        motif = (bloc_charge.get('omissions') or {}).get('autoconsommation')
        return serie, _omission(motif or MOTIF_SANS_COURBE)

    production = bloc_batterie.production_horaire(serie)
    if production is None:
        return serie, _omission(MOTIF_SANS_PRODUCTION,
                                champ='serie.colonne_energie')

    au_compteur, apres_batterie = _production_au_compteur(serie, production,
                                                          courbe)
    longueur = min(len(courbe), len(au_compteur))
    courbe = list(courbe[:longueur])
    au_compteur = list(au_compteur[:longueur])
    brute = sum(production[:longueur])

    plafond_kw, justification = _plafond_saisi(contexte)
    pas = bloc_batterie.pas_minutes(serie, bloc_charge)
    plages = _plages_saisies(contexte)
    par_pas = None
    if plages:
        if pas != 60:
            return serie, _omission(MOTIF_PLAGES_PAS_NON_HORAIRE,
                                    champ='simulation.resolution_minutes')
        points = (serie or {}).get('points') or []
        depart = (int(_nombre(points[0].get('heure')) or 0)
                  if points and isinstance(points[0], dict) else 0)
        par_pas = _limites.plafonds_par_pas(plages, depart, longueur)
    soutirage_kw, justification_soutirage = _soutirage_saisi(contexte)
    if soutirage_kw is not None and not justification_soutirage:
        return serie, _omission(
            "Un plafond de soutirage doit porter sa justification (contrat, "
            'prescription du gestionnaire de réseau).',
            champ=f'{CLE_RACCORDEMENT}.{CHAMP_JUSTIFICATION_SOUTIRAGE}')
    try:
        bilan = bilan_autoconsommation(
            courbe, au_compteur,
            plafond_injection_kw=plafond_kw,
            justification_plafond=justification,
            pas_heures=float(pas) / 60.0, plafonds_par_pas=par_pas)
    except BilanInvalide as refus:
        champ = (f'{CLE_RACCORDEMENT}.{refus.champ}' if refus.champ else '')
        return serie, _omission(refus.motif, champ=champ)

    from apps.calepinage.services.chaine_pertes import annees_de_la_fenetre

    return _publier(serie, bilan, courbe, au_compteur, brute, apres_batterie,
                    annees=annees_de_la_fenetre(contexte), plages=plages,
                    conception=contexte.get(CLE_TAUX_CONCEPTION),
                    kwc_pose=_kwc_de_la_pose(contexte),
                    soutirage=(None if soutirage_kw is None else (
                        soutirage_kw, justification_soutirage,
                        float(pas) / 60.0)))


def _soutirage_publie(soutirage, imports, annees):
    """ACAL829 — le bloc ``soutirage``, ou ``None`` sans plafond saisi."""
    if soutirage is None:
        return None
    plafond, justification, pas_heures = soutirage
    mesure = _limites.soutirage_au_dessus(imports, plafond, pas_heures)
    return {
        'plafond_kw': plafond, 'justification': justification,
        'pointe_kw': mesure['pointe_kw'],
        'heures_au_dessus': mesure['heures_au_dessus'],
        'energie_au_dessus_kwh': _par_an(mesure['energie_au_dessus_kwh'],
                                         annees),
    }


def _plages_publiees(plages, mesurees, annees):
    """ACAL828 — par plage saisie : ses heures et l'énergie qu'elle écrête
    (0 heure et 0 kWh quand rien n'a dépassé)."""
    par_rang = {ligne['rang']: ligne for ligne in mesurees}
    publiees = []
    for rang, plage in enumerate(plages or ()):
        ligne = par_rang.get(rang) or {'heures_ecretees': 0,
                                       'energie_ecretee_kwh': 0.0}
        publiees.append(dict(
            plage, heures_ecretees=_par_an(ligne['heures_ecretees'], annees),
            energie_ecretee_kwh=_par_an(ligne['energie_ecretee_kwh'],
                                        annees)))
    return publiees


def _par_an(valeur, annees):
    """ACAL54 — une énergie de la fenêtre, ramenée à l'année moyenne."""
    if valeur is None or isinstance(valeur, bool):
        return valeur
    return round(float(valeur) / annees, 3) if annees > 1 else valeur


def _publier(serie, bilan, courbe, au_compteur, brute, apres_batterie,
             annees=1, plages=None, soutirage=None, conception=None, kwc_pose=None):
    """La série enrichie et le bloc, tirés du MÊME bilan horaire.

    ACAL54 — ``annees`` : le N de la fenêtre météo ; les énergies du bloc
    sont ramenées à l'ANNÉE MOYENNE (les taux, rapports de deux énergies,
    ne bougent pas ; la série horaire reste celle de la fenêtre).
    ACAL2024 — ``conception`` (calepinage de lead) : les deux taux sont ceux
    de la conception, la définition le dit avec sa version et sa taille.
    T4-X7-002 — seulement quand la conception décrit CETTE pose (même puissance,
    batterie des deux côtés ou d'aucun) ; sinon les taux de la pose simulée, ceux
    des énergies publiées à côté, et la définition dit pourquoi (``taux_source``).
    """
    ecart = _ecart_conception_pose(conception, kwc_pose, apres_batterie) if conception else ''
    if ecart:
        definition = DEFINITION_TAUX_AUTRE_POSE.format(
            version=conception.get('version'), panneaux=conception.get('panneaux'), ecart=', ' + ecart)
    elif conception:
        definition = DEFINITION_TAUX_CONCEPTION.format(**conception)
        bilan = dict(bilan, taux_autoconsommation=conception['taux_autoconsommation'],
                     taux_couverture=conception['taux_couverture'])
    else:
        definition = DEFINITION_TAUX
    taux_source = (TAUX_AUTRE_INSTALLATION if ecart else TAUX_DE_LA_CONCEPTION if conception
                   else TAUX_DE_LA_POSE)
    bloc_plafond = bilan['plafond']
    if bloc_plafond:
        exports = list(bloc_plafond['surplus_apres_ecretage'])
        ecretee = bloc_plafond['energie_ecretee_kwh']
    else:
        exports = [max(0.0, prod - conso)
                   for conso, prod in zip(courbe, au_compteur)]
        ecretee = None
    imports = [max(0.0, conso - prod)
               for conso, prod in zip(courbe, au_compteur)]

    suite = bloc_batterie.poser_colonnes(serie, {
        'charge_kwh': [round(valeur, 4) for valeur in courbe],
        'reseau_import_kwh': [round(valeur, 4) for valeur in imports],
        'reseau_export_kwh': [round(valeur, 4) for valeur in exports],
    })

    part = bloc_batterie.autonomie(imports, courbe, annees=annees)
    publie_plafond = None
    etape = None
    if bloc_plafond:
        # ACAL1604 — les heures écrêtées, à l'année moyenne comme l'énergie.
        heures_ecretees = _par_an(bloc_plafond['heures_ecretees'], annees)
        publie_plafond = {
            'applique': True,
            'plafond_kw': bloc_plafond['plafond_kw'],
            'justification': bloc_plafond['justification'],
            'energie_ecretee_kwh': _par_an(ecretee, annees),
            'heures_ecretees': heures_ecretees,
            'motif': bloc_plafond['motif'],
            'plages': _plages_publiees(plages, bloc_plafond['plages'],
                                       annees),
        }
        etape = _etape_du_plafond(dict(
            bloc_plafond, energie_ecretee_kwh=_par_an(ecretee, annees),
            heures_ecretees=heures_ecretees))

    return suite, {
        'taux_autoconsommation': bilan['taux_autoconsommation'],
        'taux_couverture': bilan['taux_couverture'],
        'taux_autonomie': part['taux_autonomie'],
        'heures_sans_import': part['heures_sans_import'],
        'energie': {
            'consommation_kwh': _par_an(bilan['consommation_kwh'], annees),
            'production_kwh': _par_an(bilan['production_kwh'], annees),
            'production_brute_kwh': _par_an(round(brute, 3), annees),
            'autoconsomme_kwh': _par_an(bilan['autoconsomme_kwh'], annees),
            'surplus_kwh': _par_an(bilan['surplus_kwh'], annees),
            'export_reseau_kwh': _par_an(round(sum(exports), 3), annees),
            'import_reseau_kwh': _par_an(round(sum(imports), 3), annees),
            'apres_batterie': apres_batterie,
        },
        'par_mois': _par_mois(serie, courbe, au_compteur, imports, exports,
                              annees),
        'plafond': publie_plafond,
        'soutirage': _soutirage_publie(soutirage, imports, annees),
        'etape_plafond': etape,
        'definition': definition,
        'taux_source': taux_source,
        'motif_absence': '',
    }
