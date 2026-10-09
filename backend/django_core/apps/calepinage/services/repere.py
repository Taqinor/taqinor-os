"""ACAL191 (C-ACAL-003, D-ACAL-13) — le GPS du lead corrigé APRÈS le tracé.

Un calepinage porte son épingle ``roof_layout.pin`` (A). Le lead, lui, porte
LE repère toit (``crm.selectors.repere_toit``, lu via
``selectors.contexte_geographique`` — B). Quand l'équipe corrige le GPS du
lead après le tracé, A et B divergent : ce module le MESURE (lecture pure,
:func:`etat_derive`) et offre les deux seuls gestes versionnés :

* :func:`recentrer_sur_lead` — TOUTE la géométrie du document est translatée
  de A vers B par projection locale (plan tangent autour de A, puis retour
  autour de B, ``core.calepinage.geo`` — la projection SURVIVANTE de
  C-ACAL-144, jamais une quatrième). Jamais de Δlat/Δlng bruts : la longueur
  d'un degré de longitude dépend de la latitude (≈ 2 % d'écart d'échelle sur
  240 km), un pan translaté « en degrés » change de surface.
* :func:`garder_repere` — la dérive est ACQUITTÉE (``repereAcquitte = B``) :
  plus de bannière tant que le lead ne bouge pas.

Les deux écrivent par ``services.layout.enregistrer_layout`` (seul écrivain :
version, journal, verrou). Une LECTURE ne translate jamais rien.
"""
from __future__ import annotations

import copy
import math

from core.calepinage.geo import deprojeteur_local, projeteur_local

from .valeurs import nombre

#: D-ACAL-13 — au-delà de cette distance (mètres) entre l'épingle du document
#: et le repère du lead, la dérive est signalée. Constante NOMMÉE, pas un
#: réglage société (contrat ``calepinage_design_context.json`` : ``seuil_m``).
SEUIL_DERIVE_REPERE_M = 100

#: Deux repères à moins de ce delta (degrés, ≈ 1 cm) sont le MÊME repère.
_TOLERANCE_REPERE_DEG = 1e-7

ETAT_AUCUNE = 'aucune'
ETAT_A_DECIDER = 'a_decider'
ETAT_AUTOMATIQUE = 'automatique'

LIBELLE_RECENTRAGE = 'Recentré sur le GPS du lead'
LIBELLE_REPERE_GARDE = 'Repère gardé (GPS du lead acquitté)'

#: Source du repère côté contrat (``repere_lead.source``) depuis la source de
#: ``selectors.contexte_geographique``.
_SOURCE_CONTRAT = {'lead_gps': 'gps', 'lead_roof_point': 'roof_point'}

#: LES coordonnées géographiques du document ``roof_layout`` v2, chemin →
#: ``(forme, ordre)``. Le test ``test_acal_derive_repere`` parcourt
#: ``contract_samples/roof_layout_v2.schema.json`` : toute coordonnée du
#: schéma doit figurer ICI ou dans :data:`COORDONNEES_EXEMPTEES`.
#:
#: Formes : ``point`` (objet ``{lat, lng}``), ``centre`` (objet
#: ``{centerLng, centerLat}``), ``couple`` (un ``[a, b]``), ``couples`` (liste
#: de ``[a, b]``). Ordre : ``lng_lat`` partout (``LngLat`` de l'atelier), SAUF
#: ``outline`` racine que ``serializeLayout`` écrit en ``[lat, lng]``.
#: ``buildings[]`` ne porte aucune coordonnée (métadonnées de hauteur) : rien
#: à translater, l'empreinte d'un bâtiment est son pan.
CHEMINS_TRANSLATES = {
    'pin': ('point', 'lng_lat'),
    'outline': ('couples', 'lat_lng'),
    'zones[].vertices': ('couples', 'lng_lat'),
    'zones[].obstacles[]': ('centre', 'lng_lat'),
    'zones[].obstacles[].contour': ('couples', 'lng_lat'),
    'zones[].geometry.origin': ('couple', 'lng_lat'),
    'environment[]': ('centre', 'lng_lat'),
    'environment[].footprint': ('couples', 'lng_lat'),
    'exclusionZones[].vertices': ('couples', 'lng_lat'),
    'exclusionZones[].axe': ('couples', 'lng_lat'),
    'measurements[].points': ('couples', 'lng_lat'),
    'poseSurfaces[].vertices': ('couples', 'lng_lat'),
    'underlay.calage.ancre': ('couples', 'lng_lat'),
    'electrical.equipements[]': ('point', 'lng_lat'),
    'electrical.cheminements[].points[]': ('point', 'lng_lat'),
    'shadeObstructions[].contour': ('couples', 'lng_lat'),
    'shadeObstructions[].centre': ('couple', 'lng_lat'),
    # ACAL352 — la pointe d'ombre (ACAL27) suit sa base, même forme/ordre.
    'shadeObstructions[].bout': ('couple', 'lng_lat'),
    'parcelle.vertices': ('couples', 'lng_lat'),
}

