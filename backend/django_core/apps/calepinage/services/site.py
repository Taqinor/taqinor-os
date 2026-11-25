"""CAL47 — la section « imagerie & pays » des réglages société, normalisée.

LE CONSTAT
----------
Le fournisseur d'imagerie et le pays de géocodage sont FIGÉS dans le code du
site public : ``apps/web/src/lib/roofConfig.ts:31-43`` (constantes MapTiler /
Mapbox) et ``:190`` ``buildSatelliteStyle``, puis
``apps/web/src/scripts/roofPro11/mapDraw.ts:234,282`` qui passe ``&country=ma``
en dur. Conséquence mesurable : un calepinage hors Maroc géocode FAUX, et une
société ne peut choisir ni son imagerie ni ses calques. Parité marché :
l'imagerie est vendue comme une COUCHE choisie (Nearmap / EagleView).

CE QUE CE MODULE FAIT — ET NE FAIT PAS
--------------------------------------
* il NE crée AUCUN modèle et AUCUNE migration : la section ``imagerie`` de
  ``ParametresCalepinage`` (CAL45 — UNE base, sept extensions) est le seul
  support ;
* il NORMALISE et VALIDE cette section au moment de l'écriture, pour que
  ``GET /api/django/calepinage/parametres/`` rende ensuite le contrat CAL46
  (``contract_samples/site_imagerie.json``) mot pour mot : les HUIT clés
  toujours présentes, une valeur inconnue à ``null`` (ou ``[]``), jamais une
  clé absente ;
* il n'invente AUCUNE valeur par défaut. Une section vide RESTE vide, et une
  société sans réglage obtient exactement le comportement d'aujourd'hui —
  c'est la garantie d'équivalence de CAL45, et elle est testée ;
* il ne fait AUCUN appel réseau : ce fichier ne connaît que des noms de
  fournisseurs, jamais leurs URL ni leurs clés (celles-ci restent des
  variables d'environnement, côté vue).

CE QUI EST REFUSÉ, ET POURQUOI (toujours en français, en NOMMANT le champ)
--------------------------------------------------------------------------
* ``google_solar`` — GATÉ par CAL51 (et sans couverture au Maroc :
  ``apps/crm/roof_detect.py:11-12``). Le refuser ici, en le nommant, vaut mieux
  que l'accepter et le voir échouer silencieusement à l'usage ;
* ``ign_bd_ortho`` SANS ``attribution`` — l'IGN impose sa mention légale sur la
  BD ORTHO®. Une attribution ne s'invente pas : elle est SAISIE, stockée telle
  quelle, et affichée telle quelle. Sans elle, l'usage est illicite ;
* ``ign_bd_ortho`` actif avec un ``pays`` autre que ``fr`` — la BD ORTHO couvre
  le territoire français. Servir des tuiles vides à un dessinateur marocain
  n'est pas une option « permissive », c'est une carte muette ;
* une ``altitude_m`` SANS ``source_altitude`` — une altitude qu'on ne peut pas
  sourcer est une altitude qu'on ne peut pas défendre devant un client
  (règle « zéro chiffre inventé ») ;
* une clé inconnue dans la section — on ne range pas un réglage dans un tiroir
  qui n'existe pas : l'écran doit voir LAQUELLE.

La société est TOUJOURS celle passée par l'appelant (posée côté serveur) :
ce module ne lit jamais un corps de requête.
"""
from __future__ import annotations

import re

from .parametres import ReglageInvalide

import logging

logger = logging.getLogger(__name__)

#: La section des réglages que ce module porte (CAL45).
SECTION = 'imagerie'

#: Les fournisseurs d'imagerie CONNUS, et le pays qu'ils couvrent
#: (``None`` = mondial). Aucun autre n'est admis : une chaîne libre
#: produirait une carte muette découverte par le dessinateur, pas par le test.
#:
#: * ``maptiler`` / ``mapbox`` — les deux déjà câblés dans l'atelier
#:   (``apps/web/src/lib/roofConfig.ts``), comportement historique ;
#: * ``ign_bd_ortho`` — BD ORTHO® de l'IGN (WMTS), option FRANCE : donnée
#:   publique, aucune clé payante, mention légale OBLIGATOIRE.
FOURNISSEURS = {
    'maptiler': None,
    'mapbox': None,
    'ign_bd_ortho': 'fr',
}

