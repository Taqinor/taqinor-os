"""Vues de la Gestion des contrats (scopées société, accès admin/responsable).

Les viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la
société côté serveur ; l'accès est réservé au palier Administrateur/Responsable
(``IsResponsableOrAdmin``).

Niveaux de confidentialité (CONTRAT6)
--------------------------------------
La visibilité d'un ``Contrat`` est réglée par son champ ``confidentialite`` :

- ``PUBLIC``       : visible par tous les utilisateurs authentifiés de la société
                     qui ont accès au module (responsable + admin).
- ``INTERNE``      : même visibilité que PUBLIC au niveau du rôle — pas de
                     restriction supplémentaire au-dessus du filtre société.
- ``CONFIDENTIEL`` : visible uniquement par les Administrateurs.

Le filtre est appliqué dans ``ContratViewSet.get_queryset``.  Les filtres
``?confidentialite=`` permettent de restreindre la liste côté client.

ModeleContratViewSet (CONTRAT7)
--------------------------------
Bibliothèque de gabarits/modèles de contrats. Scopé société (TenantMixin).
Action ``/instancier/`` crée un ``Contrat`` pré-rempli depuis le gabarit.
"""
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from . import selectors
from .models import Clause, Contrat, ContratLien, ModeleContrat, ModeleContratClause, PartieContrat
from .serializers import (
    ClauseSerializer,
    ContratLienSerializer,
    ContratSerializer,
    InstancierContratSerializer,
    ModeleContratClauseSerializer,
    ModeleContratSerializer,
    PartieContratSerializer,
)


class _ContratsBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class ContratViewSet(_ContratsBaseViewSet):
    """Contrats de la société (CLM). Recherche par référence/objet.

    Visibilité par confidentialité : les contrats ``CONFIDENTIEL`` ne sont
    accessibles qu'aux Administrateurs. Les contrats ``PUBLIC``/``INTERNE``
    sont accessibles à tous les Responsables et Administrateurs de la société.
    Un filtre optionnel ``?confidentialite=<niveau>`` permet de restreindre
    la liste retournée.
    """
    queryset = Contrat.objects.all()
    serializer_class = ContratSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'objet']
    ordering_fields = ['date_debut', 'date_fin', 'montant', 'id', 'confidentialite']

    def get_queryset(self):
        """Queryset scopé société + filtre confidentialité.

        Les contrats ``CONFIDENTIEL`` sont exclus pour les non-Administrateurs.
        Un filtre optionnel ``?confidentialite=<valeur>`` restreint
        supplémentairement la liste.
        """
        qs = super().get_queryset()
        user = self.request.user
        # Exclure les contrats CONFIDENTIEL pour les non-Administrateurs.
        # Le palier FAISANT AUTORITÉ est ``menu_tier`` (dérive du Role FK, repli
        # legacy, et renvoie ROLE_ADMIN pour un superuser) — ``role_legacy``
        # seul n'est pas fiable pour un admin provisionné via le Role FK.
        if user.menu_tier != user.ROLE_ADMIN:
            qs = qs.exclude(
                confidentialite=Contrat.NiveauConfidentialite.CONFIDENTIEL)
        # Filtre optionnel par niveau de confidentialité.
        niveau = self.request.query_params.get('confidentialite')
        if niveau:
            qs = qs.filter(confidentialite=niveau)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def liens(self, request, pk=None):
        """Liens du contrat ENRICHIS via les sélecteurs des apps cibles.

        Pour chaque lien : libellé frais quand l'app cible expose un sélecteur
        (``source='live'``), sinon le libellé stocké (``source='stored'``). La
        société est garantie par ``get_object`` (queryset scopé société).
        """
        contrat = self.get_object()
        return Response(selectors.liens_enrichis(contrat))


