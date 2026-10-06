"""ASTK25 — verrou unique des documents stock/achats FIGÉS.

Une réception confirmée, un retour validé ou une session d'inventaire
validée ont déjà produit leurs effets (mouvements de stock, quantités reçues
du BCF, valorisation à date, OTD) : les modifier après coup réécrit
l'historique sans rejouer ces effets. Ce mixin refuse tout PUT/PATCH d'un
document dont le statut est figé — 400 « … : non modifiable » —, avant
même la validation du corps (donc jamais le 500 « AssertionError » de DRF
sur une écriture imbriquée).

Usage — déclarer, sur le ViewSet (mixin AVANT la base DRF)::

    class ReceptionFournisseurViewSet(DocumentFigeMixin, ...):
        messages_document_fige = {
            ReceptionFournisseur.Statut.CONFIRME:
                'Réception confirmée : non modifiable.',
        }

Survivant unique (réception, retour fournisseur, session d'inventaire) :
aucune garde de statut d'édition n'est réécrite à la main ailleurs.
"""
from rest_framework import status
from rest_framework.response import Response


class DocumentFigeMixin:
    #: {statut figé: message 400 renvoyé à toute tentative de modification}.
    messages_document_fige = {}

    def update(self, request, *args, **kwargs):
        # `partial_update` (PATCH) délègue à `update` : un seul point de garde.
        document = self.get_object()
        message = self.messages_document_fige.get(
            getattr(document, 'statut', None))
        if message is not None:
            return Response(
                {'detail': message}, status=status.HTTP_400_BAD_REQUEST)
        return super().update(request, *args, **kwargs)
