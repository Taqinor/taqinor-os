"""CALX288 — ``GET /api/django/ventes/devis/<pk>/economie/`` (lecture seule).

Sert le BLOC ÉCONOMIE d'un devis, à la forme du contrat committé
``apps/ventes/contract_samples/ventes_economie.json`` (CALX280) : flux annuel,
VAN, TRI, LCOE, retours simple et actualisé, hypothèses sourcées et omissions
motivées. Le calcul vit dans ``apps/ventes/economie.py`` ; l'atelier de
calepinage LIRA ce bloc (CALX289), il ne le calcule jamais (D5).

POURQUOI UN FICHIER À PART DE ``views/devis.py``
------------------------------------------------
Même patron que les actions GREFFÉES du calepinage
(``apps/calepinage/views/equipements.py``) : l'``@action`` est une fonction de
module, rattachée au ``DevisViewSet`` par affectation d'attribut de classe
(``DevisViewSet.economie = economie``). ``apps/ventes/views/__init__.py``
importe ce module en DERNIÈRE ligne — il est lui-même importé par ``urls.py``
AVANT ``router.register`` : DRF découvre donc l'action au moment de
l'enregistrement, sans rouvrir ``urls.py`` ni ``views/devis.py``.

GARDES
------
* ``self.get_object()`` passe par ``DevisViewSet.get_queryset`` : un devis
  d'une autre société est INTROUVABLE (404, jamais 403 — aucun oracle
  d'existence) ;
* ``permission_classes`` explicite, honorée par ``declared_action_permissions``
  (AUD403) : ``IsAnyRole``, le même périmètre que la lecture d'un devis
  (compte interne ; un compte portail reçoit 403) ;
* LECTURE SEULE : aucune écriture, aucun changement de statut (règle #4) ;
* aucune clé ``prix``/``cout``/``marge`` dans la réponse — l'investissement est
  le total TTC CLIENT, jamais ``Produit.prix_achat``.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsAnyRole

from ..economie import EconomieInvalide, economie_pour_devis
from .devis import DevisViewSet

__all__ = ['economie']


@action(detail=True, methods=['get'], url_path='economie',
        permission_classes=[IsAnyRole])
def economie(self, request, pk=None):
    """CALX288 — le bloc économie du devis (contrat CALX280), en lecture."""
    devis = self.get_object()
    try:
        bloc = economie_pour_devis(devis.pk, devis.company)
    except EconomieInvalide as refus:
        # Un réglage société invalide : l'erreur NOMME le champ fautif.
        return Response({'detail': str(refus), 'champ': refus.champ},
                        status=status.HTTP_400_BAD_REQUEST)
    return Response(bloc)


# Rattachement au viewset PIVOT — voir la docstring du module.
DevisViewSet.economie = economie