#: Couples / points du schéma qui NE SONT PAS des coordonnées du bâtiment.
COORDONNEES_EXEMPTEES = {
    'repereAcquitte': "le repère du LEAD acquitté — pas une géométrie du "
                      "bâtiment ; il ne suit pas le document",
    'underlay.calage.pointsImage': "pixels de l'image du plan importé, pas "
                                   "des degrés",
}


class RepereRefuse(ValueError):
    """Refus métier d'un geste de repère — message français, champ nommé."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


# ── Lecture ───────────────────────────────────────────────────────────────

def _point(valeur):
    """``{lat, lng}`` lisible, ou ``None``."""
    if not isinstance(valeur, dict):
        return None
    lat, lng = nombre(valeur.get('lat')), nombre(valeur.get('lng'))
    if lat is None or lng is None:
        return None
    return {'lat': lat, 'lng': lng}


def repere_du_lead(geo):
    """``{lat, lng, source}`` du repère toit du lead, ou ``None``.

    ``geo`` = ``selectors.contexte_geographique(calepinage)`` (lu une fois
    par l'appelant) ; ``source`` ∈ ``{'gps', 'roof_point'}``.
    """
    point = _point((geo or {}).get('pin'))
    if point is None:
        return None
    return dict(point, source=_SOURCE_CONTRAT.get((geo or {}).get('source')))


def distance_m(a, b):
    """Distance (m) entre deux ``{lat, lng}`` — projection locale autour de A."""
    projeter = projeteur_local((a['lng'], a['lat']))
    x, y = projeter((b['lng'], b['lat']))
    return math.hypot(x, y)


def _meme_repere(a, b):
    a, b = _point(a), _point(b)
    if a is None or b is None:
        return False
    return (abs(a['lat'] - b['lat']) <= _TOLERANCE_REPERE_DEG
            and abs(a['lng'] - b['lng']) <= _TOLERANCE_REPERE_DEG)


def etat_derive(roof_layout, repere_lead, *, devis_statut=None):
    """``{repere_lead, ecart_m, derive}`` — LECTURE PURE (rien n'est écrit).

    * ``ecart_m`` : distance entre ``roof_layout.pin`` et le repère du lead,
      ``None`` sans l'un des deux ;
    * ``derive.etat`` : ``'aucune'`` sous le seuil, ou quand ce repère a déjà
      été acquitté (``repereAcquitte``) ; sinon ``'automatique'`` si
      l'épingle suit le lead (``pinSource == 'lead'``, D-QJR5-15) et
      ``'a_decider'`` si elle a été posée à la main ou que sa provenance est
      inconnue. Un devis lié déjà ENVOYÉ (statut ≠ brouillon) n'est JAMAIS
      recentré d'office : ``'automatique'`` y devient ``'a_decider'``.
    """
    derive = {'etat': ETAT_AUCUNE, 'seuil_m': SEUIL_DERIVE_REPERE_M}
    document = roof_layout if isinstance(roof_layout, dict) else {}
    epingle = _point(document.get('pin'))
    if epingle is None or repere_lead is None:
        return {'repere_lead': repere_lead, 'ecart_m': None, 'derive': derive}
    ecart = distance_m(epingle, repere_lead)
    resultat = {'repere_lead': repere_lead, 'ecart_m': round(ecart, 1),
                'derive': derive}
    if ecart <= SEUIL_DERIVE_REPERE_M:
        return resultat
    if _meme_repere(document.get('repereAcquitte'), repere_lead):
        return resultat
    automatique = (document.get('pinSource') == 'lead'
                   and devis_statut in (None, '', 'brouillon'))
    derive['etat'] = ETAT_AUTOMATIQUE if automatique else ETAT_A_DECIDER
    return resultat


def _libelle_distance(metres):
    """« ≈ 780 m » / « ≈ 2,4 km » / « ≈ 240 km »."""
    if metres < 1000:
        return f'≈ {int(round(metres))} m'
    km = metres / 1000.0
    if km < 10:
        return f'≈ {km:.1f} km'.replace('.', ',')
    return f'≈ {int(round(km))} km'


def avertissement_derive(geometrie):
    """La phrase de la bannière, ou ``None`` quand rien n'est à signaler."""
    derive = (geometrie or {}).get('derive') or {}
    ecart = (geometrie or {}).get('ecart_m')
    if derive.get('etat') in (None, ETAT_AUCUNE) or ecart is None:
        return None
    return ('Le GPS du lead a été corrigé depuis le tracé '
            f'({_libelle_distance(ecart)}).')


# ── Translation (pure) ────────────────────────────────────────────────────

def _segments(chemin):
    return chemin.split('.')


def _porteurs(noeud, segments):
    """Les nœuds désignés par ``segments`` (``'a[]'`` parcourt une liste)."""
    if not segments:
        yield noeud
        return
    if not isinstance(noeud, dict):
        return
    tete, reste = segments[0], segments[1:]
    if tete.endswith('[]'):
        liste = noeud.get(tete[:-2])
        if isinstance(liste, list):
            for element in liste:
                yield from _porteurs(element, reste)
        return
    if tete in noeud:
        yield from _porteurs(noeud[tete], reste)


def _translater_couple(couple, ordre, deplacer):
    if not isinstance(couple, (list, tuple)) or len(couple) < 2:
        return couple
    a, b = nombre(couple[0]), nombre(couple[1])
    if a is None or b is None:
        return couple
    lng, lat = (a, b) if ordre == 'lng_lat' else (b, a)
    lng2, lat2 = deplacer(lng, lat)
    nouveau = [lng2, lat2] if ordre == 'lng_lat' else [lat2, lng2]
    return nouveau + list(couple[2:])


def _translater_en_place(document, chemin, forme, ordre, deplacer):
    segments = _segments(chemin)
    parent_segments, feuille = segments[:-1], segments[-1]
    if forme in ('point', 'centre'):
        # Le chemin désigne l'OBJET qui porte les deux clés.
        cle_lng, cle_lat = (('lng', 'lat') if forme == 'point'
                            else ('centerLng', 'centerLat'))
        for objet in _porteurs(document, segments):
            if not isinstance(objet, dict):
                continue
            lng, lat = nombre(objet.get(cle_lng)), nombre(objet.get(cle_lat))
            if lng is None or lat is None:
                continue
            objet[cle_lng], objet[cle_lat] = deplacer(lng, lat)
        return
    for parent in _porteurs(document, parent_segments):
        if not isinstance(parent, dict) or feuille not in parent:
            continue
        valeur = parent[feuille]
        if forme == 'couple':
            parent[feuille] = _translater_couple(valeur, ordre, deplacer)
        elif isinstance(valeur, list):
            parent[feuille] = [_translater_couple(c, ordre, deplacer)
                               for c in valeur]


def _translater_document(document, ancien, nouveau):
    """Copie de ``document`` dont CHAQUE coordonnée passe de A à B.

    Chaque point est projeté en mètres autour de ``ancien`` (A) puis
    reconverti autour de ``nouveau`` (B) : les formes métriques (longueurs,
    surfaces, azimuts) sont conservées. ``pin`` devient exactement B.
    Fonction PURE.
    """
    copie = copy.deepcopy(document) if isinstance(document, dict) else {}
    projeter = projeteur_local((ancien['lng'], ancien['lat']))
    deprojeter = deprojeteur_local((nouveau['lng'], nouveau['lat']))

    def deplacer(lng, lat):
        return deprojeter(projeter((lng, lat)))

    for chemin, (forme, ordre) in CHEMINS_TRANSLATES.items():
        _translater_en_place(copie, chemin, forme, ordre, deplacer)
    return copie


# ── Gestes (écriture versionnée) ──────────────────────────────────────────

def _repere_et_epingle(calepinage):
    from .. import selectors as cal_selectors

    repere = repere_du_lead(cal_selectors.contexte_geographique(calepinage))
    if repere is None:
        raise RepereRefuse(
            "Le lead n'a aucun repère GPS ni épingle : rien vers quoi "
            "recentrer.", champ='repere_lead')
    document = getattr(calepinage, 'roof_layout', None)
    epingle = (_point(document.get('pin')) if isinstance(document, dict)
               else None)
    return repere, document, epingle


def recentrer_sur_lead(calepinage, *, user=None, base_empreinte=None):
    """Translate TOUT le document sur le repère du lead — nouvelle version.

    Raises:
        RepereRefuse: lead sans repère, document sans épingle.
        LayoutRefuse / DocumentModifie / VerrouilleRefuse: ceux de
            ``enregistrer_layout`` (verrou respecté, 409 nommé).
    """
    from .layout import enregistrer_layout

    repere, document, epingle = _repere_et_epingle(calepinage)
    if epingle is None:
        raise RepereRefuse(
            "La conception n'a pas encore d'épingle : rien à recentrer.",
            champ='pin')
    nouveau = _translater_document(document, epingle, repere)
    nouveau['pin'] = {'lat': repere['lat'], 'lng': repere['lng']}
    # L'épingle suit désormais le GPS du lead (D-QJR5-15 pour la suite).
    nouveau['pinSource'] = 'lead'
    return enregistrer_layout(calepinage, nouveau, user=user,
                              libelle=LIBELLE_RECENTRAGE,
                              base_empreinte=base_empreinte)


def garder_repere(calepinage, *, user=None, base_empreinte=None):
    """Acquitte la dérive : ``repereAcquitte = B`` — nouvelle version."""
    from .layout import enregistrer_layout

    repere, document, _epingle = _repere_et_epingle(calepinage)
    nouveau = copy.deepcopy(document) if isinstance(document, dict) else {}
    nouveau['repereAcquitte'] = {'lat': repere['lat'], 'lng': repere['lng']}
    return enregistrer_layout(calepinage, nouveau, user=user,
                              libelle=LIBELLE_REPERE_GARDE,
                              base_empreinte=base_empreinte)


def inventaire_derives(calepinages):
    """DRY-RUN (soumis au fondateur avant merge) — aucune écriture.

    Pour chaque calepinage : ``{calepinage, ancien_pin, nouveau_pin,
    ecart_m, etat, devis}`` des seuls calepinages en dérive. À lancer en
    shell : ``inventaire_derives(Calepinage.objects.filter(company=…))``.
    """
    from .. import selectors as cal_selectors

    lignes = []
    for calepinage in calepinages:
        repere = repere_du_lead(
            cal_selectors.contexte_geographique(calepinage))
        etat = etat_derive(getattr(calepinage, 'roof_layout', None), repere)
        if etat['derive']['etat'] == ETAT_AUCUNE:
            continue
        lignes.append({
            'calepinage': calepinage.pk,
            'ancien_pin': _point((calepinage.roof_layout or {}).get('pin')),
            'nouveau_pin': repere,
            'ecart_m': etat['ecart_m'],
            'etat': etat['derive']['etat'],
            'devis': getattr(calepinage, 'devis_id', None),
        })
    return lignes
