"""PUB123 — Pont ``CreativeAsset`` → payload créatif Meta (le maillon central).

Le mur entre la créathèque MAISON et la diffusion Meta tenait à ce maillon
manquant : un asset approuvé ne pouvait pas devenir un fragment ``creative``
consommable par les dispatchs de création d'ad (PUB119 rotation, PUB120
matérialisation des rotations, PUB121 slots de lancement). Les deux bouts
existaient déjà séparément :

  * PUB122 a posé les identifiants de COMPTE (``CreativeAsset.meta_image_hash``
    / ``meta_video_id``) — les seuls identifiants qu'un créatif publicitaire
    peut référencer (une clé MinIO, Meta ne sait pas la lire) ;
  * PUB126 a posé la divulgation IA par asset (``ai_generated``) et la garde
    dure de la check-list ;
  * ``MetaConnection.page_id`` porte la Page de la société — une ``object_story_spec``
    n'existe PAS sans ``page_id`` (Meta exige l'acteur qui publie).

Ce module compose ces briques et REFUSE explicitement, en français, tout asset
non conforme : non validé policy, étiquette IA manquante, consentement PUB75
absent/révoqué/expiré/hors portée, média jamais uploadé au compte, type d'asset
incohérent avec son média, ou société sans Page connectée. Aucun refus n'est
silencieux et aucun payload n'est jamais bâti « à moitié ».

PROVENANCE — le payload transporte ``generation_audit``
(``generation_audit.asset_provenance``) : fait cité → version de la ``FactTable``
→ verdicts par claim → décision humaine → ``policy_stamp``. La chaîne survit
donc jusqu'à l'``EngineAction`` et donc jusqu'à l'ad résultante (le payload est
persisté sur l'action).

INVARIANT (règle #3) : ce module ne fait AUCUN appel réseau et n'écrit AUCUN
``status``. Il construit un fragment ; la création de l'ad, elle, naît toujours
PAUSED côté ``meta_client``.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Clés machine des refus (le texte FR reste la surface humaine).
REFUS_ASSET_ABSENT = 'asset_absent'
REFUS_POLICY = 'policy_non_validee'
REFUS_ETIQUETTE_IA = 'etiquette_ia_manquante'
REFUS_CONSENTEMENT = 'consentement'
REFUS_MEDIA = 'media_non_uploade'
REFUS_PAGE = 'page_absente'

# Raisons FR du blocage consentement (clés de ``consent_block_reason``, PUB75).
_CONSENT_FR = {
    'manquant': ("Consentement manquant : cet asset montre un client réel — le "
                 "registre CNDP (loi 09-08) n'a aucun consentement signé."),
    'revoque': ("Consentement RÉVOQUÉ par le client : cet asset ne peut plus "
                "être diffusé."),
    'expire': ("Consentement EXPIRÉ : à renouveler avant toute nouvelle "
               "diffusion de cet asset."),
    'portee': ("Consentement insuffisant : une portée requise (photo / vidéo / "
               "témoignage / géo) n'est pas couverte."),
}

# Média de COMPTE attendu selon le type d'asset : un reel / explainer diffuse
# une VIDÉO, un statique une IMAGE. On ne « rattrape » jamais un type avec le
# média de l'autre famille (un reel servi en image est un bug, pas une option).
MEDIA_VIDEO = 'video'
MEDIA_IMAGE = 'image'


def _expected_media(asset):
    from .models import CreativeAsset

    if asset.asset_type in (CreativeAsset.AssetType.REEL,
                            CreativeAsset.AssetType.EXPLAINER):
        return MEDIA_VIDEO
    return MEDIA_IMAGE


class CreativeAssetNotReady(ValueError):
    """PUB123 — Asset non conforme : porte la raison FR ET une clé machine.

    Sous-classe de ``ValueError`` : une vue la rend en 400 avec son texte FR,
    jamais en 500. ``key`` permet aux appelants (proposeurs) de router sans
    parser du français."""

    def __init__(self, reason_fr, *, key=''):
        self.reason_fr = str(reason_fr)
        self.key = key
        super().__init__(self.reason_fr)


def connection_page_id(company, *, connection=None):
    """``page_id`` de la Page Facebook de la société (champ EXISTANT sur
    ``MetaConnection`` — aucune migration n'a été nécessaire : le contrôle
    « champ additif si absent » de PUB123 est donc un NO-OP vérifié).

    Renvoie ``''`` si la société n'a pas de connexion ou pas de Page — jamais un
    id fabriqué."""
    if connection is not None:
        return (getattr(connection, 'page_id', '') or '').strip()
    from .models import MetaConnection

    conn = MetaConnection.objects.filter(company=company).first()
    return (getattr(conn, 'page_id', '') or '').strip() if conn else ''


def refusal(asset, *, company=None, connection=None):
    """Raison de refus d'un asset pour la diffusion, ou ``None`` s'il est prêt.

    Renvoie ``(clé, raison_fr)``. Ordre délibéré : ce qui relève de la CONFORMITÉ
    (policy, étiquette IA, consentement) passe AVANT la technique (média, Page) —
    un asset non conforme doit lire d'abord sa raison de conformité.
    """
    if asset is None:
        return (REFUS_ASSET_ABSENT,
                "Asset créatif introuvable pour cette société.")

    from . import policy as policy_mod

    if not asset.is_policy_passed:
        return (REFUS_POLICY,
                "Asset non validé : la check-list policy (ENG16) n'est pas "
                "passée — il ne peut pas partir en diffusion.")

    if policy_mod.ai_disclosure_block_reason(asset) is not None:
        return (REFUS_ETIQUETTE_IA, policy_mod.AI_DISCLOSURE_BLOCK_LABEL)

    consent_key = asset.consent_block_reason()
    if consent_key is not None:
        return (REFUS_CONSENTEMENT,
                _CONSENT_FR.get(
                    consent_key,
                    "Consentement non conforme : diffusion impossible."))

    expected = _expected_media(asset)
    if expected == MEDIA_VIDEO and not asset.meta_video_id:
        return (REFUS_MEDIA,
                "Vidéo jamais uploadée au compte publicitaire : un créatif ne "
                "peut référencer qu'un ``video_id`` de compte (PUB122), jamais "
                "une clé de stockage interne.")
    if expected == MEDIA_IMAGE and not asset.meta_image_hash:
        return (REFUS_MEDIA,
                "Image jamais uploadée au compte publicitaire : un créatif ne "
                "peut référencer qu'un ``image_hash`` de compte (PUB122), "
                "jamais une clé de stockage interne.")

    page_id = connection_page_id(
        company if company is not None else asset.company,
        connection=connection)
    if not page_id:
        return (REFUS_PAGE,
                "Aucune Page Facebook connectée (ID Page vide sur la connexion "
                "Meta) : un créatif publicitaire doit déclarer la Page qui "
                "publie.")
    return None


def is_ready(asset, *, company=None, connection=None):
    """Vrai si l'asset est diffusable (aucun refus). Lecture seule."""
    return refusal(asset, company=company, connection=connection) is None


