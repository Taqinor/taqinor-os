"""WIR66 — ViewSets des référentiels société (TVA / conditions / unités).

Les trois référentiels (ARC23/24/27) sont seedés à la création de société mais
n'avaient aucune exposition REST : cet écran les rend consultables/éditables.

  * Lecture (``list``/``retrieve``) : tout rôle (``IsAnyRole``) — le générateur
    de devis / la fiche produit doivent lire les libellés.
  * Écriture (``create``/``update``/``partial_update``/``destroy`` + actions) :
    Administrateur ou Responsable promu (``IsAdminOrResponsableTier``) — jamais
    le palier limité.

``company`` est filtrée et forcée côté serveur (``TenantMixin``) — jamais lue
du corps. Aucune clé canonique (code TVA/unité) ne migre (garde au sérialiseur).
"""
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAdminOrResponsableTier, IsAnyRole
from core.viewsets import CompanyScopedModelViewSet

from .models_payment_terms import ConditionPaiement
from .models_relance import Cadence, CadenceRelanceEtape
from .models_taxes import TauxTVA
from .models_units import UniteMesure
from .serializers_referentiels import (
    CadenceRelanceEtapeSerializer,
    ConditionPaiementSerializer,
    TauxTVASerializer,
    UniteMesureSerializer,
)

READ_ACTIONS = ['list', 'retrieve']


class _ReferentielViewSet(CompanyScopedModelViewSet):
    """Base commune : lecture ouverte, écriture réservée admin/responsable."""

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminOrResponsableTier()]


class TauxTVAViewSet(_ReferentielViewSet):
    """Référentiel des taux de TVA (ARC23). ``?actif=true`` pour filtrer."""

    queryset = TauxTVA.objects.all()
    serializer_class = TauxTVASerializer

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif in ('true', '1'):
            qs = qs.filter(actif=True)
        return qs

    @action(detail=True, methods=['post'])
    def set_defaut(self, request, pk=None):
        """Désigne ce taux comme STANDARD par défaut (un seul par société).

        Bascule ``defaut`` sur la ligne visée et le retire de toutes les autres
        de la même société — garantit l'unicité que ``default_taux`` suppose.
        """
        taux = self.get_object()
        company = taux.company
        TauxTVA.objects.filter(company=company, defaut=True).exclude(
            pk=taux.pk).update(defaut=False)
        if not taux.defaut:
            taux.defaut = True
            taux.save(update_fields=['defaut'])
        return Response(self.get_serializer(taux).data)


class ConditionPaiementViewSet(_ReferentielViewSet):
    """Référentiel des conditions de paiement (ARC24). ``?actif=true``."""

    queryset = ConditionPaiement.objects.all()
    serializer_class = ConditionPaiementSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif in ('true', '1'):
            qs = qs.filter(actif=True)
        return qs


class UniteMesureViewSet(_ReferentielViewSet):
    """Référentiel des unités de mesure (ARC27). ``?actif=true``."""

    queryset = UniteMesure.objects.all()
    serializer_class = UniteMesureSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif in ('true', '1'):
            qs = qs.filter(actif=True)
        return qs


class CadenceRelanceEtapeViewSet(_ReferentielViewSet):
    """RELANCE FOUNDATION — gabarit de cadence de relance par défaut
    (délai/canal/libellé), consommé par
    ``apps.crm.services.initialiser_plan_relance``. ``?actif=true``.

    MRY4 — ``?cadence=contact|apres_devis|reveil|generique`` filtre sur UNE
    cadence : c'est l'onglet de l'éditeur de Paramètres → CRM. Sans le
    paramètre, la liste reste celle de toutes les cadences (comportement
    d'avant, jamais une restriction implicite).

    MRY28 — les cadences nommées (``apres_devis``/``reveil``) n'étaient
    seedées qu'à leur premier USE (``CadenceRelanceEtape.cadence_pour``,
    appelé côté lead) : sur une société existante qui n'avait encore jamais
    initialisé l'une d'elles, l'onglet correspondant de cet éditeur
    affichait « Aucune étape pour cette cadence. » sans aucun moyen d'en
    sortir. Un ``?cadence=`` dont la société n'a AUCUNE ligne seede
    maintenant le gabarit ICI, à la lecture — idempotent et additif comme
    ``seed_cadence`` lui-même, jamais une ré-écriture d'un barreau déjà
    personnalisé."""

    queryset = CadenceRelanceEtape.objects.all()
    serializer_class = CadenceRelanceEtapeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif in ('true', '1'):
            qs = qs.filter(actif=True)
        cadence = (self.request.query_params.get('cadence') or '').strip()
        if cadence:
            if cadence not in Cadence.values:
                raise ValidationError(
                    {'cadence': 'Cadence inconnue. Choisir parmi : '
                                + ', '.join(Cadence.values) + '.'})
            qs = qs.filter(cadence=cadence)
            company = (self.request.user.company
                       if self.request.user.company_id else None)
            if company is not None and not qs.exists():
                CadenceRelanceEtape.seed_cadence(company, cadence)
        return qs
