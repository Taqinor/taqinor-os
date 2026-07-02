"""Vue DC34 — annuaire des sous-traitants chantier (référentiel UNIFIÉ).

Un sous-traitant N'EST PLUS un modèle parallèle : c'est un
``stock.Fournisseur`` de type « service » porteur d'un ``SousTraitantProfile``.
``SousTraitantViewSet`` reste l'endpoint ``sous-traitants/`` (contrat d'API
FG304 préservé) mais orchestre le couple Fournisseur/profil à travers les
SÉLECTEURS et SERVICES de l'app stock — jamais par import de
``apps.stock.models`` (contrat de découplage M1).

Lecture tout rôle, écriture responsable/admin. Multi-tenant : la société est
toujours posée côté serveur (fournisseur ET profil), jamais lue du corps.
Filtrable par ``metier`` et ``actif`` ; recherche sur la raison sociale (nom du
fournisseur) et l'ICE.
"""
from rest_framework import status, viewsets
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from apps.stock import selectors as stock_selectors
from apps.stock import services as stock_services

from ..serializers import SousTraitantSerializer

READ_ACTIONS = ['list', 'retrieve']


class SousTraitantViewSet(viewsets.ViewSet):
    """DC34 — annuaire des sous-traitants (Fournisseur type=service + profil).
    Lecture tout rôle, écriture responsable/admin. Société posée côté serveur.
    Filtrable par ``metier`` et ``actif`` ; recherche ``?search=`` sur la raison
    sociale et l'ICE."""
    serializer_class = SousTraitantSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _company(self):
        return self.request.user.company

    def _queryset(self):
        params = self.request.query_params
        metier = params.get('metier') or None
        actif = None
        raw_actif = params.get('actif')
        if raw_actif is not None and raw_actif != '':
            actif = raw_actif.lower() in ('1', 'true', 'oui', 'yes')
        qs = stock_selectors.sous_traitants_qs(
            self._company(), metier=metier, actif=actif)
        search = params.get('search')
        if search:
            from django.db.models import Q
            qs = qs.filter(Q(nom__icontains=search) | Q(ice__icontains=search))
        return qs

    def _get_object(self, pk):
        return stock_selectors.get_sous_traitant(self._company(), pk)

    # ── Actions REST ─────────────────────────────────────────────────────────
    def list(self, request):
        qs = list(self._queryset())
        data = SousTraitantSerializer(qs, many=True).data
        # Réponse paginée-compatible (les tests lisent `count`/`results`).
        return Response({'count': len(data), 'next': None, 'previous': None,
                         'results': data})

    def retrieve(self, request, pk=None):
        obj = self._get_object(pk)
        if obj is None:
            return Response(
                {'detail': 'Sous-traitant introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        return Response(SousTraitantSerializer(obj).data)

    def create(self, request):
        serializer = SousTraitantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        fournisseur = stock_services.create_sous_traitant(
            company=self._company(), user=request.user,
            nom=vd['raison_sociale'], metier=vd.get('metier', 'autre'),
            contact_personne=vd.get('contact_nom'), email=vd.get('email'),
            telephone=vd.get('telephone'), adresse=vd.get('adresse'),
            ice=vd.get('ice'), rib=vd.get('rib'),
            actif=vd.get('actif', True), note=vd.get('note'))
        return Response(SousTraitantSerializer(fournisseur).data,
                        status=status.HTTP_201_CREATED)

    def _update(self, request, pk, partial):
        obj = self._get_object(pk)
        if obj is None:
            return Response(
                {'detail': 'Sous-traitant introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        serializer = SousTraitantSerializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        identity = {}
        if 'raison_sociale' in vd:
            identity['nom'] = vd['raison_sociale']
        for src, dst in (('contact_nom', 'contact_personne'),
                         ('email', 'email'), ('telephone', 'telephone'),
                         ('adresse', 'adresse'), ('ice', 'ice'),
                         ('rib', 'rib')):
            if src in vd:
                identity[dst] = vd[src]
        stock_services.update_sous_traitant(
            fournisseur=obj, metier=vd.get('metier'), actif=vd.get('actif'),
            note=vd.get('note'), **identity)
        obj = self._get_object(pk)
        return Response(SousTraitantSerializer(obj).data)

    def update(self, request, pk=None):
        return self._update(request, pk, partial=False)

    def partial_update(self, request, pk=None):
        return self._update(request, pk, partial=True)
