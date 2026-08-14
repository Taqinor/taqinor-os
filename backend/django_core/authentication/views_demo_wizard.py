"""NTDMO25 — wizard « Créer ma société de démonstration » (3 étapes, UI).

Réservé à la console fondateur (même garde ``IsSuperuserConsole`` que le
reste de l'admin technique, ``views_console.py``). Enveloppe fine autour de
``seed_demo_company --profil --densite`` (NTDMO25 y ajoute ces deux options
ADDITIVES, défauts = comportement historique). Déclenchement en tâche Celery
best-effort (même repli synchrone que ``_run_demo_reset``, NTDMO7) ; la
progression est suivie via un compteur cache léger (clé
``demo_wizard_progress:<slug>``) — pas de nouveau modèle/migration pour un
indicateur transitoire et best-effort.
"""
from django.core.cache import cache
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .views_console import IsSuperuserConsole


_WIZARD_CREATE_REQUEST = inline_serializer('DemoWizardCreateRequest', {
    'slug': drf_serializers.CharField(required=False),
    'profil': drf_serializers.ChoiceField(
        choices=['residentiel', 'industriel', 'mixte'], required=False),
    'densite': drf_serializers.ChoiceField(
        choices=['leger', 'complet'], required=False),
})
# Instance PARTAGEE (jamais re-fabriquee) : chaque appel a inline_serializer()
# cree une NOUVELLE classe Python de meme nom -> drf-spectacular la voit
# comme un composant en collision (« identical names, different identities »)
# des qu'on la reference plus d'une fois. Reutiliser LA MEME instance sur les
# 3 reponses (200/202 de POST, 200 de GET) evite ca ; DRF copie ses champs par
# instance a la resolution (`Serializer.get_fields()`), donc aucun partage
# d'etat mutable entre les schemas qui la citent.
_WIZARD_STATUT_RESPONSE = inline_serializer('DemoWizardStatut', {
    'slug': drf_serializers.CharField(),
    'statut': drf_serializers.CharField(),
    'pourcentage': drf_serializers.IntegerField(required=False),
})


_CACHE_PREFIX = 'demo_wizard_progress:'
_CACHE_TTL = 3600


def _progress_key(slug):
    return f'{_CACHE_PREFIX}{slug}'


def set_progress(slug, pourcentage, statut='en_cours'):
    cache.set(_progress_key(slug), {'pourcentage': pourcentage,
                                    'statut': statut}, _CACHE_TTL)


def _run_wizard(slug, profil, densite):
    """Exécute la commande + trace la progression (0 → 50 → 100)."""
    from django.core.management import call_command
    set_progress(slug, 10, 'en_cours')
    call_command('seed_demo_company', slug=slug, profil=profil,
                 densite=densite, force=True, verbosity=0)
    set_progress(slug, 100, 'termine')


class DemoWizardCreateView(APIView):
    """POST — étape 3 (récapitulatif + « Générer ») du wizard NTDMO25."""
    permission_classes = [IsSuperuserConsole]

    @extend_schema(request=_WIZARD_CREATE_REQUEST,
                   responses={200: _WIZARD_STATUT_RESPONSE,
                              202: _WIZARD_STATUT_RESPONSE})
    def post(self, request):
        slug = (request.data.get('slug') or '').strip() or 'taqinor-demo-full'
        profil = request.data.get('profil', 'mixte')
        densite = request.data.get('densite', 'complet')
        if profil not in ('residentiel', 'industriel', 'mixte'):
            return Response(
                {'detail': 'profil invalide.'},
                status=status.HTTP_400_BAD_REQUEST)
        if densite not in ('leger', 'complet'):
            return Response(
                {'detail': 'densite invalide.'},
                status=status.HTTP_400_BAD_REQUEST)

        set_progress(slug, 0, 'en_cours')
        try:
            from authentication.tasks import seed_demo_company_task
            seed_demo_company_task.delay(slug, profil, densite)
            return Response(
                {'slug': slug, 'statut': 'en_cours'},
                status=status.HTTP_202_ACCEPTED)
        except Exception:
            # Pas de Celery (ou pas de task) → exécution synchrone immédiate,
            # même repli que ``_run_demo_reset`` (NTDMO7).
            _run_wizard(slug, profil, densite)
            return Response({'slug': slug, 'statut': 'termine'},
                            status=status.HTTP_200_OK)


class DemoWizardStatusView(APIView):
    """GET ?slug=... — barre de progression pollée par le frontend."""
    permission_classes = [IsSuperuserConsole]

    @extend_schema(responses={200: _WIZARD_STATUT_RESPONSE})
    def get(self, request):
        slug = request.query_params.get('slug')
        if not slug:
            return Response({'detail': 'slug requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        data = cache.get(_progress_key(slug))
        if data is None:
            return Response({'slug': slug, 'statut': 'inconnu',
                            'pourcentage': 0})
        return Response({'slug': slug, **data})