#: Les fournisseurs qui EXIGENT une mention légale saisie.
FOURNISSEURS_AVEC_ATTRIBUTION = ('ign_bd_ortho',)

#: GATÉ par CAL51 — nommé ici pour que le refus soit explicite plutôt que de
#: tomber dans le « fournisseur inconnu » générique.
FOURNISSEURS_GATES = {
    'google_solar': (
        "Le fournisseur « google_solar » n'est pas ouvert (tâche CAL51) et "
        "n'a aucune couverture au Maroc : choisissez un fournisseur de la "
        "liste."
    ),
}

#: Les huit clés de la section, dans l'ordre du contrat CAL46
#: (``contract_samples/site_imagerie.json``). Source unique de la FORME.
CLES = (
    'pays',
    'fournisseur_imagerie',
    'fournisseurs_autorises',
    'calques_optionnels',
    'attribution',
    'altitude_m',
    'source_altitude',
    'fuseau',
)

#: Les clés qui portent une LISTE (``[]`` quand rien n'est réglé).
CLES_LISTE = ('fournisseurs_autorises', 'calques_optionnels')

_PAYS = re.compile(r'^[a-z]{2}$')
_FUSEAU = re.compile(r'^[A-Za-z][A-Za-z0-9+_-]*(/[A-Za-z0-9+_-]+)*$')
_CALQUE = re.compile(r'^[a-z][a-z0-9_-]*$')

__all__ = [
    'SECTION', 'FOURNISSEURS', 'FOURNISSEURS_GATES', 'CLES', 'CLES_LISTE',
    'normaliser_section_imagerie', 'section_vide',
    # CAL55 — altitude et fuseau SOURCÉS (jamais devinés, jamais dérivés de
    # la longitude).
    'SOURCE_PVGIS', 'SOURCE_SAISIE', 'altitude_du_site',
    'fuseau_du_site', 'decalage_utc_minutes',
    # T4-U1-003 — jamais un point par défaut anonyme.
    'CENTRES_CARTE_PAR_DEFAUT', 'SOURCE_VILLE_REFERENCE',
    'point_du_site', 'site_dit',
    # T4-U4-013 — la provenance du site portée par le document.
    'CLE_PROVENANCE_SITE', 'PROVENANCES_SITE_POSE', 'RAYON_CENTRE_ANCIEN_M',
]


def section_vide():
    """La section AVEC ses huit clés, toutes inconnues.

    C'est l'état ``exemple_section_declaree_sans_valeur`` du contrat CAL46 :
    l'appelant qui reçoit huit valeurs nulles applique le comportement
    d'aujourd'hui. À NE PAS confondre avec ``{}`` (« jamais réglé »), que
    l'endpoint rend tel quel pour garantir l'équivalence stricte.
    """
    return {cle: ([] if cle in CLES_LISTE else None) for cle in CLES}


def _fournisseur_actif(section):
    """Le fournisseur à utiliser, ou ``None`` si la société n'a rien réglé.

    ``fournisseur_imagerie`` fait foi ; à défaut, le PREMIER de la liste
    ordonnée des fournisseurs autorisés ; à défaut, ``None`` — et l'appelant
    garde le comportement actuel (MapTiler, ou Mapbox si son jeton est là).
    Aucune valeur n'est inventée ici.
    """
    section = section or {}
    choisi = section.get('fournisseur_imagerie')
    if choisi:
        return choisi
    autorises = section.get('fournisseurs_autorises') or []
    return autorises[0] if autorises else None


def _refus(message, champ):
    return ReglageInvalide(message, champ=champ)


def _cles_inconnues(section):
    return sorted(set(section) - set(CLES))


def _texte_ou_none(valeur, champ, libelle):
    """Un texte NON VIDE, ou ``None``. Une chaîne blanche vaut inconnu."""
    if valeur is None:
        return None
    if not isinstance(valeur, str):
        raise _refus(
            f"« {libelle} » doit être un texte (reçu : "
            f"{type(valeur).__name__}).", champ)
    valeur = valeur.strip()
    return valeur or None


