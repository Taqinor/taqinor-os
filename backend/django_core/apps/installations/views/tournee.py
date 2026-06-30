"""Vue FG332 — optimisation de tournée de livraison multi-sites.

``TourneeLivraisonView`` : endpoint de LECTURE qui regroupe et ordonne les
livraisons planifiées d'un jour par proximité (plus proche voisin sur la
position GPS du site de chaque chantier), depuis un point de départ optionnel
(le dépôt). Consultatif (ROUTINE) — n'exécute aucune livraison.

GET /installations/tournee-livraison/?jour=YYYY-MM-DD&depart_lat=..&depart_lng=..

Multi-tenant : la société vient de ``request.user.company`` (jamais du corps).
Lecture tout rôle.
"""
from datetime import date

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsAnyRole

from .. import selectors


class TourneeLivraisonView(APIView):
    """FG332 — tournée de livraison optimisée pour un jour. Lecture tout rôle ;
    aucune écriture. Société posée serveur."""
    permission_classes = [IsAnyRole]

    def get(self, request):
        company = request.user.company
        raw_jour = request.query_params.get('jour')
        if not raw_jour:
            return Response(
                {'jour': 'Paramètre `jour` requis (YYYY-MM-DD).'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            jour = date.fromisoformat(raw_jour)
        except ValueError:
            return Response(
                {'jour': 'Date invalide (attendu YYYY-MM-DD).'},
                status=status.HTTP_400_BAD_REQUEST)
        depart_lat = request.query_params.get('depart_lat')
        depart_lng = request.query_params.get('depart_lng')
        try:
            depart_lat = float(depart_lat) if depart_lat else None
            depart_lng = float(depart_lng) if depart_lng else None
        except (ValueError, TypeError):
            return Response(
                {'depart': 'Coordonnées de départ invalides.'},
                status=status.HTTP_400_BAD_REQUEST)
        result = selectors.optimiser_tournee_livraison(
            company, jour, depart_lat=depart_lat, depart_lng=depart_lng)
        return Response(result, status=status.HTTP_200_OK)
