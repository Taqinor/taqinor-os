"""Vues du répertoire ``Tiers`` (ARC17) — CRUD scopé société.

Le viewset filtre par ``request.user.company`` (``TenantMixin.get_queryset``)
et FORCE la société côté serveur à la création (``perform_create``) — jamais
lue du corps de requête. ``tiers`` étant une couche fondation, ce module
n'importe AUCUNE app de domaine.
"""
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.settings import api_settings

from authentication.permissions import IsAdminRole
from core.mixins import TenantMixin
from core.permissions import WriteScopedPermissionMixin

from . import selectors
from .models import Tiers
from .serializers import TiersSerializer


class TiersViewSet(
        WriteScopedPermissionMixin, TenantMixin, viewsets.ModelViewSet):
    """CRUD du répertoire des tiers (parties prenantes), scopé société.

    Lecture/écriture : tout utilisateur authentifié de la société (répertoire
    de fondation, aucune permission fine dédiée pour l'instant — le repli
    légacy reste géré par ``ScopedPermission``). L'isolation multi-société est
    garantie par ``TenantMixin`` (queryset filtré + société forcée à la
    création).
    """
    queryset = Tiers.objects.all()
    serializer_class = TiersSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'nom', 'prenom', 'raison_sociale', 'email', 'telephone',
        'ice', 'rc', 'identifiant_fiscal', 'cin',
    ]
    ordering_fields = ['nom', 'prenom', 'date_creation']
    ordering = ['nom', 'prenom']
    # Répertoire de fondation : aucune permission fine dédiée — authentifié
    # + scopé société suffit (le repli légacy reste géré par ScopedPermission).
    read_permission = None
    write_permission = None

    def perform_destroy(self, instance):
        """AUD609 — un tiers RÉFÉRENCÉ par une pièce comptable ne s'efface pas.

        Le répertoire est une couche de FONDATION : les apps aval le
        référencent par ``tiers_id`` — un entier NU, sans contrainte de clé
        étrangère (``compta`` ne peut pas importer ``tiers``, et le pont est
        volontairement additif). La base ne pouvait donc RIEN refuser : un
        DELETE laissait des ``tiers_id`` orphelins dans des écritures, des
        cautions bancaires, des retenues de garantie… c'est-à-dire des pièces
        comptables pointant un tiers qui n'existe plus.

        La détection est GÉNÉRIQUE (elle interroge le registre des modèles
        installés, jamais un import d'app de domaine) : `tiers` continue de ne
        connaître aucun de ses consommateurs.
        """
        references = selectors.references_pseudo_fk(instance)
        if references:
            raise ValidationError({api_settings.NON_FIELD_ERRORS_KEY: [
                'Suppression refusée : ce tiers est référencé par %s. '
                'Supprimer la fiche laisserait ces pièces pointer un tiers '
                'inexistant — désactivez-la ou reprenez les pièces d\'abord.'
                % ', '.join('%s (%d)' % (libelle, nombre)
                            for libelle, nombre in references)]})
        super().perform_destroy(instance)

    @action(detail=False, methods=['get'],
            permission_classes=[IsAdminRole])
    def doublons(self, request):
        """ARC20 — Rapport LECTURE SEULE des doublons inter-référentiels de la
        société de l'utilisateur : le même ICE/email porté par plusieurs fiches
        ``Tiers`` (ex. un acteur à la fois Fournisseur et Partenaire). Réservé
        aux administrateurs. AUCUNE fusion, aucune écriture. Company-scopé
        (jamais les tiers d'une autre société). Renvoie ``{count, clusters}``."""
        clusters = selectors.find_duplicates(request.user.company)
        return Response({'count': len(clusters), 'clusters': clusters})

    @action(detail=False, methods=['get'], url_path='verifier-doublon')
    def verifier_doublon(self, request):
        """AUDV22 (DRAFT165-123/124, ARC20) — recherche EXACTE anti-doublon
        par ICE et/ou email, en COMPLÉMENT de la recherche floue existante
        (autocomplete). Appelée AVANT la création d'un Client/Fournisseur
        depuis le formulaire réel — jamais bloquant, un simple avertissement
        laissé à l'appelant. Company-scopé. Query params ``ice``/``email``
        (au moins un requis)."""
        ice = (request.query_params.get('ice') or '').strip()
        email = (request.query_params.get('email') or '').strip()
        if not ice and not email:
            return Response(
                {'detail': 'Le paramètre ice ou email est requis.'},
                status=status.HTTP_400_BAD_REQUEST)

        def _serialize(qs):
            return [
                {
                    'id': t.id,
                    'nom': t.nom_complet,
                    'roles': {
                        'client': t.is_client,
                        'fournisseur': t.is_fournisseur,
                        'partenaire': t.is_partenaire,
                        'soustraitant': t.is_soustraitant,
                    },
                }
                for t in qs
            ]
        company = request.user.company
        return Response({
            'ice_matches': _serialize(selectors.find_by_ice(company, ice)),
            'email_matches': _serialize(selectors.find_by_email(company, email)),
        })
