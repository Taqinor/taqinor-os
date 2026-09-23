"""CALX191 — LE BLOC « hors_reseau » : le défaut d'alimentation sur la série.

CE QUE CE MODULE EST
----------------------
Un PRODUCTEUR DE BLOC POST-CHAÎNE, comme ``etapes/batterie.py`` et
``etapes/autoconsommation.py``. ``hors_reseau`` ne figure pas dans
``chaine_pertes.ORDRE_ETAPES`` : un site isolé ne perd pas de production, il
manque de l'énergie à certaines heures — et ce défaut se compte en heures de
charge NON SERVIE, pas en pourcentage de pertes.

Sans réseau, il n'y a pas de soutirage : ce que la production et la banque ne
servent pas est une DÉFAILLANCE DE CHARGE (loss of load). C'est exactement le
chiffre qu'un site isolé doit connaître avant d'être vendu, et
``services/hors_reseau.py::simuler_hors_reseau`` (CAL154) le calcule déjà
heure par heure ; il est appelé TEL QUEL, avec son dimensionnement
(``banque_pour_autonomie``) par ``dimensionner_hors_reseau``.

Parité citée :
* PV*SOL — protection de batterie hors réseau à trois niveaux et règle de
  dimensionnement publiée :
  https://help.valentin-software.com/pvsol/en/pages/battery-inverter-and-battery/general/
* PVsyst — le régulateur gère le SOC par seuils, déconnectant le champ plein
  et la charge vide :
  https://www.pvsyst.com/help/project-design/stand-alone-systems-definition/index.html

NI QUANTILES, NI AUTOCONSOMMATION RÉSEAU DANS CE MODE
-------------------------------------------------------
Un P90 de production ne dit RIEN d'un site isolé : ce qui compte n'est pas
l'énergie produite une année sur dix, c'est l'heure où la charge n'est pas
servie. Le bloc publie donc ``quantiles_publiables: False`` avec son motif,
et ``etapes/autoconsommation.py`` s'omet de lui-même dans ce mode (les deux
lisent la MÊME déclaration, ``CLE_HORS_RESEAU``). Aucune colonne
``reseau_import_kwh`` / ``reseau_export_kwh`` n'est écrite : il n'y a pas de
réseau, et un zéro se lirait « mesuré à zéro ».

CE QUI N'EST JAMAIS SUPPOSÉ (D-CALX 7)
----------------------------------------
Les JOURS D'AUTONOMIE sont SAISIS — un abri isolé et un relais télécom n'ont
pas la même exigence, et ce nombre décide du prix de la banque. La
profondeur de décharge et le rendement aller-retour se lisent sur la fiche du
pack (CAL153), résolue par ``services/simulation.py`` (CALX5). Rien ne
manque en silence : chaque absence OMET le bloc en nommant le champ.
"""
from __future__ import annotations

from apps.calepinage.services.etapes import autoconsommation as bloc_conso
from apps.calepinage.services.etapes import batterie as bloc_batterie
from apps.calepinage.services.hors_reseau import (HorsReseauInvalide,
                                                  dimensionner_hors_reseau)

LIBELLE = 'Site hors réseau'

#: La clé du contexte qui déclare le mode — la MÊME que lit CALX190.
CLE_CONTEXTE = bloc_conso.CLE_HORS_RESEAU

#: Les colonnes de points que ce bloc écrit (contrat CALX142). Ni import ni
#: export : sans réseau, ces deux colonnes n'ont pas d'objet.
COLONNES_POSEES = ('charge_kwh', 'batterie_soc_pct')

MOTIF_RACCORDE = (
    "Ce calepinage n'est pas déclaré hors réseau : il n'y a donc aucun défaut "
    "d'alimentation à chiffrer. Le bloc « hors_reseau » est OMIS — c'est le "
    'bloc « autoconsommation » (CALX190) qui décrit un site raccordé.')

MOTIF_SANS_COURBE = (
    "Aucune courbe de consommation n'est disponible : le défaut "
    "d'alimentation se compte heure par heure CONTRE une consommation. Le "
    'bloc « hors_reseau » est OMIS — une consommation supposée ferait vendre '
    'une banque sous-dimensionnée comme suffisante.')

MOTIF_SANS_PRODUCTION = (
    "Aucune colonne d'énergie n'est lisible sur la série sortie de chaîne : "
    "le défaut d'alimentation se compte CONTRE une production, et celle-ci "
    "n'est pas calculée. Le bloc « hors_reseau » est OMIS.")

