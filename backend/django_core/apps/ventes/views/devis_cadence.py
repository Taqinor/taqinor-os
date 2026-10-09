"""SPL142 — « Relances du jour » : la vue ``action-requise`` du devis,
déplacement pur depuis ``views/devis.py`` : corps octet-identique, route
inchangée. Sa forme déclarée (``DevisActionRequiseSerializer`` et ses quatre
sous-sérialiseurs) vit dans ``serializers_cadence.py`` (même propriétaire).
"""
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from ..serializers_cadence import DevisActionRequiseSerializer
from authentication.permissions import IsAnyRole


class DevisCadenceActionsMixin:
    """SPL142 — action « Relances du jour » de ``DevisViewSet`` (mixin, aucune base)."""

    @extend_schema(responses=DevisActionRequiseSerializer)
    @action(detail=False, methods=['get'], url_path='action-requise',
            permission_classes=[IsAnyRole])
    def action_requise(self, request):
        """PACT17 (QX29/QX30) — « Relances du jour » : les devis nécessitant
        une action, groupés par MOTIF.

        L'écran ``DevisActionBoardPage`` appelait cet agrégat depuis sa
        création et l'entrée de menu était publiée aux rôles responsable/admin
        — mais la moitié serveur n'avait jamais été construite : le chemin
        retombait sur la route de DÉTAIL du routeur (``devis/<pk>/`` accepte
        n'importe quel segment), donc un 404, donc un écran mort. Cette action
        est cette moitié manquante, miroir de ``/sav/tickets/file-action/``
        (ZSAV6).

        CAD115 (SIG9) — le tableau est désormais ouvert au rôle qui relance
        réellement (nav ``['normal','responsable','admin']``), et chaque
        ligne publie ``prochaine_touche_crm`` pour arbitrer avec la file
        calendaire du CRM.

        Lecture PURE via ``selectors.devis_action_requise``, bornée à
        ``request.user.company`` — jamais de devis d'une autre société. RÈGLE
        #4 : aucune écriture, aucun statut touché.

        ADEV64 (C-ADEV-025) — et à la PORTÉE de ``request.user`` : un
        Commercial de portée ``team`` ne voit ni les devis ni les téléphones
        des clients hors de sa portée (auteur du devis ou responsable du lead).

        Renvoie ``{'buckets': {clé: {'count', 'ids'}, …}, 'wa_drafts':
        {id: message}}`` — forme déclarée par ``DevisActionRequiseSerializer``
        (PACT7 : jamais ``response=dict``).
        """
        from ..selectors import devis_action_requise
        return Response(devis_action_requise(request.user.company,
                                             user=request.user))