def _liste_de_textes(valeur, champ, libelle):
    if valeur is None:
        return []
    if not isinstance(valeur, list):
        raise _refus(
            f"« {libelle} » doit être une liste (reçu : "
            f"{type(valeur).__name__}).", champ)
    propre = []
    for element in valeur:
        if not isinstance(element, str) or not element.strip():
            raise _refus(
                f"« {libelle} » ne contient que des textes non vides "
                f"(reçu : {element!r}).", champ)
        element = element.strip()
        if element not in propre:
            propre.append(element)
    return propre


def _pays(valeur):
    valeur = _texte_ou_none(valeur, 'pays', 'Pays')
    if valeur is None:
        return None
    valeur = valeur.lower()
    if not _PAYS.match(valeur):
        raise _refus(
            "« Pays » est un code à deux lettres (ISO 3166-1 alpha-2), par "
            f"exemple « ma » ou « fr » (reçu : « {valeur} »).", 'pays')
    return valeur


def _fuseau(valeur):
    valeur = _texte_ou_none(valeur, 'fuseau', 'Fuseau horaire')
    if valeur is None:
        return None
    if not _FUSEAU.match(valeur):
        raise _refus(
            "« Fuseau horaire » attend un identifiant IANA, par exemple "
            f"« Africa/Casablanca » (reçu : « {valeur} »).", 'fuseau')
    connus = _fuseaux_connus()
    # Base de fuseaux indisponible (image sans tzdata) : un doute ne rougit
    # JAMAIS — le format a déjà été contrôlé ci-dessus.
    if connus and valeur not in connus:
        raise _refus(
            f"Le fuseau horaire « {valeur} » est inconnu de la base IANA : "
            "vérifiez l'orthographe (par exemple « Africa/Casablanca »).",
            'fuseau')
    return valeur


def _fuseaux_connus():
    try:
        from zoneinfo import available_timezones

        return available_timezones()
    except Exception:       # pragma: no cover - dépend de l'image
        logger.warning("fuseaux connus : échec ignoré, comportement dégradé", exc_info=True)
        return None


def _altitude(valeur):
    if valeur is None:
        return None
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        raise _refus(
            "« Altitude (m) » doit être un nombre de mètres (reçu : "
            f"{type(valeur).__name__}).", 'altitude_m')
    # Point culminant du pays le plus haut < 9 000 m ; la fosse la plus basse
    # habitée > -500 m. Hors de cette plage, c'est une saisie, pas un site.
    if not -500 <= float(valeur) <= 9000:
        raise _refus(
            "« Altitude (m) » doit rester entre -500 et 9000 mètres "
            f"(reçu : {valeur}).", 'altitude_m')
    return float(valeur)


def _fournisseurs_autorises(valeur):
    autorises = _liste_de_textes(valeur, 'fournisseurs_autorises',
                                 "Fournisseurs d'imagerie autorisés")
    for nom in autorises:
        _controler_fournisseur(nom, 'fournisseurs_autorises')
    return autorises


def _controler_fournisseur(nom, champ):
    if nom in FOURNISSEURS_GATES:
        raise _refus(FOURNISSEURS_GATES[nom], champ)
    if nom not in FOURNISSEURS:
        raise _refus(
            f"Fournisseur d'imagerie inconnu : « {nom} ». Fournisseurs "
            f"admis : {', '.join(sorted(FOURNISSEURS))}.", champ)