class PartieContratViewSet(_ContratsBaseViewSet):
    """Parties/signataires des contrats de la société.

    Société posée côté serveur (``TenantMixin.perform_create``) ; le contrat
    rattaché est validé même société par le sérialiseur. Filtrable par
    ``?contrat=<id>`` et recherchable par nom/email.
    """
    queryset = PartieContrat.objects.all()
    serializer_class = PartieContratSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'email']
    ordering_fields = ['ordre', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        contrat_id = self.request.query_params.get('contrat')
        if contrat_id:
            qs = qs.filter(contrat_id=contrat_id)
        return qs


class ContratLienViewSet(_ContratsBaseViewSet):
    """Liens contrat → devis / lead / installation / maintenance (refs lâches).

    ``company`` est posée côté serveur (TenantMixin) ; le ``contrat`` reçu est
    validé même-société par le sérialiseur. Filtres optionnels ``?contrat=<id>``
    et ``?type_cible=<type>``.
    """
    queryset = ContratLien.objects.select_related('contrat').all()
    serializer_class = ContratLienSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id']

    def get_queryset(self):
        qs = super().get_queryset()
        contrat_id = self.request.query_params.get('contrat')
        if contrat_id:
            qs = qs.filter(contrat_id=contrat_id)
        type_cible = self.request.query_params.get('type_cible')
        if type_cible:
            qs = qs.filter(type_cible=type_cible)
        return qs


class ModeleContratViewSet(_ContratsBaseViewSet):
    """Bibliothèque de gabarits de contrats (CONTRAT7).

    Scopé société (TenantMixin). ``company`` est posée côté serveur.

    Filtres : ``?actif=true/false``, ``?categorie=<texte>``.
    Recherche : ``nom``, ``categorie``.

    Action supplémentaire :
    - POST ``/<id>/instancier/`` : crée et renvoie un ``Contrat`` pré-rempli
      depuis ce gabarit (type_contrat, devise, confidentialite du gabarit ;
      ``objet`` et ``reference`` peuvent être surchargés dans le corps).
    """
    queryset = ModeleContrat.objects.all()
    serializer_class = ModeleContratSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'categorie']
    ordering_fields = ['ordre', 'nom', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        # Filtre optionnel ?actif=true/false
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'oui'))
        # Filtre optionnel ?categorie=<texte>
        categorie = self.request.query_params.get('categorie')
        if categorie:
            qs = qs.filter(categorie__icontains=categorie)
        return qs

    @action(detail=True, methods=['post'])
    def instancier(self, request, pk=None):
        """Crée un ``Contrat`` pré-rempli depuis ce gabarit.

        Les champs du gabarit (type_contrat_defaut, devise_defaut,
        confidentialite_defaut) sont copiés sur le nouveau contrat. L'appelant
        peut fournir ``objet`` et ``reference`` dans le corps de la requête pour
        surcharger les valeurs par défaut (``objet`` est requis si non fourni,
        car c'est un champ obligatoire sur ``Contrat``). La société est posée
        côté serveur.
        """
        modele = self.get_object()
        body_serializer = InstancierContratSerializer(data=request.data)
        body_serializer.is_valid(raise_exception=True)
        data = body_serializer.validated_data

        objet = data.get('objet') or modele.nom
        reference = data.get('reference', '')

        contrat = Contrat.objects.create(
            company=request.user.company,
            created_by=request.user,
            objet=objet,
            reference=reference,
            type_contrat=modele.type_contrat_defaut,
            devise=modele.devise_defaut,
            confidentialite=modele.confidentialite_defaut,
        )
        return Response(
            ContratSerializer(contrat, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class ClauseViewSet(_ContratsBaseViewSet):
    """Bibliothèque de clauses réutilisables (CONTRAT8).

    Scopé société (TenantMixin). ``company`` est posée côté serveur.

    Filtres : ``?actif=true/false``, ``?type_clause=<valeur>``,
              ``?categorie=<texte>``.
    Recherche : ``titre``, ``categorie``, ``corps``.
    """

    queryset = Clause.objects.all()
    serializer_class = ClauseSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["titre", "categorie", "corps"]
    ordering_fields = ["ordre", "titre", "type_clause", "id"]

    def get_queryset(self):
        qs = super().get_queryset()
        # Filtre optionnel ?actif=true/false
        actif = self.request.query_params.get("actif")
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ("1", "true", "oui"))
        # Filtre optionnel ?type_clause=<valeur>
        type_clause = self.request.query_params.get("type_clause")
        if type_clause:
            qs = qs.filter(type_clause=type_clause)
        # Filtre optionnel ?categorie=<texte>
        categorie = self.request.query_params.get("categorie")
        if categorie:
            qs = qs.filter(categorie__icontains=categorie)
        return qs


class ModeleContratClauseViewSet(_ContratsBaseViewSet):
    """Liaisons ordonnées ModeleContrat ↔ Clause (CONTRAT8).

    Permet d'associer des clauses à un gabarit de contrat avec un ordre
    d'affichage propre au gabarit. Scopé société ; ``company`` posée côté
    serveur.

    Filtre optionnel : ``?modele=<id>`` pour lister les clauses d'un gabarit.
    """

    queryset = ModeleContratClause.objects.select_related("modele", "clause").all()
    serializer_class = ModeleContratClauseSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["ordre", "id"]

    def get_queryset(self):
        qs = super().get_queryset()
        modele_id = self.request.query_params.get("modele")
        if modele_id:
            qs = qs.filter(modele_id=modele_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)