MOTIF_SANS_AUTONOMIE = (
    "Le nombre de jours d'autonomie n'est pas saisi : il n'est jamais "
    'supposé, et c’est lui qui dimensionne la banque. Le bloc '
    '« hors_reseau » est OMIS.')

MOTIF_QUANTILES = (
    "Hors réseau, aucun quantile de production (P50/P90, CALX186-187) n'est "
    "publié : ce qui décide d'un site isolé n'est pas l'énergie produite une "
    "année sur dix, c'est l'heure où la charge n'est pas servie. Le taux de "
    'défaillance et le mois le plus défavorable tiennent ce rôle.')

MENTION_CONSOMMATION_JOURNALIERE = (
    'La consommation journalière qui dimensionne la banque est DÉRIVÉE de la '
    'courbe de charge assemblée ({total} kWh sur {jours} jour(s)), jamais '
    'saisie séparément : deux chiffres pour une même grandeur finiraient par '
    'diverger.')


def _nombre(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return None if nombre != nombre else nombre


def _grandeur(specs, nom):
    grandeurs = (specs or {}).get('grandeurs')
    if not isinstance(grandeurs, dict):
        return None, None
    ligne = grandeurs.get(nom)
    if not isinstance(ligne, dict):
        return None, None
    return _nombre(ligne.get('valeur')), ligne.get('source')


def _fiche_du_pack(contexte):
    """Les grandeurs de fiche du pack déclaré — DoD, rendement, puissances.

    Elles viennent de ``services/batterie.py::specs_batterie``, résolu par
    l'orchestrateur : ce module ne lit ni base ni réseau.
    """
    declaration = (contexte or {}).get(bloc_batterie.CLE_CONTEXTE)
    groupes = (declaration or {}).get('groupes') or []
    for groupe in groupes:
        if not isinstance(groupe, dict):
            continue
        specs = groupe.get('specs')
        if not isinstance(specs, dict):
            continue
        dod, source_dod = _grandeur(specs, 'dod_pct')
        return {
            'dod_pct': dod,
            'source_dod': source_dod,
            'rendement_ar_pct': _grandeur(specs, 'rendement_ar_pct')[0],
            'puissance_charge_kw': _nombre(specs.get('puissance_charge_kw')),
            'puissance_decharge_kw': _nombre(
                specs.get('puissance_decharge_kw')),
        }
    return {'dod_pct': None, 'source_dod': None, 'rendement_ar_pct': None,
            'puissance_charge_kw': None, 'puissance_decharge_kw': None}


def _mois_par_heure(serie, longueur):
    """Le mois de chaque pas, lu sur le calendrier de la série."""
    mois = []
    for point in ((serie or {}).get('points') or [])[:longueur]:
        numero = _nombre(point.get('mois'))
        if numero is None:
            return None
        mois.append(int(numero))
    return mois if len(mois) == longueur else None


def _omission(motif, *, champ=''):
    texte = motif.strip()
    if champ:
        texte = f'{texte} Champ manquant : « {champ} ».'
    return {
        'heures': None, 'consommation_kwh': None, 'production_kwh': None,
        'servi_kwh': None, 'defaillance_kwh': None,
        'heures_defaillantes': None, 'taux_defaillance': None,
        'surplus_perdu_kwh': None, 'soc_minimal_pct': None,
        'mois_le_plus_defavorable': None, 'par_mois': [],
        'banque': None, 'quantiles_publiables': None, 'motif_quantiles': '',
        'mentions': [], 'motif_absence': texte,
    }


# ── l'entrée unique, appelée par services/simulation.py (CALX5) ──────────

def bloc_hors_reseau(serie, contexte=None, *, charge=None):
    """Le bloc ``resultat['hors_reseau']`` et la série enrichie.

    Args:
        serie: la série sortie de chaîne, côté alternatif (CALX170).
        contexte: le contexte de simulation (CALX5). Sa clé ``hors_reseau``
            porte ``{actif, jours_autonomie, etat_initial_kwh}`` ; la fiche
            du pack se lit sur la déclaration de batterie (CALX188).
        charge: la courbe de charge de CALX189, déjà assemblée.

    Returns:
        ``(serie, bloc)``. Le bloc OMIS porte ``taux_defaillance: None`` et
        son motif, et la série ressort INCHANGÉE.
    """
    contexte = contexte or {}

    if not bloc_conso.mode_hors_reseau(contexte):
        return serie, _omission(MOTIF_RACCORDE, champ=f'{CLE_CONTEXTE}.actif')

    possible, motif_fuseau = bloc_batterie.verdict_horaire(contexte)
    if not possible:
        return serie, _omission(motif_fuseau)

    declaration = contexte.get(CLE_CONTEXTE) or {}
    jours = _nombre(declaration.get('jours_autonomie'))
    if jours is None or jours <= 0:
        return _omission_autonomie(serie)

    bloc_charge = bloc_batterie.courbe_de_charge(serie, contexte,
                                                 charge=charge)
    courbe = bloc_charge.get('courbe')
    if not courbe:
        return serie, _omission(MOTIF_SANS_COURBE)

    production = bloc_batterie.production_horaire(serie)
    if production is None:
        return serie, _omission(MOTIF_SANS_PRODUCTION,
                                champ='serie.colonne_energie')

    longueur = min(len(courbe), len(production))
    courbe = list(courbe[:longueur])
    production = list(production[:longueur])
    pas = bloc_batterie.pas_minutes(serie, bloc_charge)
    heures_du_pas = float(pas) / 60.0

    total_conso = sum(courbe)
    jours_couverts = (longueur * heures_du_pas) / 24.0
    if jours_couverts <= 0:
        return serie, _omission(MOTIF_SANS_COURBE)
    conso_journaliere = total_conso / jours_couverts

    fiche = _fiche_du_pack(contexte)
    try:
        rendu = dimensionner_hors_reseau(
            courbe, production,
            jours_autonomie=jours,
            consommation_journaliere_kwh=conso_journaliere,
            dod_pct=fiche['dod_pct'],
            source_dod=fiche['source_dod'],
            rendement_ar_pct=fiche['rendement_ar_pct'],
            puissance_charge_kw=fiche['puissance_charge_kw'],
            puissance_decharge_kw=fiche['puissance_decharge_kw'],
            mois_par_heure=_mois_par_heure(serie, longueur),
            etat_initial_kwh=declaration.get('etat_initial_kwh'),
            pas_heures=heures_du_pas,
            # CALX272 — les seuils de protection SAISIS sur le document
            # (``hors_reseau.seuils``) ; absents ⇒ comportement d'origine.
            seuils=declaration.get('seuils'))
    except HorsReseauInvalide as refus:
        return serie, _omission(refus.motif,
                                champ=refus.champ or '')

    mention = MENTION_CONSOMMATION_JOURNALIERE.format(
        total=round(total_conso, 1), jours=round(jours_couverts, 1))
    return _publier(serie, rendu, courbe, mention)


def _omission_autonomie(serie):
    return serie, _omission(MOTIF_SANS_AUTONOMIE,
                            champ=f'{CLE_CONTEXTE}.jours_autonomie')


def _publier(serie, rendu, courbe, mention):
    """La série enrichie et le bloc, tirés de la MÊME simulation."""
    banque = rendu['banque']
    simulation = rendu['simulation']
    capacite = banque['capacite_utile_kwh']
    etats = simulation['etat_de_charge_kwh']
    socs = [round(etat / capacite * 100.0, 2) for etat in etats]

    suite = bloc_batterie.poser_colonnes(serie, {
        'charge_kwh': [round(valeur, 4) for valeur in courbe],
        'batterie_soc_pct': socs,
    })

    pire = simulation['mois_le_plus_defavorable']
    return suite, {
        'heures': simulation['heures'],
        'consommation_kwh': simulation['consommation_kwh'],
        'production_kwh': simulation['production_kwh'],
        'servi_kwh': simulation['servi_kwh'],
        'defaillance_kwh': simulation['defaillance_kwh'],
        'heures_defaillantes': simulation['heures_defaillantes'],
        'taux_defaillance': simulation['taux_defaillance'],
        'surplus_perdu_kwh': simulation['surplus_perdu_kwh'],
        'soc_minimal_pct': min(socs) if socs else None,
        'mois_le_plus_defavorable': pire['mois'] if pire else None,
        'par_mois': simulation['par_mois'],
        'banque': {
            'capacite_utile_kwh': banque['capacite_utile_kwh'],
            'capacite_nominale_kwh': banque['capacite_nominale_kwh'],
            'jours_autonomie': banque['jours_autonomie'],
            'dod_pct': banque['dod_pct'],
            'source_dod': banque['source_dod'],
        },
        'quantiles_publiables': False,
        'motif_quantiles': MOTIF_QUANTILES,
        'mentions': (list(banque['mentions']) + list(simulation['mentions'])
                     + [mention]),
        'motif_absence': '',
    }
