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

#: Les colonnes de points que ce bloc écrit (contrat CALX142).
COLONNES_POSEES = ('charge_kwh', 'reseau_import_kwh', 'reseau_export_kwh')

REFERENCE_PVSYST = (
    'PVsyst — Self-consumption : les échanges d’énergie sont instantanés, le '
    'croisement exige un profil de charge '
    '(https://www.pvsyst.com/help/project-design/grid-connected-system-'
    'definition/self-consumption.html)')

MOTIF_HORS_RESEAU = (
    'Ce calepinage est déclaré HORS RÉSEAU : il n’y a ni import ni injection, '
    'donc aucun taux d’autoconsommation réseau à publier. Le bloc '
    '« autoconsommation » est OMIS — c’est le bloc « hors_reseau » (CALX191) '
    'qui décrit ce mode.')

MOTIF_SANS_PRODUCTION = (
    "Aucune colonne d'énergie n'est lisible sur la série sortie de chaîne : "
    'le croisement se joue heure par heure CONTRE une production, et '
    "celle-ci n'est pas calculée. Le bloc « autoconsommation » est OMIS.")

DEFINITION_TAUX = (
    "Taux d'autoconsommation = énergie autoconsommée ÷ production vue au "
    'point de livraison. Couverture = énergie autoconsommée ÷ CONSOMMATION '
    '(règle COUV-AUTO) — jamais production ÷ consommation. Autonomie = 1 − '
    'énergie importée ÷ consommation.')


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


def _nombre(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return None if nombre != nombre else nombre


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
    if plafond is None:
        return None, ''
    justification = str(declaration.get(CHAMP_JUSTIFICATION) or '').strip()
    return plafond, justification


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
        'energie': None, 'plafond': None, 'etape_plafond': None,
        'definition': '', 'motif_absence': texte,
    }


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
    try:
        bilan = bilan_autoconsommation(
            courbe, au_compteur,
            plafond_injection_kw=plafond_kw,
            justification_plafond=justification,
            pas_heures=float(pas) / 60.0)
    except BilanInvalide as refus:
        champ = (f'{CLE_RACCORDEMENT}.{refus.champ}' if refus.champ else '')
        return serie, _omission(refus.motif, champ=champ)

    return _publier(serie, bilan, courbe, au_compteur, brute, apres_batterie)


def _publier(serie, bilan, courbe, au_compteur, brute, apres_batterie):
    """La série enrichie et le bloc, tirés du MÊME bilan horaire."""
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

    part = bloc_batterie.autonomie(imports, courbe)
    publie_plafond = None
    etape = None
    if bloc_plafond:
        publie_plafond = {
            'applique': True,
            'plafond_kw': bloc_plafond['plafond_kw'],
            'justification': bloc_plafond['justification'],
            'energie_ecretee_kwh': ecretee,
            'heures_ecretees': bloc_plafond['heures_ecretees'],
            'motif': bloc_plafond['motif'],
        }
        etape = _etape_du_plafond(bloc_plafond)

    return suite, {
        'taux_autoconsommation': bilan['taux_autoconsommation'],
        'taux_couverture': bilan['taux_couverture'],
        'taux_autonomie': part['taux_autonomie'],
        'heures_sans_import': part['heures_sans_import'],
        'energie': {
            'consommation_kwh': bilan['consommation_kwh'],
            'production_kwh': bilan['production_kwh'],
            'production_brute_kwh': round(brute, 3),
            'autoconsomme_kwh': bilan['autoconsomme_kwh'],
            'surplus_kwh': bilan['surplus_kwh'],
            'export_reseau_kwh': round(sum(exports), 3),
            'import_reseau_kwh': round(sum(imports), 3),
            'apres_batterie': apres_batterie,
        },
        'plafond': publie_plafond,
        'etape_plafond': etape,
        'definition': DEFINITION_TAUX,
        'motif_absence': '',
    }
