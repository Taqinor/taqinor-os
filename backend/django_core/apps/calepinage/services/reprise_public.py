"""CAL110 — reprendre le tracé public « mon-toit » dans un calepinage.

LE CONSTAT
----------
Les deux pages publiques du parcours font tourner le MÊME moteur 3D et créent
un lead, mais le tracé du visiteur n'atterrissait nulle part côté ERP : le
lead ne stocke qu'un point et un contour UNIQUE. Un visiteur qui dessine trois
pans en perdait deux, en silence.

CE QUE CE MODULE FAIT
----------------------
Il TRADUIT ce que le lead porte en un document ``roof_layout`` v2, puis crée
UN calepinage brouillon rattaché au lead, pré-tracé. Rien de plus :

* la lecture du lead passe par ``apps.crm.selectors`` — jamais ses modèles
  (frontière inter-apps, contrats import-linter) ;
* AUCUNE écriture vers crm : ``roof_outline`` et ``roof_point`` du lead
  restent exactement ce qu'ils sont (CAL217 est fondue ici) ;
* la création et l'enregistrement passent par les chemins COMMUNS du module
  (``services.creation.creer_pour_lead``, ``services.layout``), donc la
  version et le chatter sont alimentés comme pour n'importe quelle
  conception.

ZÉRO CRÉATION SILENCIEUSE
--------------------------
Un lead SANS tracé exploitable ne crée AUCUN calepinage : un calepinage vide
ferait croire à une conception commencée, et il faudrait ensuite le distinguer
d'un vrai. Un lead qui a DÉJÀ un calepinage n'en reçoit pas un second (la
reprise est idempotente : le même lead rejoué ne duplique rien).

ZÉRO CHIFFRE INVENTÉ
---------------------
Le document rendu ne porte que ce que le visiteur a réellement tracé ou dit.
Aucune puissance de panneau, aucune cote de module, aucune estimation n'y est
ajoutée : le traducteur du moteur (CAL78) refusera d'ailleurs un document sans
kit chiffrable, et c'est le comportement voulu — un calepinage pré-tracé est
un TRACÉ, pas une étude.

ORDRE DES AXES — LE PIÈGE, FERMÉ ICI
--------------------------------------
``Lead.roof_outline`` est en ``[lat, lng]`` (comme ``outline`` du document),
tandis que ``zones[].vertices`` est en ``[lng, lat]``. Les deux se ressemblent
et la confusion produit une toiture retournée, plausible et fausse. La
conversion est donc faite par une fonction NOMMÉE, et un test la couvre.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: La clé sous laquelle le document public voyage (contrat
#: ``contract_samples/lead_layout_public.json``).
CLE_LAYOUT = 'roof_layout'

#: Le champ JSON du lead qui porte les réponses publiques sans colonne dédiée.
CHAMP_PORTEUR = 'web_questionnaire'

#: Le repère de la zone construite à partir du seul ``roof_outline``.
REPERE_ZONE_CONTOUR = 'z1'

__all__ = [
    'CLE_LAYOUT', 'CHAMP_PORTEUR', 'REPERE_ZONE_CONTOUR',
    'document_public_du_lead', 'latlng_vers_lnglat',
    'reprendre_trace_public',
]


def latlng_vers_lnglat(points):
    """``[[lat, lng], …]`` -> ``[[lng, lat], …]`` — l'échange est NOMMÉ.

    Rend ``[]`` sur une entrée illisible : un contour à moitié lu vaut moins
    que pas de contour du tout.
    """
    propres = []
    for point in points or ():
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return []
        lat, lng = point[0], point[1]
        if isinstance(lat, bool) or isinstance(lng, bool):
            return []
        if not isinstance(lat, (int, float)) \
                or not isinstance(lng, (int, float)):
            return []
        propres.append([float(lng), float(lat)])
    return propres


def _epingle(lead):
    """``{lat, lng}`` du lead, ou ``None`` — jamais une ville devinée."""
    brut = getattr(lead, 'roof_point', None)
    if not isinstance(brut, dict):
        return None
    lat, lng = brut.get('lat'), brut.get('lng')
    if isinstance(lat, bool) or isinstance(lng, bool):
        return None
    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
        return None
    return {'lat': float(lat), 'lng': float(lng)}


def _document_transporte(lead):
    """Le document v2 transporté par le lead, s'il en porte un de valide."""
    porteur = getattr(lead, CHAMP_PORTEUR, None)
    if not isinstance(porteur, dict):
        return None
    document = porteur.get(CLE_LAYOUT)
    if not isinstance(document, dict) or not document:
        return None
    zones = document.get('zones')
    if not isinstance(zones, list) or not zones:
        return None
    return document


def document_public_du_lead(lead):
    """Le document ``roof_layout`` v2 d'un lead public, ou ``None``.

    Deux sources, dans cet ordre — jamais une troisième inventée :

    1. le DOCUMENT transporté par la page publique (clé ``roof_layout`` du
       champ porteur, contrat ``lead_layout_public.json``) : il porte
       PLUSIEURS zones, c'est tout l'objet de CAL110 ;
    2. à défaut, le ``roof_outline`` du lead — le cas de tous les leads
       existants — traduit en UNE zone. C'est une traduction de ce que le
       visiteur a tracé, pas une géométrie supposée.

    Rend ``None`` quand le lead ne porte aucun tracé exploitable : il ne faut
    alors créer AUCUN calepinage.
    """
    if lead is None:
        return None

    transporte = _document_transporte(lead)
    epingle = _epingle(lead)
    if transporte is not None:
        document = dict(transporte)
        # L'épingle du lead ne remplace jamais celle du document : c'est le
        # document qui fait foi sur sa propre géométrie.
        if document.get('pin') is None and epingle is not None:
            document['pin'] = epingle
        return document

    contour = latlng_vers_lnglat(getattr(lead, 'roof_outline', None) or [])
    if len(contour) < 3:
        return None
    document = {
        'version': 2,
        'source': 'lead',
        'zones': [{'id': REPERE_ZONE_CONTOUR, 'vertices': contour}],
        'outline': [[point[1], point[0]] for point in contour],
    }
    if epingle is not None:
        document['pin'] = epingle
    return document


def reprendre_trace_public(lead_id, company, *, user=None):
    """Crée le calepinage brouillon PRÉ-TRACÉ d'un lead public.

    Args:
        lead_id: le lead dont on reprend le tracé.
        company: la société — posée côté serveur (celle du lead), jamais lue
            d'un corps de requête.
        user: l'auteur, quand un utilisateur agit. Une capture publique n'en
            a pas : le calepinage est alors créé sans auteur, ce qui est la
            vérité (personne n'a agi dans l'ERP).

    Returns:
        Le ``Calepinage`` créé, ou ``None`` quand il ne FAUT pas en créer :
        lead introuvable, lead sans tracé exploitable, ou lead qui a déjà un
        calepinage (idempotence).
    """
    from apps.crm.selectors import get_company_lead

    from .. import selectors
    from .creation import creer_pour_lead
    from .layout import enregistrer_layout

    if company is None or not lead_id:
        return None

    lead = get_company_lead(company, lead_id)
    if lead is None:
        return None

    document = document_public_du_lead(lead)
    if document is None:
        return None

    if selectors.liste_calepinages(company, lead_id=lead_id).exists():
        # Déjà repris (rejeu d'événement, lead ré-enregistré) : on ne crée
        # jamais un second calepinage pour le même tracé.
        return None

    calepinage = creer_pour_lead(lead_id, company, user=user)
    enregistrer_layout(calepinage, document, user=user,
                       libelle='Tracé repris du parcours public « mon toit »')
    return calepinage
