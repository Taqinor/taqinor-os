"""Vues (API) de l'app CPQ.

Tous les ViewSets héritent de ``CompanyScopedModelViewSet`` (ARC2) : le
queryset est scopé société et ``perform_create`` force ``company`` côté
serveur. La liste des produits n'est jamais lue du corps pour le scope."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers, status
from rest_framework.decorators import action
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from core.viewsets import CompanyScopedModelViewSet
from authentication.permissions import (
    IsResponsableOrAdmin, IsAnyRole, HasPermissionOrLegacy,
)

from .models import (
    OptionProduit, ContrainteCompatibilite, RegleProduitCPQ, OffreGroupee,
    PrixContractuel, QuestionConfigurateur, SessionConfigurateur,
    ReponseConfigurateur, SeuilMargeFamille, RegleApprobationRemise,
    ClauseCGV, ProduitEquivalent, ParametresCPQ,
)
from .serializers import (
    OptionProduitSerializer, ContrainteCompatibiliteSerializer,
    RegleProduitCPQSerializer, OffreGroupeeSerializer,
    PrixContractuelSerializer, QuestionConfigurateurSerializer,
    SeuilMargeFamilleSerializer, RegleApprobationRemiseSerializer,
    ClauseCGVSerializer, ProduitEquivalentSerializer,
    ParametresCPQSerializer,
)
from . import reports, selectors, services


class OptionProduitViewSet(CompanyScopedModelViewSet):
    queryset = OptionProduit.objects.all()
    serializer_class = OptionProduitSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class ContrainteCompatibiliteViewSet(CompanyScopedModelViewSet):
    queryset = ContrainteCompatibilite.objects.all()
    serializer_class = ContrainteCompatibiliteSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class RegleProduitCPQViewSet(CompanyScopedModelViewSet):
    queryset = RegleProduitCPQ.objects.all()
    serializer_class = RegleProduitCPQSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'evaluer'):
            return [IsAnyRole()]
        # NTCPQ36 — permission granulaire cpq_regles_gerer (repli légacy).
        return [HasPermissionOrLegacy('cpq_regles_gerer')()]

    @action(detail=False, methods=['post'], url_path='evaluer')
    def evaluer(self, request):
        """NTCPQ2 — Évalue les règles actives contre un contexte fourni.

        Corps : ``{"context": {...}}`` (dict plat construit depuis les lignes
        candidates du devis, ex. ``{"kwc": 12}``). Renvoie les actions
        déclenchées."""
        context = request.data.get('context')
        if context is None:
            # Repli : tout champ hors "context" est traité comme le contexte.
            context = {k: v for k, v in request.data.items() if k != 'context'}
        declenchees = selectors.evaluer_regles_produit(
            company=request.user.company, context=context)
        return Response({'actions_declenchees': declenchees})


class OffreGroupeeViewSet(CompanyScopedModelViewSet):
    queryset = OffreGroupee.objects.prefetch_related('lignes').all()
    serializer_class = OffreGroupeeSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    @action(detail=True, methods=['post'], url_path='appliquer',
            permission_classes=[IsResponsableOrAdmin])
    def appliquer(self, request, pk=None):
        """NTCPQ3 — Applique le bundle au devis ``?devis_id=`` : insère les
        LigneDevis correspondantes en respectant le mode de prix."""
        offre = self.get_object()
        devis_id = request.query_params.get('devis_id') or request.data.get('devis_id')
        if not devis_id:
            return Response({'detail': 'devis_id requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        from apps.ventes.models import Devis
        try:
            devis = Devis.objects.get(pk=devis_id, company=request.user.company)
        except Devis.DoesNotExist:
            return Response({'detail': 'Devis introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        lignes = services.appliquer_offre_groupee(
            offre=offre, devis=devis, user=request.user)
        return Response({
            'detail': f'Offre « {offre.nom} » appliquée.',
            'lignes_creees': [li.id for li in lignes],
            'sous_total_ht': str(devis.total_ht),
        }, status=status.HTTP_201_CREATED)


class PrixContractuelViewSet(CompanyScopedModelViewSet):
    queryset = PrixContractuel.objects.select_related(
        'client', 'produit').all()
    serializer_class = PrixContractuelSerializer
    # NTCPQ5 — CRUD réservé Directeur / Commercial responsable.
    permission_classes = [IsResponsableOrAdmin]

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        company = self.request.user.company
        client = serializer.validated_data.get('client')
        produit = serializer.validated_data.get('produit')
        if client is not None and client.company_id != company.id:
            raise ValidationError({'client': 'Client inconnu.'})
        if produit is not None and produit.company_id != company.id:
            raise ValidationError({'produit': 'Produit inconnu.'})
        serializer.save(company=company, created_by=self.request.user)

    def _verifier_auteur_ou_role_eleve(self, instance):
        """NTCPQ37 — un commercial ne peut modifier/supprimer QUE le
        PrixContractuel qu'il a lui-même créé ; au-delà, il faut la
        permission granulaire ``cpq_prix_contractuels_gerer`` (NTCPQ36,
        repli légacy inclus via ``HasPermissionOrLegacy``)."""
        from rest_framework.exceptions import PermissionDenied
        user = self.request.user
        if instance.created_by_id == user.id:
            return
        if HasPermissionOrLegacy('cpq_prix_contractuels_gerer')().has_permission(
                self.request, self):
            return
        raise PermissionDenied(
            "Seul l'auteur de ce prix contractuel (ou un rôle élevé) peut "
            "le modifier ou le supprimer.")

    def perform_update(self, serializer):
        instance = self.get_object()
        self._verifier_auteur_ou_role_eleve(instance)
        # NTCPQ46 — audit trail des changements de prix_ht (ancienne/nouvelle
        # valeur, auteur, société) via l'infrastructure d'audit GÉNÉRIQUE déjà
        # en prod (apps.audit.recorder) — aucun nouveau modèle.
        ancien_prix = instance.prix_ht
        serializer.save()
        nouveau_prix = serializer.instance.prix_ht
        if ancien_prix != nouveau_prix:
            from apps.audit import recorder
            recorder.record_field_change(
                serializer.instance, 'prix_ht', ancien_prix, nouveau_prix,
                user=self.request.user, field_label='Prix HT (contractuel)',
                # PrixContractuel n'est pas (encore) une cible chatter ARC30 —
                # seul l'AuditLog est visé par NTCPQ46 (écran d'audit staff).
                chatter=False)

    def perform_destroy(self, instance):
        self._verifier_auteur_ou_role_eleve(instance)
        instance.delete()


class QuestionConfigurateurViewSet(CompanyScopedModelViewSet):
    queryset = QuestionConfigurateur.objects.all()
    serializer_class = QuestionConfigurateurSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class SeuilMargeFamilleViewSet(CompanyScopedModelViewSet):
    """WIR105 — CRUD des seuils de marge par famille (NTCPQ6), pour un écran
    Paramètres CPQ (plus de dépendance au Django admin). Lecture tout rôle,
    écriture réservée Directeur / Commercial responsable."""
    queryset = SeuilMargeFamille.objects.select_related('categorie').all()
    serializer_class = SeuilMargeFamilleSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class RegleApprobationRemiseViewSet(CompanyScopedModelViewSet):
    """WIR105 — CRUD des paliers d'approbation par profondeur de remise
    (NTCPQ7/8), pour un écran Paramètres CPQ. Écriture réservée Directeur /
    Commercial responsable ; ces paliers pilotent l'approbation NTCPQ7/8
    résolue par ``services.resoudre_regle_remise``."""
    queryset = RegleApprobationRemise.objects.all()
    serializer_class = RegleApprobationRemiseSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class ClauseCGVViewSet(CompanyScopedModelViewSet):
    """NTCPQ11/12 — Bibliothèque de clauses/CGV réutilisables.

    Lecture tout rôle, écriture réservée Directeur / Commercial responsable :
    un admin crée/désactive une clause sans toucher au code. L'action
    ``tester`` évalue À BLANC la clause contre un devis existant — purement
    consultative, elle n'écrit RIEN (le snapshot ne se fige qu'à l'envoi)."""
    queryset = ClauseCGV.objects.all()
    serializer_class = ClauseCGVSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'tester'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    @action(detail=True, methods=['get', 'post'], url_path='tester')
    def tester(self, request, pk=None):
        """Test à blanc contre un devis existant de la société.

        ``?devis_id=`` (ou corps ``devis_id``). Renvoie
        ``{applicable, contexte, condition_lisible}`` sans rien persister."""
        clause = self.get_object()
        devis_id = (request.query_params.get('devis_id')
                    or request.data.get('devis_id'))
        if not devis_id:
            return Response({'detail': 'devis_id requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        from apps.ventes.models import Devis
        devis = Devis.objects.filter(
            pk=devis_id, company=request.user.company).first()
        if devis is None:
            return Response({'detail': 'Devis introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        from apps.ventes.services import contexte_clauses_devis
        contexte = contexte_clauses_devis(devis)
        return Response({
            'applicable': selectors.clause_sapplique(clause, contexte),
            'contexte': contexte,
            'condition_lisible':
                ClauseCGVSerializer(clause).data['condition_lisible'],
        })


class ProduitEquivalentViewSet(CompanyScopedModelViewSet):
    """NTCPQ16 — Règles de substitution produit par tier (moteur de variantes).
    Lecture tout rôle, écriture réservée Directeur / Commercial responsable."""
    queryset = ProduitEquivalent.objects.select_related(
        'produit_source', 'produit_substitut').all()
    serializer_class = ProduitEquivalentSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class ParametresCPQViewSet(CompanyScopedModelViewSet):
    """NTCPQ30 — Réglages CPQ, SINGLETON par société (pattern
    ``contrats.ParametresLocationViewSet``/ZCTR4).

    ``GET/PATCH cpq/parametres-cpq/courant/`` lit/modifie la ligne unique de
    la société (créée à la volée, ``get_or_create``) ; ``company`` posée
    CÔTÉ SERVEUR. Le CRUD standard reste disponible (scopé société) mais
    ``courant/`` est le point d'entrée recommandé côté frontend (jamais deux
    lignes par société — contrainte ``OneToOneField``)."""
    queryset = ParametresCPQ.objects.all()
    serializer_class = ParametresCPQSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'courant'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    @action(detail=False, methods=['get', 'patch'], url_path='courant')
    def courant(self, request):
        parametres, _ = ParametresCPQ.objects.get_or_create(
            company=request.user.company)
        if request.method == 'GET':
            return Response(ParametresCPQSerializer(parametres).data)
        if not IsResponsableOrAdmin().has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)
        serializer = ParametresCPQSerializer(
            parametres, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# Classe PARTAGEE (fabriquee UNE SEULE fois) : appeler inline_serializer()
# a nouveau creerait une deuxieme classe Python de meme nom, vue par
# drf-spectacular comme un composant en collision (« identical names,
# different identities »). GET et POST renvoient la MEME instance en liste
# (many=True) a partir de cette classe unique.
_CpqVarianteSerializer = inline_serializer('CpqVariante', {
    'devis_id': drf_serializers.IntegerField(),
    'reference': drf_serializers.CharField(),
    'tier': drf_serializers.CharField(),
    'statut': drf_serializers.CharField(),
    'total_ht': drf_serializers.CharField(),
}).__class__


class DevisVariantesView(APIView):
    """NTCPQ16 — ``cpq/devis/{id}/variantes/``.

    GET : liste les variantes déjà générées (tier + totaux HT).
    POST : (re)génère les variantes du devis par substitution de produits
    (corps optionnel ``{tiers: [...]}``). Moteur SEUL — la comparaison
    côte-à-côte est l'affaire de l'UI (FG212). Aucun PDF, aucun changement de
    statut."""

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def _devis(self, request, pk):
        from apps.ventes.models import Devis
        return Devis.objects.filter(
            pk=pk, company=request.user.company).first()

    @staticmethod
    def _payload(variantes):
        return [{
            'devis_id': v.id,
            'reference': v.reference,
            'tier': v.variante_tier,
            'statut': v.statut,
            'total_ht': str(v.total_ht),
        } for v in variantes]

    @extend_schema(responses=_CpqVarianteSerializer(many=True))
    def get(self, request, pk):
        devis = self._devis(request, pk)
        if devis is None:
            return Response({'detail': 'Devis introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(self._payload(
            devis.variantes_cpq.all().order_by('variante_tier', 'id')))

    @extend_schema(request=None,
                   responses={201: _CpqVarianteSerializer(many=True)})
    def post(self, request, pk):
        devis = self._devis(request, pk)
        if devis is None:
            return Response({'detail': 'Devis introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        variantes = services.generer_variantes_devis(
            devis, user=request.user, tiers=request.data.get('tiers'))
        return Response(self._payload(variantes),
                        status=status.HTTP_201_CREATED)


class _CsvOrJSONRenderer(JSONRenderer):
    """NTCPQ24 — même correctif que XGED22 (``apps/ged/views.py``) : DRF
    négocie le contenu sur ``?format=`` AVANT l'exécution de la vue
    (``DefaultContentNegotiation``, indépendant des ``format_suffix_patterns``)
    — sans renderer déclaré pour ``csv``, l'appel ``?format=csv`` échoue en
    amont avec un 404 (jamais notre ``HttpResponse`` renvoyée). On déclare
    donc explicitement ce format pour que la négociation aboutisse ; la vue
    renvoie ensuite un ``HttpResponse`` CSV manuel (jamais sérialisé par ce
    renderer — le JSON reste le comportement par défaut sans ``?format=csv``).
    """
    format = 'csv'
    media_type = 'text/csv'


class RapportConformiteView(APIView):
    """NTCPQ24 — GET ``cpq/rapports/conformite/?date_debut=&date_fin=
    &commercial_id=``.

    Rapport INTERNE (staff) du taux de conformité des configurations des devis
    envoyés sur la période. ``?format=csv`` renvoie une ligne par devis envoyé
    (référence, date, commercial, conformité) — export interne bureau d'études
    / direction commerciale, jamais un document client (aucun PDF, aucune
    donnée de marge)."""
    permission_classes = [IsResponsableOrAdmin]
    renderer_classes = [JSONRenderer, BrowsableAPIRenderer, _CsvOrJSONRenderer]

    COLONNES = ['reference', 'date_envoi', 'commercial', 'conforme',
                'bloquant', 'nb_violations']

    @extend_schema(responses={200: inline_serializer('CpqRapportConformite', {
        'total': drf_serializers.IntegerField(),
        'conformes': drf_serializers.IntegerField(),
        'non_conformes': drf_serializers.IntegerField(),
        'taux_conformite_pct': drf_serializers.FloatField(),
        'lignes': drf_serializers.ListField(child=inline_serializer(
            'CpqRapportConformiteLigne', {
                'devis_id': drf_serializers.IntegerField(),
                'reference': drf_serializers.CharField(),
                'date_envoi': drf_serializers.CharField(allow_null=True),
                'commercial': drf_serializers.CharField(allow_null=True),
                'conforme': drf_serializers.BooleanField(),
                'bloquant': drf_serializers.BooleanField(),
                'nb_violations': drf_serializers.IntegerField(),
            })),
    })})
    def get(self, request):
        rapport = reports.rapport_conformite_configurations(
            request.user.company,
            date_debut=request.query_params.get('date_debut') or None,
            date_fin=request.query_params.get('date_fin') or None,
            commercial_id=request.query_params.get('commercial_id') or None)
        if request.query_params.get('format') != 'csv':
            return Response(rapport)

        import csv
        from django.http import HttpResponse
        reponse = HttpResponse(content_type='text/csv; charset=utf-8')
        reponse['Content-Disposition'] = (
            'attachment; filename="conformite-configurations.csv"')
        writer = csv.DictWriter(
            reponse, fieldnames=self.COLONNES, extrasaction='ignore')
        writer.writeheader()
        for ligne in rapport['lignes']:
            writer.writerow({c: ligne.get(c) for c in self.COLONNES})
        return reponse


class MargeSousSeuilView(APIView):
    """NTCPQ23 — GET ``cpq/marge-sous-seuil/``.

    Tableau de bord CPQ INTERNE : devis en cours (non encore acceptés) dont au
    moins une ligne passe sous le seuil de marge de sa famille (NTCPQ6).
    Réservé aux rôles staff — ces données de marge ne quittent JAMAIS l'ERP
    (aucune sortie client, règle #4). Filtres : ``?commercial=`` et
    ``?famille=``."""
    permission_classes = [IsResponsableOrAdmin]

    @extend_schema(responses={200: inline_serializer('CpqMargeSousSeuil', {
        'devis': drf_serializers.ListField(child=drf_serializers.DictField()),
    })})
    def get(self, request):
        return Response({'devis': reports.devis_sous_seuil_marge(
            request.user.company,
            commercial_id=request.query_params.get('commercial'),
            famille=request.query_params.get('famille'))})


class FeuilleConfigurationView(APIView):
    """NTCPQ22 — GET ``cpq/devis/{id}/feuille-configuration/``.

    Export PDF INTERNE (bureau d'études) : configuration technique complète
    avec prix d'achat et marge par ligne. Réservé aux rôles staff
    (Directeur / Commercial responsable) et STRICTEMENT distinct du PDF client
    ``/proposal`` (règle #4) — jamais rendu par ``quote_engine``, jamais nommé
    « devis » ni « proposition ».

    ``?format=json`` renvoie les mêmes données sans rendre le PDF (usage écran
    interne / test). NTCPQ36 — réservé ``cpq_marge_voir`` (compte à rôle fin) :
    ce document porte le prix d'achat/la marge par ligne."""
    permission_classes = [HasPermissionOrLegacy('cpq_marge_voir')]

    @extend_schema(responses={200: OpenApiTypes.BINARY})
    def get(self, request, pk):
        from django.http import HttpResponse
        from apps.ventes.models import Devis
        devis = Devis.objects.filter(
            pk=pk, company=request.user.company).first()
        if devis is None:
            return Response({'detail': 'Devis introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        if request.query_params.get('format') == 'json':
            return Response(services.donnees_feuille_configuration(devis))
        pdf = services.generer_feuille_configuration_pdf(devis)
        reponse = HttpResponse(pdf, content_type='application/pdf')
        reponse['Content-Disposition'] = (
            'inline; filename="feuille-configuration-'
            f'{devis.reference}.pdf"')
        return reponse


class ImportPrixContractuelsCsvView(APIView):
    """NTCPQ41 — POST ``cpq/prix-contractuels/import-csv/``.

    Import CSV en masse de ``PrixContractuel`` (fichier multipart clé
    ``file``, ou corps texte brut ``text/csv``). Colonnes attendues :
    ``client_ref, produit_ref, prix_ht, date_debut, date_fin, motif``.
    Valide chaque ligne indépendamment — les lignes valides sont importées
    même si d'autres échouent, jamais un import « tout ou rien ». Réservé
    Directeur / Commercial responsable (même palier que la création directe
    NTCPQ5)."""
    permission_classes = [IsResponsableOrAdmin]

    @extend_schema(request=None, responses={200: inline_serializer(
        'CpqImportPrixContractuelsResultat', {
            'importees': drf_serializers.IntegerField(),
            'total': drf_serializers.IntegerField(),
            'erreurs': drf_serializers.ListField(
                child=drf_serializers.DictField()),
        })})
    def post(self, request):
        upload = request.FILES.get('file')
        if upload is not None:
            csv_text = upload.read().decode('utf-8-sig')
        else:
            csv_text = request.body.decode('utf-8-sig') if request.body else ''
        if not csv_text.strip():
            return Response({'detail': 'Fichier CSV requis (file, ou corps '
                                       'texte brut).'},
                            status=status.HTTP_400_BAD_REQUEST)
        resultat = services.importer_prix_contractuels_csv(
            request.user.company, csv_text, user=request.user)
        return Response(resultat)


class CatalogueReglesCompatibiliteView(APIView):
    """NTCPQ42 — GET ``cpq/rapports/catalogue-regles/?export=xlsx``.

    Export LECTURE SEULE (audit/revue hors-ligne bureau d'études) de
    ``ContrainteCompatibilite`` (NTCPQ1) et ``RegleProduitCPQ`` (NTCPQ2).
    Jamais un import inverse dans cette tâche (pas de risque d'écrasement
    accidentel de règles). ``?export=xlsx`` renvoie un classeur (une feuille
    par type de règle) — jamais ``?format=``, réservé par DRF."""
    permission_classes = [IsResponsableOrAdmin]

    @extend_schema(responses={200: inline_serializer(
        'CpqCatalogueReglesCompatibilite', {
            'contraintes': drf_serializers.ListField(
                child=drf_serializers.DictField()),
            'regles_produit': drf_serializers.ListField(
                child=drf_serializers.DictField()),
        })})
    def get(self, request):
        if request.query_params.get('export') == 'xlsx':
            return reports.catalogue_regles_compatibilite_xlsx(
                request.user.company)
        return Response(
            reports.catalogue_regles_compatibilite(request.user.company))


class RapportApprobationsView(APIView):
    """NTCPQ25 — GET ``cpq/rapports/approbations/?approbateur_id=&export=xlsx``.

    Rapport INTERNE (staff) de l'historique des approbations de remise
    (NTCPQ7) : devis, remise demandée, approbateur, délai de traitement
    (heures), motif de rejet. ``?export=xlsx`` renvoie un classeur (jamais
    ``?format=`` — réservé par la négociation de contenu DRF, motif NTCPQ24 ;
    jamais passé par ``apps/dataimport``, module hors périmètre de cette app
    — même patron auto-suffisant que ``apps.ventes.exports``, openpyxl
    directement)."""
    permission_classes = [IsResponsableOrAdmin]

    @extend_schema(responses={200: inline_serializer(
        'CpqRapportApprobations', {
            'lignes': drf_serializers.ListField(
                child=drf_serializers.DictField()),
        })})
    def get(self, request):
        lignes = reports.rapport_approbations(
            request.user.company,
            approbateur_id=request.query_params.get('approbateur_id') or None)
        if request.query_params.get('export') == 'xlsx':
            return reports.rapport_approbations_xlsx(lignes)
        return Response({'lignes': lignes})


class ComparaisonVariantesView(APIView):
    """NTCPQ26 — GET ``cpq/devis/{id}/comparaison-variantes/``.

    Export PDF interne (même famille que NTCPQ22, généré par ``apps.cpq``,
    jamais ``quote_engine``) listant côte à côte les variantes générées
    (NTCPQ16) d'un devis — 3 colonnes économique/standard/premium avec
    marge par colonne, outil de préparation d'entretien commercial, jamais
    transmis au client. ``?format=json`` renvoie les mêmes données sans
    rendre le PDF (usage écran interne / test)."""
    permission_classes = [IsResponsableOrAdmin]

    @extend_schema(responses={200: OpenApiTypes.BINARY})
    def get(self, request, pk):
        from django.http import HttpResponse
        from apps.ventes.models import Devis
        devis = Devis.objects.filter(
            pk=pk, company=request.user.company).first()
        if devis is None:
            return Response({'detail': 'Devis introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        if request.query_params.get('format') == 'json':
            return Response(services.donnees_comparaison_variantes(devis))
        pdf = services.generer_comparaison_variantes_pdf(devis)
        reponse = HttpResponse(pdf, content_type='application/pdf')
        reponse['Content-Disposition'] = (
            'inline; filename="comparaison-variantes-'
            f'{devis.reference}.pdf"')
        return reponse


class RelancerApprobationView(APIView):
    """NTCPQ28 — POST ``cpq/devis/{id}/relancer-approbation/``.

    Écran guidé CÔTÉ DEMANDEUR (jamais l'écran d'approbation NTCPQ8 lui-même,
    réservé à l'approbateur) : quand ``envoyer``/``generer-pdf`` est bloqué
    par NTCPQ7, le demandeur relance manuellement l'approbateur assigné
    (notification, throttlée à 1/24h — même marqueur que la relance
    automatique NTCPQ33). Ouvert à tout rôle interne (le demandeur n'est
    pas forcément Responsable/Admin)."""
    permission_classes = [IsAnyRole]

    def post(self, request, pk):
        from apps.ventes.models import Devis
        devis = Devis.objects.filter(
            pk=pk, company=request.user.company).first()
        if devis is None:
            return Response({'detail': 'Devis introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        etape, envoyee = services.relancer_etape_approbation(
            devis, user=request.user)
        detail = 'Relance envoyée.'
        if not envoyee:
            detail = 'Déjà relancée dans les dernières 24h.'
        return Response({
            'etape_id': etape.id,
            'niveau': etape.niveau,
            'approbateur': (
                getattr(etape.approbateur, 'username', None)
                if etape.approbateur_id else None),
            'relance_envoyee': envoyee,
            'detail': detail,
        })


class SuggestionsProduitView(APIView):
    """NTCPQ19 — GET ``cpq/suggestions/?produit_id=``.

    Jusqu'à 3 produits associés : d'abord les ``RECOMMANDE`` déclarés (NTCPQ1),
    puis les produits les plus fréquemment co-achetés dans les devis ACCEPTÉS
    de la société. Purement suggestif — aucune action automatique, aucun prix
    d'achat exposé."""
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: inline_serializer('CpqSuggestionsProduit', {
        'suggestions': drf_serializers.ListField(child=inline_serializer(
            'CpqSuggestionProduit', {
                'produit_id': drf_serializers.IntegerField(),
                'nom': drf_serializers.CharField(),
                'source': drf_serializers.CharField(),
                'occurrences': drf_serializers.IntegerField(),
            })),
    })})
    def get(self, request):
        produit_id = request.query_params.get('produit_id')
        if not produit_id:
            return Response({'detail': 'produit_id requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'suggestions': reports.suggestions_produit(
            company=request.user.company, produit_id=produit_id)})


class ConfigurateurDemarrerView(APIView):
    """NTCPQ9 — POST cpq/configurateur/demarrer/. Crée une session et renvoie
    le token + les questions actives de la société."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        company = request.user.company
        session = SessionConfigurateur.objects.create(company=company)
        questions = QuestionConfigurateur.objects.filter(
            company=company, actif=True).order_by('ordre', 'id')
        return Response({
            'session': str(session.token),
            'questions': QuestionConfigurateurSerializer(
                questions, many=True).data,
        }, status=status.HTTP_201_CREATED)


def _get_session(request, token):
    return SessionConfigurateur.objects.filter(
        token=token, company=request.user.company).first()


class ConfigurateurRepondreView(APIView):
    """NTCPQ9 — POST cpq/configurateur/{session}/repondre/. Enregistre une ou
    plusieurs réponses (upsert par question)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        session = _get_session(request, token)
        if session is None:
            return Response({'detail': 'Session introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        reponses = request.data.get('reponses')
        if reponses is None:
            reponses = [{
                'question': request.data.get('question')
                or request.data.get('question_id'),
                'valeur': request.data.get('valeur'),
            }]
        for r in reponses:
            qid = r.get('question')
            question = QuestionConfigurateur.objects.filter(
                id=qid, company=session.company).first()
            if question is None:
                continue
            ReponseConfigurateur.objects.update_or_create(
                session=session, question=question,
                defaults={'valeur': r.get('valeur')})
        session.save(update_fields=['updated_at'])
        return Response({'detail': 'Réponses enregistrées.'})


class ConfigurateurResultatView(APIView):
    """NTCPQ9 — GET cpq/configurateur/{session}/resultat/. Résout les produits/
    bundles correspondant aux réponses via le moteur de règles NTCPQ2."""
    permission_classes = [IsAuthenticated]

    def get(self, request, token):
        session = _get_session(request, token)
        if session is None:
            return Response({'detail': 'Session introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(selectors.resoudre_configurateur(session))


class ConfigurateurGenererDevisView(APIView):
    """NTCPQ10 — POST cpq/configurateur/{session}/generer-devis/.

    Transforme le résultat résolu en Devis brouillon (lignes + lead/client si
    fournis). Ne génère jamais le PDF. Corps : ``{lead?, client?}``."""
    permission_classes = [IsResponsableOrAdmin]

    def post(self, request, token):
        session = SessionConfigurateur.objects.filter(
            token=token, company=request.user.company).first()
        if session is None:
            return Response({'detail': 'Session introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        company = request.user.company
        lead = None
        client = None
        lead_id = request.data.get('lead')
        client_id = request.data.get('client')
        if lead_id:
            from apps.crm.selectors import get_company_lead
            lead = get_company_lead(company, lead_id)
            if lead is None:
                return Response({'detail': 'Lead introuvable.'},
                                status=status.HTTP_404_NOT_FOUND)
        if client_id:
            from apps.crm.selectors import get_company_client
            client = get_company_client(company, client_id)
            if client is None:
                return Response({'detail': 'Client introuvable.'},
                                status=status.HTTP_404_NOT_FOUND)
        devis = services.generer_devis_depuis_configurateur(
            session, user=request.user, lead=lead, client=client)
        return Response({
            'detail': 'Devis brouillon créé.',
            'devis_id': devis.id,
            'reference': devis.reference,
        }, status=status.HTTP_201_CREATED)


class ValiderCompatibiliteView(APIView):
    """NTCPQ1 — POST cpq/valider-compatibilite/.

    Corps : ``{"produit_ids": [1, 2, 3]}``. Renvoie les violations, séparées en
    ``bloquantes`` (INCOMPATIBLE / REQUIERT) et ``avertissements`` (RECOMMANDE)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        company = request.user.company
        produit_ids = request.data.get('produit_ids') or []
        if not isinstance(produit_ids, (list, tuple)):
            return Response(
                {'detail': 'produit_ids doit être une liste.'},
                status=status.HTTP_400_BAD_REQUEST)
        violations = selectors.violations_compatibilite(
            company=company, produit_ids=produit_ids)
        bloquantes = [v for v in violations if v['bloquante']]
        avertissements = [v for v in violations if not v['bloquante']]
        return Response({
            'valide': not bloquantes,
            'violations': violations,
            'bloquantes': bloquantes,
            'avertissements': avertissements,
        })