def _story_spec(asset, *, page_id, link_url=''):
    """``object_story_spec`` d'un asset PRÊT (refus déjà tranchés en amont).

    * vidéo → ``video_data`` (``video_id`` de compte + message/titre + CTA) ;
    * image + lien → ``link_data`` (le format d'une ad de trafic/leads) ;
    * image sans lien → ``photo_data`` (aucun lien n'est FABRIQUÉ).

    Aucune VIGNETTE n'est envoyée pour une vidéo : la vignette choisie (PUB83)
    est une clé de stockage interne, pas un asset de compte Meta — en inventer
    un hash serait un créatif rejeté. Meta dérive sa vignette par défaut ;
    l'upload de la vignette choisie est un pas distinct, non construit ici.
    """
    spec = {'page_id': page_id}
    link_url = (link_url or '').strip()
    cta = (asset.cta or '').strip()
    message = (asset.primary_text or '').strip()
    title = (asset.hook_text or '').strip()

    if _expected_media(asset) == MEDIA_VIDEO:
        data = {'video_id': asset.meta_video_id}
        if message:
            data['message'] = message
        if title:
            data['title'] = title
        if cta:
            call = {'type': cta}
            if link_url:
                call['value'] = {'link': link_url}
            data['call_to_action'] = call
        spec['video_data'] = data
        return spec

    if link_url:
        data = {'image_hash': asset.meta_image_hash, 'link': link_url}
        if message:
            data['message'] = message
        if title:
            data['name'] = title
        if cta:
            data['call_to_action'] = {'type': cta,
                                      'value': {'link': link_url}}
        spec['link_data'] = data
        return spec

    data = {'image_hash': asset.meta_image_hash}
    if message:
        data['caption'] = message
    spec['photo_data'] = data
    return spec


def build_creative_payload(asset, *, company=None, connection=None,
                           link_url='', with_provenance=True):
    """PUB123 — Fragments de payload d'un asset APPROUVÉ, prêts à fusionner dans
    le payload d'une ``EngineAction`` de création d'ad.

    Renvoie ::

        {
          'creative': {'object_story_spec': {...}},   # ce que Graph reçoit
          'creative_asset_id': <pk>,                  # garde policy ENG15
          'ai_generated': <bool>,                     # divulgation PUB126
          'generation_audit': {...},                  # provenance PUB84/AGEN9
        }

    ``creative`` est EXACTEMENT le fragment que le client encode dans le champ
    ``creative`` (même forme que ``{'creative_id': …}`` du chemin duplicate) :
    les appelants n'ont rien à savoir de Graph.

    Le fragment de divulgation vient de ``policy.ai_disclosure_payload`` : la clé
    INTERNE ``ai_generated`` voyage toujours au niveau du payload, et le jour où
    le champ Graph de divulgation sera CONFIRMÉ (``policy.GRAPH_AI_DISCLOSURE_FIELD``,
    vide aujourd'hui — voir la note sourcée de ``policy.py``) il est ajouté À LA
    SPEC sans toucher un seul appelant.

    Lève ``CreativeAssetNotReady`` (raison FR + clé) sur tout asset non conforme.
    """
    from . import generation_audit, policy as policy_mod

    company = company if company is not None else getattr(asset, 'company', None)
    refus = refusal(asset, company=company, connection=connection)
    if refus is not None:
        raise CreativeAssetNotReady(refus[1], key=refus[0])

    page_id = connection_page_id(company, connection=connection)
    creative = {
        'object_story_spec': _story_spec(
            asset, page_id=page_id, link_url=link_url),
    }

    disclosure = policy_mod.ai_disclosure_payload(asset)
    graph_field = policy_mod.GRAPH_AI_DISCLOSURE_FIELD
    if graph_field and graph_field in disclosure:
        creative[graph_field] = disclosure[graph_field]

    payload = {
        'creative': creative,
        'creative_asset_id': asset.pk,
        'ai_generated': bool(disclosure.get('ai_generated')),
    }
    if with_provenance:
        payload['generation_audit'] = generation_audit.asset_provenance(asset)
    return payload
