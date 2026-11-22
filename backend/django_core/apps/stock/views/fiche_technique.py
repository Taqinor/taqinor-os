from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import UnsupportedMediaType
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework import serializers
from ..openapi_helpers import INT, OBJET, P, corps
from core.viewsets import CompanyScopedModelViewSet
from ..importers.fiche_pan_ond import FichierIllisible, champs_a_ecrire, parse_pan_ond_bytes
from ..models import FicheTechnique, Produit
from ..erreurs_achats import ConflitEtat
from ..serializers_fiche_technique import CODE_REFUS_ETAT, FicheTechniqueSerializer
from authentication.permissions import (
    LectureDuModule,
    IsAdminRole,
    HasPermissionOrLegacy,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


#: api-fuzz stock (vague 8) — seul le PDF constructeur voyage en multipart
#: (``uploadFicheTechniquePdf`` du front) : les objets/listes JSON de la fiche
#: (``struct_notice``, ``lim_marques``…) n'ont aucune forme multipart lisible.
FichePdfCorps = corps('FichePdfCorps', pdf=serializers.FileField())


def _ecart_pmax_societe(company):
    """ACAL657 — le seuil société ``fiche_ecart_pmax_pct`` (section
    ``electrique_societe`` du calepinage), ou ``None`` quand il n'est pas saisi."""
    from apps.calepinage.selectors import parametres_de_societe
    from apps.calepinage.services.limites_livraison import ecart_pmax_societe

    return ecart_pmax_societe(parametres_de_societe(company).get('electrique_societe'))


@extend_schema_view(
    list=extend_schema(parameters=[P('produit', INT)]),
    create=extend_schema(request={'application/json': FicheTechniqueSerializer}),
    update=extend_schema(request={'application/json': FicheTechniqueSerializer}),
    partial_update=extend_schema(request={
        'application/json': FicheTechniqueSerializer,
        'multipart/form-data': FichePdfCorps}),
)
class FicheTechniqueViewSet(CompanyScopedModelViewSet):
    """DC35 / FG254 — fiches techniques (datasheets) rattachées aux produits.

    Multi-tenant : le queryset est filtré sur la société du demandeur
    (``TenantMixin``) et ``company`` est forcé serveur dans ``perform_create``
    — jamais accepté depuis le corps de la requête. Lecture tout rôle, écriture
    selon la permission stock, suppression admin."""
    queryset = FicheTechnique.objects.select_related('produit').all()
    serializer_class = FicheTechniqueSerializer
    filter_backends = [filters.OrderingFilter]
    ordering = ['-date_mise_a_jour']
    # YAPIC2 — whitelist explicite (jamais '__all__').
    ordering_fields = ['date_creation', 'date_mise_a_jour', 'pmax_wc']
    # api-fuzz stock (vague 8) : plus de formulaire urlencodé (415) ; le
    # multipart ne sert qu'au PDF (PATCH) et à ``importer-datasheet``.
    parser_classes = [JSONParser, MultiPartParser]

    def initial(self, request, *args, **kwargs):
        """Création / remplacement complet (POST, PUT) : JSON seul — un
        multipart y est refusé 415 (``struct_notice`` y arrivait en texte
        « None », 400 sur un corps conforme). Posé ici et non dans
        ``create``/``update`` : la forme servie reste celle du sérialiseur
        (lisible par ``check_api_shapes``)."""
        super().initial(request, *args, **kwargs)
        if (self.action in ('create', 'update')
                and (request.content_type or '').lower().startswith('multipart/')):
            raise UnsupportedMediaType(request.content_type)

    def handle_exception(self, exc):
        """Refus d'état du sérialiseur (code ``refus_etat`` : courbe non croissante,
        masse sans notice), seul ou avec un doublon (``unique``) → 409 ; toute
        autre erreur de corps reste 400."""
        if isinstance(exc, serializers.ValidationError):
            codes = _codes(exc.get_codes())
            if CODE_REFUS_ETAT in codes and codes <= {CODE_REFUS_ETAT, 'unique'}:
                exc = ConflitEtat(exc.detail)
        return super().handle_exception(exc)

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [LectureDuModule()]  # APFS109
        elif self.action in WRITE_ACTIONS:
            return [HasPermissionOrLegacy('stock_modifier')()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        from ..utils.params import id_requete_ou_400
        produit_id = id_requete_ou_400(self.request, 'produit')
        if produit_id:
            qs = qs.filter(produit_id=produit_id)
        return qs

    @extend_schema(request={'multipart/form-data': corps('FicheImporterDatasheetCorps',
                                                         produit=serializers.IntegerField(),
                                                         file=serializers.FileField(),
                                                         confirmer=serializers.BooleanField(required=False))},
                   responses=OBJET)
    @action(detail=False, methods=['post'], url_path='importer-datasheet')  # écran : ImportFichePvsyst (CALX357)
    def importer_datasheet(self, request):
        """CAL117 — import OPTIONNEL d'une fiche constructeur .PAN/.OND.

        Sans ``confirmer=true`` (ou par défaut) : APERÇU seul, aucune
        écriture — rend le mapping proposé, les clés reconnues/non reconnues
        et celles déjà saisies (donc qui seraient IGNORÉES à la
        confirmation). Avec ``confirmer=true`` : écrit UNIQUEMENT les champs
        encore vides de la fiche (crée la fiche si le produit n'en a pas
        encore) — un champ déjà saisi n'est JAMAIS écrasé."""
        upload = request.FILES.get('file')
        produit_id = request.data.get('produit')
        if upload is None or not produit_id:
            return Response(
                {'detail': 'produit et file sont requis.',
                 'champ': 'file' if upload is None else 'produit'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            produit_id = int(produit_id)
        except (TypeError, ValueError):
            return Response(
                {'detail': 'produit doit être un identifiant entier.',
                 'champ': 'produit'},
                status=status.HTTP_400_BAD_REQUEST)
        produit = Produit.objects.filter(
            pk=produit_id, company=request.user.company).first()
        if produit is None:
            return Response(
                {'detail': 'Produit introuvable.', 'champ': 'produit'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            proposition = parse_pan_ond_bytes(
                upload.read(), filename=getattr(upload, 'name', '') or '',
                ecart_pmax_pct=_ecart_pmax_societe(request.user.company))
        except FichierIllisible as exc:
            # CALX356 — le refus nomme la ligne fautive quand il y en a une.
            return Response(
                {'detail': str(exc), 'champ': exc.champ, 'ligne': exc.ligne},
                status=status.HTTP_400_BAD_REQUEST)
        if proposition.refus:
            # ACAL657 — fiche incohérente : refusée, rien n'est proposé.
            return Response(
                {'detail': proposition.refus, 'champ': 'file', 'ligne': None},
                status=status.HTTP_400_BAD_REQUEST)

        # CALX356 — l'aperçu montre la valeur TELLE QU'ELLE SERA ENREGISTRÉE
        # (décimales du champ, entier pour un champ entier), jamais un arrondi
        # fait plus tard en silence par la base.
        mapping = {champ: _au_format_du_champ(champ, valeur)
                   for champ, valeur in proposition.mapping.items()}
        fiche = getattr(produit, 'fiche_technique', None)
        if fiche is not None:
            a_ecrire, deja_saisis = champs_a_ecrire(fiche, mapping)
        else:
            a_ecrire, deja_saisis = dict(mapping), []

        # CI #997 fuzz (2) : true/false seulement (``0``/``oui`` -> 400).
        from ..utils.params import booleen_formulaire_ou_400
        confirmer = booleen_formulaire_ou_400(request.data, 'confirmer')
        if not confirmer:
            return Response({
                'type_fiche': proposition.type_fiche,
                'mapping': {k: str(v) for k, v in a_ecrire.items()},
                'reconnus': proposition.reconnus,
                'non_reconnus': proposition.non_reconnus,
                'champs_attendus_absents': proposition.champs_attendus_absents,
                'deja_saisis': deja_saisis,
                # ACAL1081 — contrat posé seul : refus (ACAL657) et conversions
                # (ACAL658) se remplissent avec leur producteur.
                'refus': proposition.refus,
                'conversions': proposition.conversions,
                # REP-657 — contrôles non faits, dits à l'écran.
                'controles_omis': proposition.controles_omis,
                'confirme': False,
            })

        if fiche is None:
            fiche = FicheTechnique(
                company=request.user.company, produit=produit,
                type_fiche=proposition.type_fiche)
        for champ_nom, valeur in a_ecrire.items():
            setattr(fiche, champ_nom, valeur)
        fiche.save()
        return Response({
            'type_fiche': proposition.type_fiche,
            'ecrits': sorted(a_ecrire.keys()),
            'deja_saisis': deja_saisis,
            'non_reconnus': proposition.non_reconnus,
            'champs_attendus_absents': proposition.champs_attendus_absents,
            'refus': proposition.refus,
            'conversions': proposition.conversions,
            'controles_omis': proposition.controles_omis,
            'confirme': True,
            'fiche': FicheTechniqueSerializer(fiche).data,
        })


def _au_format_du_champ(champ, valeur):
    """CALX356 — ``valeur`` au format de stockage du champ ``FicheTechnique``
    (décimales du ``DecimalField`` arrondies au demi supérieur, entier pour un
    champ entier) ; tout autre champ inchangé."""
    from decimal import ROUND_HALF_UP, Decimal
    from django.db import models as dj_models
    modele = FicheTechnique._meta.get_field(champ)
    if isinstance(modele, dj_models.DecimalField):
        pas = Decimal(1).scaleb(-modele.decimal_places)
        return Decimal(valeur).quantize(pas, rounding=ROUND_HALF_UP)
    if isinstance(modele, dj_models.IntegerField):
        return int(Decimal(valeur).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return valeur


def _codes(codes):
    """Ensemble des codes d'erreur DRF, aplati (dict / liste imbriqués)."""
    if isinstance(codes, dict):
        return set().union(*(_codes(v) for v in codes.values())) if codes else set()
    if isinstance(codes, (list, tuple)):
        return set().union(*(_codes(v) for v in codes)) if codes else set()
    return {codes}
