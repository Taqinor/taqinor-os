"""ACAL489 — fournisseur Claude de la capacité ``vision_toit`` (D-ACAL-33).

Image de toit → contour et pans PROPOSÉS (l'utilisateur confirme). Appel de
l'API Anthropic (Messages) par ``httpx`` — aucun nouveau paquet ; même patron
que ``apps/adsengine/veille_ia.py::appeler`` SANS l'importer (le noyau ne
dépend d'aucune app). ÉTEINT sans clé : ``is_configured`` faux ⇒ le registre
rend le NO-OP. Clé ``VISION_TOIT_CLE_API`` et modèle ``VISION_TOIT_MODELE`` en
réglages, jamais en dur. Seuls les octets et le type de l'image partent ; rien
n'est journalisé de l'image. Ne lève jamais : 4xx, 5xx, délai ou réponse
invalide ⇒ ``ok=False`` et raison française.

DÉPENDANCE PAYANTE : API Anthropic, inactive tant que la clé est vide.
"""
from __future__ import annotations

import base64
import json

import httpx
from django.conf import settings

from core.ai.providers import AIResult, VisionToitProvider
from core.ai.registry import register_provider

URL_MESSAGES = 'https://api.anthropic.com/v1/messages'
VERSION_API = '2023-06-01'
MAX_TOKENS = 2048
DELAI_S = 60
TYPES_IMAGE = ('image/jpeg', 'image/png', 'image/gif', 'image/webp')
CONSIGNE = (
    "Tu reçois une image vue du ciel d'un toit. Repère chaque pan de toiture "
    "et réponds UNIQUEMENT par un objet JSON "
    '{"pans": [{"sommets": [[x, y], ...], "confiance": c}]} où x et y sont '
    "des fractions de la largeur et de la hauteur de l'image (0 à 1, origine "
    "en haut à gauche), au moins 3 sommets par pan, et c une confiance entre "
    "0 et 1. Aucun texte hors du JSON.")


def _reglage(nom):
    return str(getattr(settings, nom, '') or '').strip()


def _fraction(valeur):
    return (isinstance(valeur, (int, float)) and not isinstance(valeur, bool)
            and 0 <= valeur <= 1)


def valider_pans(objet):
    """``(pans, '')`` si la proposition est valide, sinon ``(None, raison)``."""
    pans = objet.get('pans') if isinstance(objet, dict) else None
    if not isinstance(pans, list) or not pans:
        return None, 'aucun pan proposé'
    propres = []
    for pan in pans:
        sommets = pan.get('sommets') if isinstance(pan, dict) else None
        if not isinstance(sommets, list) or len(sommets) < 3:
            return None, 'pan à moins de 3 sommets'
        for point in sommets:
            if not (isinstance(point, list) and len(point) == 2
                    and all(_fraction(v) for v in point)):
                return None, 'coordonnée hors de [0, 1]'
        confiance = pan.get('confiance')
        propres.append({'sommets': [[float(x), float(y)] for x, y in sommets],
                        'confiance': float(confiance) if _fraction(confiance) else None})
    return propres, ''


def _objet(texte):
    texte = (texte or '').strip()
    debut, fin = texte.find('{'), texte.rfind('}')
    if debut < 0 or fin < debut:
        raise ValueError('aucun objet JSON')
    return json.loads(texte[debut:fin + 1])


@register_provider
class ClaudeVisionToitProvider(VisionToitProvider):
    key = 'claude'
    label = 'Claude (détection du toit)'
    #: Transport httpx injectable (tests : ``httpx.MockTransport``) ; None = réseau.
    transport = None

    def is_configured(self) -> bool:
        return bool(_reglage('VISION_TOIT_CLE_API') and _reglage('VISION_TOIT_MODELE'))

    def _echec(self, raison, usage=None):
        return AIResult(ok=False, configured=True, provider=self.key,
                        data={'usage': usage} if usage else {}, error=raison)

    def detecter(self, *, content, mime_type):
        if mime_type not in TYPES_IMAGE:
            return self._echec("type d'image non pris en charge")
        if not content:
            return self._echec('image vide')
        corps = {
            'model': _reglage('VISION_TOIT_MODELE'),
            'max_tokens': MAX_TOKENS,
            'system': CONSIGNE,
            'messages': [{'role': 'user', 'content': [{
                'type': 'image',
                'source': {'type': 'base64', 'media_type': mime_type,
                           'data': base64.b64encode(content).decode('ascii')},
            }]}],
        }
        entetes = {'x-api-key': _reglage('VISION_TOIT_CLE_API'),
                   'anthropic-version': VERSION_API,
                   'content-type': 'application/json'}
        try:
            with httpx.Client(timeout=DELAI_S, transport=self.transport) as client:
                reponse = client.post(URL_MESSAGES, json=corps, headers=entetes)
        except httpx.TimeoutException:
            return self._echec('délai dépassé')
        except httpx.HTTPError as exc:
            return self._echec(f'erreur réseau ({type(exc).__name__})')
        try:
            donnees = reponse.json()
        except ValueError:
            donnees = {}
        donnees = donnees if isinstance(donnees, dict) else {}
        brut = donnees.get('usage')
        usage = ({'prompt_tokens': brut.get('input_tokens') or 0,
                  'completion_tokens': brut.get('output_tokens') or 0}
                 if isinstance(brut, dict) else None)
        if reponse.status_code >= 400:
            return self._echec(f'HTTP {reponse.status_code}', usage)
        if donnees.get('stop_reason') == 'refusal':
            return self._echec('refus du modèle', usage)
        texte = ''.join(str(b.get('text') or '') for b in donnees.get('content') or []
                        if isinstance(b, dict) and b.get('type') == 'text')
        try:
            pans, raison = valider_pans(_objet(texte))
        except (ValueError, TypeError):
            pans, raison = None, 'réponse invalide'
        if pans is None:
            return self._echec(raison, usage)
        data = {'pans': pans}
        if usage:
            data['usage'] = usage
        return AIResult(ok=True, configured=True, provider=self.key, data=data)