def normaliser_section_imagerie(valeur):
    """La section ``imagerie`` VALIDÉE et complétée à ses huit clés.

    Args:
        valeur: la section telle que l'appelant l'envoie.

    Returns:
        ``{}`` si la section est vide — ÉQUIVALENCE : une société sans réglage
        se comporte EXACTEMENT comme aujourd'hui, aucun défaut n'est inventé.
        Sinon, les huit clés du contrat CAL46, toujours toutes présentes.

    Raises:
        ReglageInvalide: message FRANÇAIS nommant le champ fautif.
    """
    if valeur is None:
        return {}
    if not isinstance(valeur, dict):
        raise _refus(
            "La section « imagerie » doit être un objet (reçu : "
            f"{type(valeur).__name__}).", SECTION)
    if not valeur:
        return {}

    inconnues = _cles_inconnues(valeur)
    if inconnues:
        raise _refus(
            f"Réglage d'imagerie inconnu : « {', '.join(inconnues)} ». "
            f"Réglages admis : {', '.join(CLES)}.", inconnues[0])

    section = section_vide()
    section['pays'] = _pays(valeur.get('pays'))
    section['fournisseurs_autorises'] = _fournisseurs_autorises(
        valeur.get('fournisseurs_autorises'))
    section['calques_optionnels'] = _calques(valeur.get('calques_optionnels'))
    section['attribution'] = _texte_ou_none(
        valeur.get('attribution'), 'attribution', 'Attribution')
    section['altitude_m'] = _altitude(valeur.get('altitude_m'))
    section['source_altitude'] = _texte_ou_none(
        valeur.get('source_altitude'), 'source_altitude',
        "Source de l'altitude")
    section['fuseau'] = _fuseau(valeur.get('fuseau'))

    choisi = _texte_ou_none(valeur.get('fournisseur_imagerie'),
                            'fournisseur_imagerie', "Fournisseur d'imagerie")
    if choisi is not None:
        _controler_fournisseur(choisi, 'fournisseur_imagerie')
        if (section['fournisseurs_autorises']
                and choisi not in section['fournisseurs_autorises']):
            raise _refus(
                f"Le fournisseur « {choisi} » ne figure pas dans les "
                "fournisseurs autorisés de la société : ajoutez-le à la "
                "liste ou choisissez-en un autre.", 'fournisseur_imagerie')
    section['fournisseur_imagerie'] = choisi

    _controler_coherence(section)
    return section


def _calques(valeur):
    calques = _liste_de_textes(valeur, 'calques_optionnels',
                               'Calques optionnels')
    for calque in calques:
        if not _CALQUE.match(calque):
            raise _refus(
                "Un calque optionnel s'écrit en minuscules sans espace "
                f"(reçu : « {calque} »).", 'calques_optionnels')
    return calques


def _controler_coherence(section):
    """Les refus qui portent sur PLUSIEURS champs à la fois."""
    if section['altitude_m'] is not None and not section['source_altitude']:
        raise _refus(
            "Une altitude saisie doit dire d'où elle vient : renseignez "
            "« Source de l'altitude » (relevé GPS, plan topographique…).",
            'source_altitude')

    actif = _fournisseur_actif(section)
    if actif is None:
        return
    if actif in FOURNISSEURS_AVEC_ATTRIBUTION and not section['attribution']:
        raise _refus(
            f"Le fournisseur « {actif} » impose une mention légale : "
            "renseignez « Attribution » (elle est affichée telle quelle, "
            "jamais reconstruite).", 'attribution')
    pays_couvert = FOURNISSEURS.get(actif)
    if (pays_couvert and section['pays']
            and section['pays'] != pays_couvert):
        raise _refus(
            f"Le fournisseur « {actif} » ne couvre que le pays "
            f"« {pays_couvert} » : il ne peut pas servir un site en "
            f"« {section['pays']} ».", 'fournisseur_imagerie')


# ── CAL55 — L'ALTITUDE ET LE FUSEAU DU SITE, SOURCÉS, JAMAIS DEVINÉS ───────
#
# L'altitude change l'irradiance et le fuseau décale toute la course du
# soleil ; aucun des deux n'existait dans l'atelier (les seules « élévations »
# y sont SOLAIRES). Les deux règles fondateur de la tâche :
#
# * l'ALTITUDE vient de la réponse PVGIS DÉJÀ appelée
#   (``inputs.location.elevation``) et est stockée AVEC SA SOURCE ; PVGIS muet
#   ⇒ champ VIDE et mention « non renseignée », jamais un nombre de repli ;
# * le FUSEAU vient de la base de fuseaux (``zoneinfo``) ou est SAISI —
#   **JAMAIS dérivé de la longitude**. Un fuseau est une décision POLITIQUE,
#   pas une coordonnée : le Maroc a vécu à UTC+1 toute l'année de 2018 au
#   19/09/2026 (une dérivation par la longitude, -7,6° ⇒ UTC+0, se serait
#   alors trompée d'une heure pleine sur toute la production horaire), puis il
#   est repassé à UTC+0 le 20/09/2026 — décret n° 2.26.530 relatif à l'heure
#   légale — sans qu'aucune longitude ne bouge. Seule la base de fuseaux suit
#   ces décisions ; le calcul ci-dessous (``decalage_utc_minutes``) l'interroge
#   à la DATE demandée, il ne fige aucun décalage.
#
# Dans les deux cas, une valeur SAISIE par la société l'emporte sur la valeur
# automatique : c'est elle qui connaît son site.

