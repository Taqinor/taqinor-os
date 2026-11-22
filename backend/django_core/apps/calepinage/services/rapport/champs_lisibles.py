"""R3-19 — les chemins internes d'un motif, imprimés en intitulés de métier.

Les motifs d'omission de la cascade finissent par « Champ manquant : « chemin
». » (``etapes.etape_omise``) ou citent « Non renseigné(s) : « chemin » ».
Ce texte est une DONNÉE servie, relue ailleurs par expression régulière
(``a_renseigner.py``, contrat ``a_renseigner``) : il ne change PAS à la
source. Seul le texte IMPRIMÉ (rapport, diagramme) passe par ``motif_lisible``.

Les intitulés viennent, dans cet ordre, du registre des réglages société
(``parametres_cles.registre``), des libellés de champ de fiche
(``rapport.systeme.LIBELLE_CHAMP_FICHE``) puis de la table ci-dessous, qui ne
porte que ce que ces deux sources ne savent pas dire. Un chemin sans
intitulé connu s'imprime « donnée manquante » — jamais brut.
"""
from __future__ import annotations

import re

DONNEE_MANQUANTE = 'donnée manquante'

#: Chemin de la donnée du document de calepinage → intitulé de métier. La
#: clé est le chemin SANS crochets (``cables[W1].section_mm2`` →
#: ``cables.section_mm2``).
INTITULES_CHEMINS = {
    'ombrage.solarAccess': "accès solaire de chaque module (ombrage)",
    'ombrage.solarAccess.values': "accès solaire de chaque module (ombrage)",
    'ombrage.shading12x24': "matrice d'ombrage 12 mois × 24 heures",
    'ombrage.skyViewFactor': 'facteur de vue du ciel',
    'ombrage.layout': 'implantation des modules (ombrage)',
    'solarAccess.bandes': "bandes d'accès solaire des modules",
    'serie.points': 'série météo horaire',
    'serie.points.heure': 'heure de chaque point de la série météo',
    'serie.points.t_cell_c': 'température de cellule de la série horaire',
    'serie.colonne_energie': "colonne d'énergie de la série horaire",
    'serie_horaire.mois': 'mois couverts par la série horaire',
    'meteo.heure.decalage_minutes': 'décalage horaire de la série météo',
    'horizon.points': "profil d'horizon du site",
    'site.lat': 'latitude du site',
    'site.lon': 'longitude du site',
    'plan.inclinaison_deg': 'inclinaison du pan',
    'plan.azimut_pvgis_deg': 'orientation du pan',
    'electrique.onduleurs': 'onduleurs retenus',
    'electrique.chainage.puissance_module_wc': 'puissance crête du module (Wc)',
    'cheminement.onduleur_vers_tgbt_m': 'longueur de câble onduleur → TGBT (m)',
    'cables': 'câbles du projet',
    'cables.section_mm2': 'section du câble (mm²)',
    'affectation': 'affectation des modules aux optimiseurs',
    'simulation.resolution_minutes': 'pas de temps de la simulation (minutes)',
    # Champs de fiche technique cités par leur nom de base de données.
    'degradation_annuelle_pct': 'dégradation annuelle du module (%/an)',
    'degradation_annee1_pct': 'dégradation du module la première année (%)',
    'ond_rendement_euro_pct': "rendement européen de l'onduleur (%)",
    'opt_rendement_pct': "rendement de l'optimiseur (%)",
    'rendement_par_charge': "courbe de rendement de l'onduleur selon la charge",
    'phases': "nombre de phases de l'onduleur",
}

