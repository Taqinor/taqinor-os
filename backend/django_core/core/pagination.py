"""YAPIC1 — pagination partagée avec plafond dur (``max_page_size``).

Le défaut historique pointait le ``PageNumberPagination`` brut de DRF :
``PAGE_SIZE=100`` figé, aucun ``page_size_query_param`` — un client ne pouvait
ni réduire la taille de page, ni le serveur borner une requête custom. Rien ne
garantissait non plus qu'un futur override ne renvoie une liste non bornée.

``StandardPagination`` :
  * ``page_size=50`` par défaut ;
  * ``page_size_query_param='page_size'`` — le client peut demander moins ;
  * ``max_page_size=200`` — PLAFOND DUR : ``?page_size=5000`` renvoie au plus
    200 lignes (DRF ``get_page_size`` borne à ``max_page_size``).

L'enveloppe ``count/next/previous/results`` reste STRICTEMENT identique à celle
de DRF (aucune surcharge de ``get_paginated_response``). Câblée en
``DEFAULT_PAGINATION_CLASS`` ; les 7 vues ``pagination_class=None`` volontaires
(dashboard core, connecteurs…) restent inchangées.
"""
from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200
