"""ENFP (décision fondateur D2 du 09/10/2026) — les vues SANS fichier
n'acceptent que du JSON ; le multipart reste réservé aux vues d'upload.

Constat (api-fuzz du 09/10, cluster D2, 51 constats) : le défaut DRF
(``JSONParser`` + ``FormParser`` + ``MultiPartParser``) fait accepter à TOUTE
vue un corps ``multipart/form-data`` dont les booléens arrivent en chaînes
(``"false"`` coercé selon des règles de formulaire HTML), alors que le schéma
OpenAPI ne publie que ``application/json`` pour elle.

Pourquoi le DÉFAUT GLOBAL n'est PAS basculé en JSON seul (ENFP, 09/10) : au
moins 16 modules lisent ``request.FILES`` sans déclarer leurs parseurs (ils
s'appuient sur le défaut DRF) — les basculer en JSON seul casserait leurs
uploads. La liste est dans le rapport ENFP ; une fois que chaque vue d'upload
déclare ``parser_classes = PARSEURS_UPLOAD`` (ou ``ParseursUploadMixin``), le
défaut ``REST_FRAMEWORK['DEFAULT_PARSER_CLASSES']`` pourra passer à
``PARSEURS_JSON``.

Usage (lanes par app) :

* vue sans fichier : ``parser_classes = PARSEURS_JSON`` ou hériter de
  ``JsonSeulementMixin`` ; un corps multipart reçoit alors un 415
  ``unsupported_media_type`` (enveloppe ``core.exceptions``) ;
* vue d'upload : ``parser_classes = PARSEURS_UPLOAD`` ou hériter de
  ``ParseursUploadMixin`` (comportement actuel, rendu EXPLICITE) ;
* ``@action`` : ``@action(..., parser_classes=PARSEURS_UPLOAD)``.

Tuples (immuables) : une sous-classe ne peut pas muter la liste partagée.
"""
from __future__ import annotations

from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

PARSEURS_JSON = (JSONParser,)
PARSEURS_UPLOAD = (JSONParser, MultiPartParser, FormParser)


class JsonSeulementMixin:
    """Vue sans fichier : corps JSON uniquement (D2)."""

    parser_classes = PARSEURS_JSON


class ParseursUploadMixin:
    """Vue d'upload : JSON + multipart + formulaire, déclarés explicitement."""

    parser_classes = PARSEURS_UPLOAD