#: La source publiée quand l'altitude vient de la réponse PVGIS.
SOURCE_PVGIS = 'PVGIS'

#: La source publiée quand la société a saisi la valeur elle-même.
SOURCE_SAISIE = 'saisie'

MENTION_ALTITUDE_INCONNUE = (
    "Altitude non renseignée : PVGIS ne l'a pas fournie et personne ne l'a "
    "saisie."
)
MENTION_FUSEAU_INCONNU = (
    "Fuseau horaire non renseigné : il se SAISIT (identifiant IANA, par "
    "exemple « Africa/Casablanca ») — il ne se déduit JAMAIS de la longitude."
)


def _altitude_pvgis(charge):
    """L'altitude que PVGIS publie avec sa réponse, ou ``None``.

    PVGIS rend ``inputs.location.elevation`` (mètres). Une réponse sans
    élévation, ou avec une élévation illisible, rend ``None`` — et l'appelant
    ne publiera AUCUNE altitude.
    """
    entrees = (charge or {}).get('inputs') if isinstance(charge, dict) else None
    lieu = (entrees or {}).get('location') if isinstance(entrees, dict) else None
    valeur = (lieu or {}).get('elevation') if isinstance(lieu, dict) else None
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    return float(valeur)


def altitude_du_site(section, *, charge_pvgis=None):
    """``{'altitude_m', 'source', 'mention'}`` — la valeur SAISIE l'emporte.

    Args:
        section: la section ``imagerie`` des réglages société (CAL47), qui
            porte ``altitude_m`` et ``source_altitude`` quand la société les
            a saisis (une altitude sans source y est déjà refusée).
        charge_pvgis: la réponse PVGIS déjà obtenue, s'il y en a une.

    Returns:
        ``altitude_m`` à ``None`` quand personne ne la connaît — jamais une
        valeur de repli — et ``mention`` qui le DIT en français.
    """
    section = section or {}
    saisie = section.get('altitude_m')
    if isinstance(saisie, (int, float)) and not isinstance(saisie, bool):
        return {
            'altitude_m': float(saisie),
            # La source saisie est republiée TELLE QUELLE (relevé GPS, plan
            # topographique…) : c'est elle qui rend le chiffre défendable.
            'source': section.get('source_altitude') or SOURCE_SAISIE,
            'mention': '',
        }
    depuis_pvgis = _altitude_pvgis(charge_pvgis)
    if depuis_pvgis is None:
        return {'altitude_m': None, 'source': None,
                'mention': MENTION_ALTITUDE_INCONNUE}
    return {'altitude_m': depuis_pvgis, 'source': SOURCE_PVGIS, 'mention': ''}


#: ACAL129 — la PROVENANCE du fuseau effectif, publiée
#: (``meteo.heure.provenance_fuseau``, ``site_effectif.source``).
PROVENANCE_IMAGERIE = 'imagerie'
PROVENANCE_PROFIL_SOCIETE = 'profil_societe'
MENTION_FUSEAU_PROFIL = (
    'fuseau repris du profil société (Paramètres › Société)')


def _fuseau_du_profil(company):
    """ACAL129 — le fuseau SAISI au profil de la société
    (``CompanyProfile.fuseau_horaire``), ou ``None`` (pas de société, pas de
    profil, champ vide). Lecture fonction-locale d'une app de fondation."""
    if company is None or getattr(company, 'pk', None) is None:
        return None
    from apps.parametres.models_company import CompanyProfile

    fuseau = (CompanyProfile.objects.filter(company=company)
              .values_list('fuseau_horaire', flat=True).first())
    fuseau = str(fuseau or '').strip()
    return fuseau or None


