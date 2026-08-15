"""NTEXT10 — API du report-builder : définitions de rapport croisé sauvegardées.

CRUD scopé société (``core.viewsets.CompanyScopedModelViewSet``) + un
``POST …/rapport-definitions/<id>/executer/`` qui REJOUE la définition :

  1. ``core.data_explorer.run_query(dataset, company, user, spec)`` — la portée
     société est portée par le ``queryset_provider`` du dataset (déjà scopé),
     jamais reconstruite ici ;
  2. si la définition porte un ``pivot_spec``, ``core.pivot.build_pivot`` croise
     le résultat plat (transformation PURE, sans accès base).

Aucune importation d'app métier : le lien au domaine est le NOM du dataset,
résolu par le noyau — même frontière que ``core.SavedQuery``.
"""
from django.db.models import Q
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.viewsets import CompanyScopedModelViewSet

from .models import RapportDefinition


class RapportDefinitionSerializer(serializers.ModelSerializer):
    partage_label = serializers.CharField(
        source='get_partage_display', read_only=True)
    owner_username = serializers.CharField(
        source='owner.username', read_only=True, default='')

    class Meta:
        model = RapportDefinition
        # company + owner sont posés CÔTÉ SERVEUR — jamais lus du corps.
        fields = [
            'id', 'titre', 'dataset', 'spec', 'pivot_spec', 'partage',
            'partage_label', 'owner_username', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'partage_label', 'owner_username', 'created_at',
            'updated_at',
        ]

    def validate_dataset(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Le dataset est requis.')
        return value


class RapportDefinitionViewSet(CompanyScopedModelViewSet):
    """CRUD + exécution des définitions de rapport, bornés à la société.

    Visibilité : ses propres rapports + ceux partagés à la société (même
    modèle personnel/société que ``core.SavedQuery``). Le filtre société de
    ``CompanyScopedModelViewSet`` reste appliqué en premier — un rapport
    ``societe`` ne franchit JAMAIS la frontière du tenant.
    """
    serializer_class = RapportDefinitionSerializer
    queryset = RapportDefinition.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        return qs.filter(
            Q(owner=user)
            | Q(partage=RapportDefinition.Partage.SOCIETE)
            | Q(owner__isnull=True)
        ).distinct()

    # NTEXT36 — audit plateforme. L'aide est importée PARESSEUSEMENT (dans la
    # méthode) pour ne pas créer d'arête d'import au chargement du module :
    # ce fichier reste sans dépendance d'app métier en tête de fichier.
    def _audit_plateforme(self, identifiant, libelle, old=None, new=None):
        from apps.customfields.audit_plateforme import journaliser_plateforme

        utilisateur = self.request.user
        journaliser_plateforme(
            company=getattr(utilisateur, 'company', None), user=utilisateur,
            cible='rapport', identifiant=identifiant,
            libelle=libelle, old=old, new=new)

    def perform_create(self, serializer):
        # company forcée côté serveur (socle) ; owner = utilisateur courant.
        serializer.save(company=self.request.user.company,
                        owner=self.request.user)
        self._audit_plateforme(
            serializer.instance.pk, 'Définition de rapport créée',
            old=None, new=serializer.instance.titre)

    def perform_update(self, serializer):
        avant = serializer.instance.titre
        super().perform_update(serializer)
        self._audit_plateforme(
            serializer.instance.pk, 'Définition de rapport modifiée',
            old=avant, new=serializer.instance.titre)

    def perform_destroy(self, instance):
        avant, identifiant = instance.titre, instance.pk
        super().perform_destroy(instance)
        self._audit_plateforme(
            identifiant, 'Définition de rapport supprimée',
            old=avant, new=None)

    def perform_content_negotiation(self, request, force=False):
        # NTEXT11 — ``export()`` réutilise ``?format=csv|xlsx`` pour choisir
        # le format du FICHIER exporté, mais DRF réserve CE MÊME nom de
        # paramètre pour choisir le RENDERER de la réponse
        # (``URL_FORMAT_OVERRIDE``). Sans court-circuit, la négociation de
        # contenu — qui tourne dans ``APIView.initial()``, AVANT d'atteindre
        # ``export()`` — échoue en ``Http404`` dès qu'aucun renderer « csv »/
        # « xlsx » n'est enregistré (seuls JSON/Browsable le sont ici).
        # ``export()`` répond TOUJOURS par un ``HttpResponse`` brut (jamais
        # un ``Response`` DRF) : le renderer négocié n'est donc jamais
        # utilisé pour cette action, on peut la court-circuiter sans risque.
        if self.action == 'export':
            from rest_framework.renderers import JSONRenderer
            return (JSONRenderer(), 'application/json')
        return super().perform_content_negotiation(request, force=force)

    @action(detail=True, methods=['post'], url_path='executer')
    def executer(self, request, pk=None):
        """Rejoue la définition et renvoie ``{rows}`` (+ ``pivot`` si demandé)."""
        from core import data_explorer
        from core.formula import FormulaError
        from core.pivot import PivotSpec, build_pivot

        obj = self.get_object()
        try:
            rows = data_explorer.run_query(
                obj.dataset, request.user.company, request.user,
                obj.spec or {})
        except data_explorer.DatasetInconnu as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_404_NOT_FOUND)
        except (data_explorer.ChampNonAutorise, FormulaError) as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)

        pivot_spec = obj.pivot_spec or {}
        # Sans ``pivot_spec`` : résultat PLAT, la clé ``pivot`` reste ABSENTE
        # (comportement inchangé, affirmé par le test backend). Les deux formes
        # sont écrites en LITTÉRAL — une clé posée dynamiquement est invisible
        # à `scripts/check_api_shapes.py`, qui déclarait alors « le serveur ne
        # renvoie aucun champ pivot » à l'écran qui l'affiche pourtant.
        if not pivot_spec:
            return Response({'rows': rows})

        try:
            spec = PivotSpec(**pivot_spec)
        except (TypeError, ValueError) as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            pivot = build_pivot(rows, spec)
        except FormulaError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'rows': rows, 'pivot': pivot})

    @action(detail=True, methods=['get'], url_path='export')
    def export(self, request, pk=None):
        """NTEXT11 — export ``?format=csv|xlsx`` de la définition rejouée.

        RÉUTILISE l'infra d'export déjà en place pour les abonnements
        (``rapport_abonnements`` : mêmes aplatissements plat/croisé, même
        constructeur xlsx partagé ``apps.records.xlsx``) — aucun second moteur
        de rendu. Un rapport croisé sort avec ses totaux de ligne et de
        colonne ; un rapport plat avec ses en-têtes de champ.

        GARDE PRIX D'ACHAT : toute colonne dont le nom trahit un prix d'achat
        ou une marge est RETIRÉE du fichier (jamais d'export client-facing
        d'une donnée de marge, règle du repo), quelle que soit la définition.
        """
        import csv
        import io

        from django.http import HttpResponse

        from core import data_explorer
        from core.formula import FormulaError

        from .rapport_abonnements import (
            _lignes_pivot, _lignes_plates, executer_definition,
        )

        obj = self.get_object()
        fmt = (request.query_params.get('format') or 'csv').strip().lower()
        if fmt not in ('csv', 'xlsx'):
            return Response(
                {'detail': "Format non supporté : utilisez « csv » ou "
                           "« xlsx »."},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            rows, pivot = executer_definition(obj)
        except data_explorer.DatasetInconnu as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_404_NOT_FOUND)
        except (data_explorer.ChampNonAutorise, FormulaError,
                TypeError, ValueError) as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)

        entetes, lignes = (_lignes_pivot(pivot) if pivot
                           else _lignes_plates(rows))
        entetes, lignes = _sans_colonnes_interdites(entetes, lignes)

        base = obj.titre or obj.dataset or 'rapport'
        nom = ''.join(
            c for c in base if c.isalnum() or c in ('-', '_')) or 'rapport'

        if fmt == 'xlsx':
            try:
                from apps.records.xlsx import workbook_bytes
                contenu = workbook_bytes(
                    entetes, lignes, sheet_title=base[:31])
            except Exception:  # pragma: no cover - dépend d'openpyxl
                return Response(
                    {'detail': "Export xlsx indisponible sur ce serveur : "
                               "réessayez au format csv."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE)
            reponse = HttpResponse(
                contenu,
                content_type='application/vnd.openxmlformats-officedocument'
                             '.spreadsheetml.sheet')
            reponse['Content-Disposition'] = (
                f'attachment; filename="{nom}.xlsx"')
            return reponse

        tampon = io.StringIO()
        writer = csv.writer(tampon)
        if entetes:
            writer.writerow(entetes)
        writer.writerows(lignes)
        reponse = HttpResponse(
            tampon.getvalue().encode('utf-8-sig'),
            content_type='text/csv; charset=utf-8')
        reponse['Content-Disposition'] = f'attachment; filename="{nom}.csv"'
        return reponse


#: NTEXT11 — fragments de nom de colonne qui ne sortent JAMAIS dans un export
#: (prix d'achat / marge : donnée interne, jamais client-facing).
COLONNES_INTERDITES = ('prix_achat', 'prixachat', 'marge', 'cout_achat')


def _sans_colonnes_interdites(entetes, lignes):
    """Retire des en-têtes ET des lignes toute colonne de prix d'achat/marge."""
    if not entetes:
        return entetes, lignes
    gardes = [
        i for i, entete in enumerate(entetes)
        if not any(mot in str(entete).lower().replace(' ', '_')
                   for mot in COLONNES_INTERDITES)
    ]
    if len(gardes) == len(entetes):
        return entetes, lignes
    return (
        [entetes[i] for i in gardes],
        [[ligne[i] for i in gardes if i < len(ligne)] for ligne in lignes],
    )
