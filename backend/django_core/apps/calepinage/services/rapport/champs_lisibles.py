"""R3-19 — les chemins internes d'un motif, imprimés en intitulés de métier.

Les motifs d'omission de la cascade finissent par « Champ manquant : « chemin
». » (``etapes.etape_omise``) ou citent « Non renseigné(s) : « chemin » ».
Ce texte est une DONNÉE servie, relue ailleurs par expression régulière
(``a_renseigner.py``, contrat ``a_renseigner``) : il ne change PAS à la
source. Seuls le texte IMPRIMÉ (rapport, diagramme) et le texte SERVI à l'écran
(``avec_motifs_lisibles``, ACAL1323) passent par ``motif_lisible``.

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
    # T4-X5-013 — la batterie de la simulation est le PRODUIT de la ligne
    # batterie du devis lié (``chaines.batterie_du_calepinage``) : sans lui,
    # la stratégie déclarée seule ne suffit pas.
    'batterie.groupes': ('produit batterie : ajoutez la batterie au devis '
                         'lié, puis relancez la simulation'),
    'hors_reseau': 'hors réseau',
    'electrique.chainage': 'câblage des chaînes',
    'roof_layout.pin': 'point GPS du site',
    # ACAL1323 — chemins encore servis bruts à l'écran (Économie, Production).
    'remplacements': 'remplacements de matériel prévus',
    'Produit.garantie_production_mois': 'garantie de production du module (mois)',
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
    poste = libelle_de_poste(sans)
    if not poste and sans.endswith('_pct'):  # « indisponibilite_pct »
        poste = libelle_de_poste(sans[:-4])
        poste = poste + ' (%)' if poste else ''
    return _intitule_champ(chemin) or poste or _intitule_saisie(sans)


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
    texte = texte if texte == brut else _nettoyer(texte)
    return _phrases_uniques(texte)


def _phrases_uniques(texte):
    """ACAL1654 — une phrase répétée (motifs concaténés) ne s'imprime qu'une
    fois ; un texte sans répétition est rendu tel quel."""
    phrases = re.split(r'(?<=[.!?])\s+', texte)
    uniques = list(dict.fromkeys(phrases))
    return texte if len(uniques) == len(phrases) else ' '.join(uniques)


#: ACAL1654 — la provenance SERVIE d'une étape, en mots (les codes que l'écran
#: ne nomme pas déjà) ; ACAL1656 réutilise la MÊME table à l'impression.
SOURCES_LISIBLES = {
    'texte': 'page publiée',
    'societe': 'réglage société',
    'document': 'document du calepinage',
    'materiel': 'matériel du calepinage',
}


def _etape_servie(etape):
    """ACAL1654 — l'étape SERVIE : motif lisible (étape omise), source en
    mots, référence sans code de tâche ni chemin ; la MÊME étape si rien ne
    change."""
    servie = dict(etape)
    if etape.get('motif_omission'):
        servie['motif_lisible'] = motif_lisible(etape['motif_omission'])
    if isinstance(etape.get('source'), str) and etape['source'] in SOURCES_LISIBLES:
        servie['source'] = SOURCES_LISIBLES[etape['source']]
    if isinstance(etape.get('reference'), str) and etape['reference']:
        servie['reference'] = motif_lisible(etape['reference'])
    return servie if servie != etape else etape


#: ACAL1323 — les motifs SERVIS à l'écran, où qu'ils soient dans le résultat.
_CLES_MOTIF_SERVI = frozenset(('motif_omission', 'motif_absence'))
#: ACAL1741 — les avertissements (liste de phrases) recopient des motifs
#: (« Projection pluriannuelle non publiée. … Non renseigné(s) : « Fiche… »).
_CLES_PHRASES_SERVIES = frozenset(('avertissements',))


def _phrases_lisibles(phrases):
    """La liste de phrases, chacune lisible ; la MÊME liste si rien ne change."""
    lues = [motif_lisible(t) if isinstance(t, str) else t for t in phrases]
    return phrases if lues == phrases else lues


def _servis_lisibles(noeud, cles=_CLES_MOTIF_SERVI):
    """``noeud`` dont chaque motif servi est rendu lisible (même objet s'il
    n'en porte aucun : rien n'est recopié pour rien)."""
    if isinstance(noeud, list):
        lus = [_servis_lisibles(v, cles) for v in noeud]
        return lus if any(a is not b for a, b in zip(lus, noeud)) else noeud
    if not isinstance(noeud, dict):
        return noeud
    lus = {c: (motif_lisible(v) if c in cles and isinstance(v, str) and v
               else _phrases_lisibles(v)
               if c in _CLES_PHRASES_SERVIES and isinstance(v, list)
               and cles is _CLES_MOTIF_SERVI
               else _servis_lisibles(v, cles)) for c, v in noeud.items()}
    return lus if any(lus[c] != noeud[c] if isinstance(noeud[c], str)
                      else lus[c] is not noeud[c] for c in noeud) else noeud


def avec_motifs_lisibles(resultat):
    """Le ``resultat`` servi à l'écran : chaque étape OMISE de la cascade porte
    ``motif_lisible`` (R3-19) et, ACAL1323, chaque ``motif_omission`` /
    ``motif_absence`` servi est lui-même en intitulés de métier (« matrice
    d'ombrage 12 mois × 24 heures », jamais « ombrage.shading12x24 »), comme
    le motif d'un champ hors registre de ``cascade.a_renseigner``.

    Une copie : le résultat STOCKÉ n'est jamais modifié — ``a_renseigner`` y
    a relu le chemin (sa ``cible.champ`` pointe toujours le champ à saisir) ;
    sans motif, rendu tel quel."""
    cascade = resultat.get('cascade') if isinstance(resultat, dict) else None
    etapes = cascade.get('etapes') if isinstance(cascade, dict) else None
    if isinstance(etapes, list):
        lues = [_etape_servie(e) if isinstance(e, dict) else e for e in etapes]
        ailleurs = _servis_lisibles(cascade.get('a_renseigner'), {'motif'})
        cascade = dict(cascade, etapes=lues, **(
            {'a_renseigner': ailleurs} if 'a_renseigner' in cascade else {}))
        resultat = dict(resultat, cascade=cascade)
    return _servis_lisibles(resultat)