def fuseau_du_site(section, *, company=None):
    """``{'fuseau', 'source', 'mention', 'provenance'}`` — SAISI, jamais
    déduit.

    Le fuseau est validé contre la base IANA (``zoneinfo``) à l'écriture
    (``normaliser_section_imagerie``) ; ici on le SERT, ou on dit qu'il
    manque. Aucune coordonnée n'entre dans cette fonction : c'est la garantie
    structurelle qu'aucun fuseau ne peut être dérivé d'une longitude.

    ACAL129 — préséance : le fuseau des réglages d'IMAGERIE du calepinage,
    sinon (``company`` fournie) celui SAISI au profil de la société — repli
    DÉCLARÉ, avec sa provenance et sa mention. Jamais la longitude.
    """
    fuseau = (section or {}).get('fuseau')
    if fuseau:
        return {'fuseau': fuseau, 'source': 'base IANA (zoneinfo)',
                'mention': '', 'provenance': PROVENANCE_IMAGERIE}
    profil = _fuseau_du_profil(company)
    if profil:
        return {'fuseau': profil, 'source': 'base IANA (zoneinfo)',
                'mention': MENTION_FUSEAU_PROFIL,
                'provenance': PROVENANCE_PROFIL_SOCIETE}
    return {'fuseau': None, 'source': None,
            'mention': MENTION_FUSEAU_INCONNU, 'provenance': None}


