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

R3-19 (suite) — la FAMILLE entière : un motif ne laisse sortir ni code de
tâche (``CALX146``, ``ACAL389``), ni chemin pointé, ni clé en soulignés, ni
index. Une référence de code disparaît ; un chemin devient l'intitulé du
calcul ; une clé de poste de pertes devient le libellé du poste
(``chaine_pertes.LIBELLES``) ; ce qui reste sans intitulé devient « une
donnée ». La garde ``test_cal223_contrats`` rejoue la liste des motifs.
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
    'sous_chaines_par_module': 'nombre de sous-chaînes de cellules du module',
    'bifacialite_pct': 'bifacialité du module (%)',
    'opt_modules_par_optimiseur': "nombre de modules par optimiseur",
    'opt_ac_unites_max_par_branche': "nombre maximal d'unités par branche AC",
    'opt_ac_i_max_a': 'courant AC maximal de la branche (A)',
    'electrical.cheminements': 'cheminements de câble',
    'cheminements': 'cheminements de câble',
    'section_mm2': 'section du câble (mm²)',
    'cote': 'côté du tronçon (continu ou alternatif)',
    'ib_a': "courant d'emploi (A)",
    'chute_pct': 'chute de tension (%)',
    'nb_conducteurs': 'nombre de conducteurs',
    'longueur_m': 'longueur du tronçon (m)',
    'zones.geometry.panelSlopeLenM': 'côté de table dans la pente',
    'zones.geometry.rowPitchM': 'pas entre rangées',
    'zones.geometry.tiltDeg': 'inclinaison des tables',
    'zones.geometry.kwc': 'puissance crête posée du pan',
    'zones.geometry.gcr': "taux d'occupation du sol",
    'zones.geometry.solarAccess': 'accès solaire de chaque module (ombrage)',
    'zones.geometry.solarAccess.bandes': "bandes d'accès solaire des modules",
    'zones.geometry.skyViewFactor': 'facteur de vue du ciel',
    'zones.geometry.panels.cy': 'position des panneaux',
    'plans.azimut_pvgis_deg': 'orientation du pan',
    'meteo.heure.base': 'base horaire de la série météo',
    'meteo.heure': 'heure de la série météo',
    'raccordement.cos_phi_impose': 'cos φ imposé',
    'raccordement.source_cos_phi': 'source du cos φ imposé',
    'batterie.coupures': 'coupures de courant déclarées',
    'batterie.coupures.duree_h': 'durée des coupures (h)',
    'batterie.appareils': 'appareils secourus',
    'electrique.chainage': 'câblage des chaînes',
    'roof_layout.pin': 'point GPS du site',
    'solarAccess.values': "accès solaire de chaque module (ombrage)",
    # Noms de colonnes de la série météo.
    'gi_w_m2': "irradiance du plan des modules",
    'gh_w_m2': 'irradiance horizontale',
    'gr_i_w_m2': "composante réfléchie de l'irradiance",
    't_cell_c': 'température de cellule',
    # Les noyaux de calcul.
    'core.calepinage.soleil': 'position du soleil',
    'core.calepinage.soleil.position_solaire': 'position du soleil',
    'core.calepinage.ombre_rangees': 'ombre portée des rangées',
    'core.electrique': 'calcul électrique',
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
#: Un code de tâche (jamais un mot de la langue) : CAL153, CALX146, ACAL389,
#: D-CALX 7, CALX186-187.
_CODE = r'(?:D-)?(?:ACAL|CALX|CAL)[ -]?\d+(?:\s*[-–/]\s*\d+)*'
_CODE_ENTRE_PARENTHESES = re.compile(
    r'\s*\(\s*(?:(?:calculé par|tâche|voir)\s+)?%s(?:\s*[,/]\s*%s)*\s*\)'
    % (_CODE, _CODE))
_CODE_NU = re.compile(r'(?:\s*,)?\s*\b%s\b' % _CODE)
#: Une clé technique : au moins un souligné, ou un chemin pointé dont chaque
#: segment a deux caractères (« p.ex. » n'en est pas un).
_CLE_SNAKE = r'[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+'
_CHEMIN_POINTE = (r'[A-Za-z_]\w+(?:\[[^\]]*\])?'
                  r'(?:\.[A-Za-z_]\w+(?:\[[^\]]*\])?)+')
_TECHNIQUE = re.compile(r'(?<![\w/.])(?:%s|%s)(?![\w(])' % (
    _CHEMIN_POINTE, _CLE_SNAKE))
_FICHIER = re.compile(r'(?:[\w-]+/)+[\w-]+\.py|\b\w+\.py\b')
_ENTRE_GUILLEMETS_TECH = re.compile(
    r'« ([^\s»]*[_.\[][^\s»]*)(?:: \w+)? »')
_UN_ELEMENT_PARENTHESE = r'(?:« [^»]+ »|[\w./\[\]-]+)'
_PARENTHESE_TECHNIQUE = re.compile(
    r'\s*\(\s*(?:voir )?%s(?:,\s*%s)*\s*\)'
    % (_UN_ELEMENT_PARENTHESE, _UN_ELEMENT_PARENTHESE))
_LISTE_DE_POSTES = re.compile(r'\(((?:[a-z][a-z0-9_]*)(?:, [a-z][a-z0-9_]*)*)\)')
UNE_DONNEE = 'une donnée'


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


def libelle_de_poste(cle):
    """Le libellé français d'un poste de pertes (clé de la cascade) ou ``''``."""
    from ..chaine_pertes import LIBELLES

    return LIBELLES.get(cle, '')


