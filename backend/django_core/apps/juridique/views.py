"""Vues du module ``apps.juridique`` (groupe NTJUR).

Tout est scopé société (``CompanyScopedModelViewSet``, ARC2 : queryset filtré
sur ``request.user.company`` + ``company`` forcée côté serveur dans
``perform_create``). S'y ajoute le filtrage de CONFIDENTIALITÉ (NTJUR1) : un
dossier ``confidentiel`` est simplement ABSENT du queryset d'un utilisateur
sans le palier requis — un accès direct par id renvoie donc 404 (jamais 403,
qui révélerait l'existence du dossier).
"""
from rest_framework import filters

from core.viewsets import CompanyScopedModelViewSet

from . import selectors
from .models import DossierJuridique
from .serializers import DossierJuridiqueSerializer


class DossierJuridiqueViewSet(CompanyScopedModelViewSet):
    """CRUD des dossiers juridiques de la société (NTJUR1).

    Le contrôle d'accès suit le patron YRBAC3 des modules voisins
    (``contrats``/``litiges``) : lecture et écriture gardées par des codes
    distincts, avec le repli légacy pour les comptes sans rôle fin.
    """

    queryset = DossierJuridique.objects.select_related(
        'company', 'responsable_interne', 'created_by').all()
    serializer_class = DossierJuridiqueSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'titre', 'partie_adverse_nom']
    ordering_fields = ['id', 'date_ouverture', 'montant_en_jeu', 'statut']
    read_permission = 'juridique_voir'
    write_permission = 'juridique_gerer'

    def get_queryset(self):
        """Scope société (ARC2) + exclusion des dossiers confidentiels.

        Filtres optionnels : ``?statut=``, ``?nature=``, ``?type_procedure=``,
        ``?responsable_interne=``.
        """
        qs = super().get_queryset()
        user = self.request.user
        if not selectors.peut_voir_confidentiel(user):
            qs = qs.exclude(
                confidentialite=(
                    DossierJuridique.NiveauConfidentialite.CONFIDENTIEL))
        params = self.request.query_params
        for champ in ('statut', 'nature', 'type_procedure',
                      'responsable_interne', 'confidentialite'):
            valeur = params.get(champ)
            if valeur:
                qs = qs.filter(**{champ: valeur})
        return qs

    def perform_create(self, serializer):
        """Crée le dossier avec une référence anti-collision (``JUR-AAAA-NNNN``).

        La société est TOUJOURS celle de l'appelant (jamais lue du corps), et
        la référence passe par ``core.numbering`` — jamais ``count() + 1``.
        """
        from core.numbering import create_with_reference

        company = self.request.user.company
        create_with_reference(
            DossierJuridique, 'JUR', company,
            lambda reference: serializer.save(
                company=company, reference=reference,
                created_by=self.request.user),
            period='yearly')