def decalage_utc_minutes(fuseau, moment):
    """Le décalage UTC d'un fuseau À UN INSTANT, lu dans ``zoneinfo``.

    C'est la SEULE façon correcte d'obtenir un décalage : il dépend de la
    date (heure d'été), et une formule sur la longitude se tromperait d'une
    heure pleine au Maroc. Renvoie ``None`` si le fuseau est inconnu de la
    base installée — un doute ne produit jamais un chiffre.
    """
    if not fuseau or moment is None:
        return None
    try:
        from zoneinfo import ZoneInfo

        decalage = moment.replace(tzinfo=ZoneInfo(fuseau)).utcoffset()
    except Exception:       # pragma: no cover - dépend de la base installée
        logger.warning("decalage utc minutes : échec ignoré, comportement dégradé", exc_info=True)
        return None
    if decalage is None:
        return None
    return int(decalage.total_seconds() // 60)


# ═══════════════════════════════════════════════════════════════════════════
# T4-U1-003 — JAMAIS UN POINT PAR DÉFAUT ANONYME
# ═══════════════════════════════════════════════════════════════════════════
#
# Un toit créé « par ses dimensions » sur une carte jamais localisée est posé
# au CENTRE PAR DÉFAUT de la carte (outil de dessin : ``MOROCCO_CENTER`` de
# ``apps/web/src/scripts/roofPro11/constants.ts`` ; ``DEFAULT_CENTER`` de
# ``frontend/src/components/MapView.jsx``), et ce centre arrivait comme
# épingle : la simulation calculait alors au milieu du Maroc (737 m
# d'altitude), sans que rien ne le nomme. Ces points ne sont pas un site.

#: Les centres de carte par défaut (lat, lon) des outils de dessin.
CENTRES_CARTE_PAR_DEFAUT = ((31.79, -7.09), (31.7917, -7.0926))

#: Tolérance (degrés, ≈ 0,1 m) : seul le centre EXACT (au bruit flottant près)
#: est écarté, jamais un point posé à la main à côté.
TOLERANCE_CENTRE_DEG = 1e-6

#: La provenance d'un site résolu par la ville du lead (``site.source``).
SOURCE_VILLE_REFERENCE = 'ville_reference'


def _point_par_defaut(lat, lon):
    """Vrai quand ``(lat, lon)`` est un centre de carte par défaut."""
    if lat is None or lon is None:
        return False
    return any(abs(lat - c_lat) <= TOLERANCE_CENTRE_DEG
               and abs(lon - c_lon) <= TOLERANCE_CENTRE_DEG
               for c_lat, c_lon in CENTRES_CARTE_PAR_DEFAUT)


def _site_de_reference(ville, *, adresse=False):
    """Le site d'un calepinage SANS épingle : la ville de référence du devis.

    Réutilise ``pvgis_profils.ancre_de_reference`` — la résolution que suit
    le productible du devis pour ce lead (orthographes courantes comprises,
    sinon ancre la plus proche du gazetier). Rend ``{lat, lon, source,
    ville_reference, libelle}``, ou ``None`` quand aucune ville de référence
    ne se résout (la simulation est alors refusée en le disant).
    ``adresse=True`` (relecture m1) : une ADRESSE libre ne se résout que si
    elle nomme exactement une ville (``ancre_de_reference_adresse``).
    """
    from apps.parametres.pvgis_profils import (
        ancre_de_reference,
        ancre_de_reference_adresse,
    )
    from apps.parametres.villes_resolution import nom_canonique

    reference = (ancre_de_reference_adresse if adresse
                 else ancre_de_reference)(ville)
    if reference is None:
        return None
    nom = nom_canonique(reference['cle'])
    libelle = ('%s (ville de référence)' % nom
               if reference['proche_km'] is None
               else '%s (ville de référence la plus proche)' % nom)
    return {
        'lat': float(reference['lat']),
        'lon': float(reference['lon']),
        'source': SOURCE_VILLE_REFERENCE,
        'ville_reference': nom,
        'libelle': libelle,
    }


# ── T4-U4-013 — LA PROVENANCE DE L'ÉPINGLE, PORTÉE PAR LE DOCUMENT ─────────
#
# L'atelier écrit ``pin`` = centroïde du pan tracé, que le site ait été
# localisé ou non : un toit tracé par clics à l'échelle du pays partait avec
# une épingle à quelques kilomètres du centre par défaut (pas EXACTEMENT
# dessus), et la simulation calculait au milieu du Maroc (« Coordonnées — »,
# 737 m). Le document dit désormais D'OÙ vient le site, clé racine
# ``siteLocalise`` (contrat ``roof_layout_v2.schema.json``) :
#
# * ``'lead'`` (GPS / repère de la fiche), ``'adresse'`` (recherche d'adresse,
#   « Localiser », coordonnées collées), ``'epingle'`` (épingle déplacée à la
#   main), ``'trace'`` (toit tracé à la main sur la carte zoomée au niveau du
#   toit) : l'épingle est POSÉE ;
# * ``null`` : l'atelier sait que personne n'a localisé le site — l'épingle
#   n'est que le centre du tracé, elle n'est PAS un site ;
# * clé ABSENTE (document écrit avant ce changement, ou par le serveur —
#   reprise du site public, webhook) : RÈGLE SANS MIGRATION — l'épingle compte
#   comme posée si elle est le repère du lead, ou si elle est à plus de
#   ``RAYON_CENTRE_ANCIEN_M`` de tout centre de carte par défaut ; à moins de
#   2 km d'un centre par défaut (zone montagneuse sans client connu, là où
#   tombe un tracé fait sans localiser), elle ne l'est pas.

#: La clé racine du document qui porte la provenance du site.
CLE_PROVENANCE_SITE = 'siteLocalise'

#: Les provenances qui font d'une épingle un site posé.
PROVENANCES_SITE_POSE = ('lead', 'adresse', 'epingle', 'trace')

#: Documents sans provenance : rayon (m) autour d'un centre par défaut dans
#: lequel une épingle n'est pas un site (sauf si c'est le repère du lead).
RAYON_CENTRE_ANCIEN_M = 2000.0


def _distance_au_centre_m(lat, lon):
    """Distance (m, approximation locale) au centre par défaut le plus proche."""
    import math

    return min(
        math.hypot((lat - c_lat) * 111320.0,
                   (lon - c_lon) * 111320.0 * math.cos(math.radians(c_lat)))
        for c_lat, c_lon in CENTRES_CARTE_PAR_DEFAUT)


def _lat_lon(epingle):
    from .valeurs import nombre

    if not isinstance(epingle, dict):
        return None, None
    return (nombre(epingle.get('lat')),
            nombre(epingle.get('lng') if epingle.get('lng') is not None
                   else epingle.get('lon')))


def _epingle_du_document_posee(document, lire_geo_une_fois):
    """Vrai quand l'épingle du document est un SITE (règles ci-dessus)."""
    lat, lon = _lat_lon(document.get('pin'))
    if lat is None or lon is None or _point_par_defaut(lat, lon):
        return False
    if CLE_PROVENANCE_SITE in document:
        return document.get(CLE_PROVENANCE_SITE) in PROVENANCES_SITE_POSE
    if _distance_au_centre_m(lat, lon) > RAYON_CENTRE_ANCIEN_M:
        return True
    lat_lead, lon_lead = _lat_lon(lire_geo_une_fois().get('pin'))
    return (lat_lead is not None and lon_lead is not None
            and abs(lat - lat_lead) <= TOLERANCE_CENTRE_DEG
            and abs(lon - lon_lead) <= TOLERANCE_CENTRE_DEG)


def _epingle_posee(document, lire_geo):
    """``(lat, lon, geo)`` — L'épingle du site, au sens unique « site posé ».

    Lue par la simulation ET par ``soleil-legal`` (une seule définition, via
    :func:`point_du_site`) : l'épingle du document quand elle est un site
    (:func:`_epingle_du_document_posee` — provenance ``siteLocalise``, règle
    sans migration pour les documents qui ne la portent pas, jamais un centre
    de carte par défaut) ; à défaut, celle du lead (``lire_geo()`` :
    ``selectors.contexte_geographique``, appelé au plus une fois, rendu dans
    ``geo``). ``(None, None, geo)`` quand aucune épingle n'est posée.
    """
    lu = {}

    def lire_geo_une_fois():
        if 'geo' not in lu:
            lu['geo'] = lire_geo() or {}
        return lu['geo']

    document = document if isinstance(document, dict) else {}
    if _epingle_du_document_posee(document, lire_geo_une_fois):
        lat, lon = _lat_lon(document.get('pin'))
        return lat, lon, lu.get('geo')
    lat, lon = _lat_lon(lire_geo_une_fois().get('pin'))
    return lat, lon, lu['geo']


def _reference_du_contexte(geo):
    """La ville de référence de la ville du lead, sinon de l'adresse (lead ou
    client) quand elle nomme UNE SEULE ville connue — jamais une ville
    devinée (relecture m1 : « Route d'El Jadida, Casablanca » ne se résout
    pas)."""
    for texte, adresse in ((geo.get('ville'), False),
                           (geo.get('adresse'), True)):
        if texte:
            reference = _site_de_reference(texte, adresse=adresse)
            if reference is not None:
                return reference
    return None


def point_du_site(document, lire_geo):
    """``(lat, lon, reference)`` du site simulé — T4-U1-003, T4-U4-013.

    L'épingle posée (:func:`_epingle_posee`) ; sans elle, la ville de
    référence de la ville du lead, sinon de l'adresse du lead ou du client
    (``reference`` = ``{source, ville_reference, libelle}``), sinon
    ``(None, None, None)`` — et l'appelant refuse en disant quoi faire.
    """
    lat, lon, geo = _epingle_posee(document, lire_geo)
    if lat is not None and lon is not None:
        return lat, lon, None
    reference = _reference_du_contexte(geo if geo is not None
                                       else lire_geo() or {})
    if reference is None:
        return lat, lon, None
    return reference['lat'], reference['lon'], {
        cle: reference[cle] for cle in ('source', 'ville_reference', 'libelle')}


#: Ce que le bandeau nomme quand le calcul prendrait le repère GPS du lead.
LIBELLE_REPERE_LEAD = 'la position GPS de la fiche'


def site_de_repli(geo):
    """Relecture M1 — ce que le calcul fera quand le document n'a PAS de site
    posé, nommé pour le bandeau « Site non localisé » : le libellé de la ville
    de référence (``« Casablanca (ville de référence) »``),
    :data:`LIBELLE_REPERE_LEAD` quand le lead porte un repère, ou ``None``
    quand le calcul serait refusé. MÊME résolution que :func:`point_du_site`
    (appelée sur un document sans épingle) — l'écran ne la redérive jamais."""
    point = point_de_repli(geo)
    return point['libelle'] if point else None


def point_de_repli(geo):
    """T4-X2-005 — le POINT de :func:`site_de_repli` : ``{lat, lon, libelle}``
    (le libellé du bandeau), ou ``None`` quand le calcul serait refusé. L'atelier
    y cale ses calculs solaires (pas entre rangées…) tant que le site n'est pas
    localisé : le même lieu que la simulation, jamais l'épingle du centre du pays."""
    lat, lon, reference = point_du_site({}, lambda: geo or {})
    if lat is None or lon is None:
        return None
    libelle = reference['libelle'] if reference is not None else LIBELLE_REPERE_LEAD
    return {'lat': lat, 'lon': lon, 'libelle': libelle}


def site_dit(meteo, site):
    """Le bloc ``meteo`` publié : tel quel, sauf quand le site vient d'une
    ville de référence — ``meteo.site`` dit alors sa provenance, son nom, son
    libellé et le point demandé."""
    if not site.get('source'):
        return meteo
    return dict(meteo, site={cle: site.get(cle) for cle in (
        'source', 'ville_reference', 'libelle', 'lat', 'lon')})