def _intitule_technique(chemin):
    """L'intitulé d'un chemin ou d'une clé : postes, réglages, fiche, saisie."""
    sans = _CROCHETS.sub('', chemin)
    return (_intitule_champ(chemin) or libelle_de_poste(sans)
            or _intitule_saisie(sans))


def _intitule_saisie(sans):
    """Le champ de raccordement / de fiche onduleur, sans son article."""
    from ..raccordement import INTITULES_SAISIE

    cle = sans.rpartition('.')[2]
    texte = INTITULES_SAISIE.get(cle, '')
    for article in ('le ', 'la ', "l'"):
        if texte.startswith(article):
            return texte[len(article):]
    return texte


def champ_en_clair(chemin):
    """L'intitulé d'un champ nommé par une omission, ou ``''`` s'il est inconnu."""
    return _intitule_technique(str(chemin or ''))


def _retirer_codes(texte):
    """Aucun code de tâche ne s'imprime : la référence disparaît."""
    texte = _CODE_ENTRE_PARENTHESES.sub('', texte)
    texte = _CODE_NU.sub('', texte)
    sans = re.sub(r'^\s*[—–-]\s*', '', texte)
    if sans != texte:  # « D-CALX 16 — le spectral… » → « Le spectral… »
        sans = sans[:1].upper() + sans[1:]
    return sans


def _minuscule(libelle):
    """Initiale en minuscule, sauf un sigle (« LID », « IAM »)."""
    if libelle[1:2].isupper():
        return libelle
    return libelle[:1].lower() + libelle[1:]


def _postes_en_liste(correspondance):
    """``(salissure, lid, ohmique_dc)`` → les libellés des postes."""
    cles = correspondance.group(1).split(', ')
    libelles = [libelle_de_poste(c) for c in cles]
    if not all(libelles):
        return correspondance.group(0)
    return '(%s)' % ', '.join(_minuscule(texte) for texte in libelles)


def _technique_en_prose(correspondance):
    """Un chemin ou une clé au milieu d'une phrase : son intitulé, sinon
    « une donnée » ; un nom de noyau de calcul inconnu devient « le calcul »."""
    chemin = correspondance.group(0)
    libelle = _intitule_technique(chemin)
    if libelle:
        return libelle
    return 'le calcul interne' if chemin.startswith('core.') else UNE_DONNEE


def _guillemets_techniques(correspondance):
    libelle = _intitule_technique(correspondance.group(1))
    return '« %s »' % libelle if libelle else UNE_DONNEE


def _nettoyer(texte):
    texte = re.sub(r'\(\s*\)', '', texte)
    texte = re.sub(r'[ \t]{2,}', ' ', texte)
    return re.sub(r'\s+([,.])', r'\1', texte).strip()


def motif_lisible(motif):
    """Le motif servi, rendu lisible pour celui qui lit le document.

    Rien ne change dans ce qui est déjà de la langue : le reste de la phrase,
    ses chiffres et sa ponctuation sont rendus tels quels. Sortent de la
    phrase : les codes de tâche, les noms de fichiers, les chemins pointés,
    les clés en soulignés et les index (voir le docstring du module). Un
    chemin inconnu après « Champ manquant : » devient « Une donnée manque ».
    """
    brut = str(motif) if motif is not None else ''
    texte = _retirer_codes(brut)

    def champ_manquant(correspondance):
        libelle = _intitule_champ(correspondance.group(2))
        if not libelle:
            return 'Une donnée manque'
        return '%s« %s »' % (correspondance.group(1), libelle)

    if '«' in texte:
        texte = _CHAMP_MANQUANT.sub(champ_manquant, texte)
        texte = _NON_RENSEIGNES.sub(
            lambda c: c.group(1) + _traduire_liste(
                c.group(2), remplacer_inconnu=True), texte)

        def identifiant_en_phrase(correspondance):
            chemin = correspondance.group(1)
            libelle = (_intitule_champ(chemin)
                       if _IDENTIFIANT.match(chemin) else '')
            return '« %s »' % libelle if libelle else correspondance.group(0)

        texte = _UN_CHAMP.sub(identifiant_en_phrase, texte)
    texte = _LISTE_DE_POSTES.sub(_postes_en_liste, texte)
    texte = _PARENTHESE_TECHNIQUE.sub(
        lambda c: '' if (_TECHNIQUE.search(c.group(0))
                         or _FICHIER.search(c.group(0))) else c.group(0),
        texte)
    texte = _FICHIER.sub('', texte) if '.py' in texte else texte
    texte = _ENTRE_GUILLEMETS_TECH.sub(_guillemets_techniques, texte)
    texte = _TECHNIQUE.sub(_technique_en_prose, texte)
    return texte if texte == brut else _nettoyer(texte)


def avec_motifs_lisibles(resultat):
    """Le ``resultat`` servi, chaque étape OMISE de la cascade portant, à côté
    de ``motif_omission`` (inchangé : la donnée relue par expression régulière),
    son texte lisible ``motif_lisible`` — la SEULE source des écrans (R3-19).

    Une copie : le résultat stocké n'est jamais modifié ; sans cascade, rendu
    tel quel."""
    cascade = resultat.get('cascade') if isinstance(resultat, dict) else None
    etapes = cascade.get('etapes') if isinstance(cascade, dict) else None
    if not isinstance(etapes, list):
        return resultat
    lues = [dict(e, motif_lisible=motif_lisible(e['motif_omission']))
            if isinstance(e, dict) and e.get('motif_omission') else e
            for e in etapes]
    return dict(resultat, cascade=dict(cascade, etapes=lues))