_FICHES = ('fiche_module', 'fiche_onduleur', 'fiche', 'FicheTechnique')
_CROCHETS = re.compile(r'\[[^\]]*\]')
_PARENTHESE_FINALE = re.compile(r'\s*(\(.*\))\s*$', re.S)
_CHAMP_MANQUANT = re.compile(r'(Champ manquant : )« (.*?) »(?=\.|$)', re.S)
_NON_RENSEIGNES = re.compile(r'(Non renseigné\(s\) : )((?:« [^»]+ »(?:, )?)+)')
_UN_CHAMP = re.compile(r'« ([^»]+) »')
#: Un identifiant interne cité entre guillemets dans une phrase (jamais un
#: mot de la langue) : un point, un souligné ou un crochet, sans espace.
_IDENTIFIANT = re.compile(r'^[A-Za-z][\w.\[\]]*[._\[][\w.\[\]]*$')


def _registre_ou_fiche(prefixe, cle):
    """L'intitulé d'un réglage société ou d'un champ de fiche, ou ``''``."""
    from ..parametres_cles import registre
    from .systeme import LIBELLE_CHAMP_FICHE

    if prefixe in ('simulation', 'reglages_simulation', ''):
        if cle in registre('simulation'):
            return registre('simulation')[cle][0]
    if prefixe in ('electrique_societe', ''):
        if cle in registre('electrique_societe'):
            return registre('electrique_societe')[cle][0]
    if prefixe in _FICHES or prefixe == '':
        return LIBELLE_CHAMP_FICHE.get(cle) or INTITULES_CHEMINS.get(cle, '')
    return ''


def _intitule_champ(chemin):
    """L'intitulé de métier d'UN chemin ; ``''`` quand il n'est pas connu.

    Plusieurs chemins séparés par « / » se traduisent un à un ; une mention
    entre parenthèses en queue (``(ligne « Mono-Si »)``) est conservée.
    """
    texte = str(chemin or '').strip()
    suite = ''
    trouve = _PARENTHESE_FINALE.search(texte)
    if trouve:
        suite = ' ' + trouve.group(1)
        texte = texte[:trouve.start()].strip()
    if ' / ' in texte:
        parts = [_intitule_champ(p) for p in texte.split(' / ')]
        return ' / '.join(parts) + suite if all(parts) else ''
    sans = _CROCHETS.sub('', texte)
    if sans in INTITULES_CHEMINS:
        return INTITULES_CHEMINS[sans] + suite
    prefixe, _, cle = sans.partition('.')
    if not cle:
        prefixe, cle = '', sans
    libelle = _registre_ou_fiche(prefixe, cle)
    return libelle + suite if libelle else ''


def _traduire_liste(texte, *, remplacer_inconnu):
    def un_champ(correspondance):
        chemin = correspondance.group(1)
        libelle = _intitule_champ(chemin)
        if libelle:
            return '« %s »' % libelle
        return '« %s »' % DONNEE_MANQUANTE if remplacer_inconnu else (
            correspondance.group(0))

    return _UN_CHAMP.sub(un_champ, texte)


def motif_lisible(motif):
    """Le motif servi, avec ses chemins internes remplacés par leur intitulé.

    Rien d'autre ne change : le reste de la phrase, ses chiffres et sa
    ponctuation sont rendus tels quels. Un chemin inconnu après « Champ
    manquant : » ou « Non renseigné(s) : » devient « donnée manquante ».
    """
    texte = str(motif) if motif is not None else ''
    if '«' not in texte:
        return texte

    def champ_manquant(correspondance):
        libelle = _intitule_champ(correspondance.group(2))
        return '%s« %s »' % (correspondance.group(1),
                             libelle or DONNEE_MANQUANTE)

    texte = _CHAMP_MANQUANT.sub(champ_manquant, texte)
    texte = _NON_RENSEIGNES.sub(
        lambda c: c.group(1) + _traduire_liste(c.group(2),
                                               remplacer_inconnu=True),
        texte)

    def identifiant_en_phrase(correspondance):
        chemin = correspondance.group(1)
        libelle = _intitule_champ(chemin) \
            if _IDENTIFIANT.match(chemin) else ''
        return '« %s »' % libelle if libelle else correspondance.group(0)

    return _UN_CHAMP.sub(identifiant_en_phrase, texte)
