"""Vue FG313 — contrôle budgétaire à la commande.

``ControleBudgetaireCommandeView`` : un endpoint de LECTURE qui répond, avant de
valider un bon de commande, si un montant d'achat prévu tient dans le budget
RESTANT du programme (``BudgetProjet``, FG294, même app). Il ne valide rien et ne
modifie rien — c'est un garde-fou consultatif (ROUTINE) que l'écran d'achat
appelle avant l'envoi.

GET /installations/controle-budgetaire/?montant=...&projet=...&categorie=materiel

Multi-tenant : la société vient de ``request.user.company`` (jamais du corps). Le
programme ciblé est implicitement scopé société par le sélecteur. Lecture tout
rôle (consultation), comme les autres lectures budget.
"""
from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsAnyRole

from .. import selectors

CATEGORIES = ('materiel', 'main_oeuvre', 'sous_traitance', 'divers')


class ControleBudgetaireCommandeView(APIView):
    """FG313 — contrôle budgétaire consultatif avant commande. Lecture tout
    rôle ; aucune écriture. Société posée serveur."""
    permission_classes = [IsAnyRole]

    def get(self, request):
        company = request.user.company
        raw_montant = request.query_params.get('montant')
        try:
            montant = Decimal(str(raw_montant)) if raw_montant else Decimal('0')
        except (InvalidOperation, ValueError):
            return Response(
                {'montant': 'Montant invalide.'},
                status=status.HTTP_400_BAD_REQUEST)
        if montant < 0:
            return Response(
                {'montant': 'Le montant ne peut pas être négatif.'},
                status=status.HTTP_400_BAD_REQUEST)
        projet_id = request.query_params.get('projet') or None
        categorie = request.query_params.get('categorie') or 'materiel'
        if categorie not in CATEGORIES:
            return Response(
                {'categorie': f'Catégorie inconnue (attendu {CATEGORIES}).'},
                status=status.HTTP_400_BAD_REQUEST)
        result = selectors.controle_budgetaire_commande(
            company, montant, projet_id=projet_id, categorie=categorie)
        return Response(result, status=status.HTTP_200_OK)
