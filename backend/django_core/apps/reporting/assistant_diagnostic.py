"""COP-G6 — ``GET /api/django/reporting/assistant/diagnostic/`` : « qu'est-ce qui
a cassé hier ? », « l'assistant marche-t-il ? » pour l'ADMINISTRATEUR.

Le résumé du journal des problèmes (``problemes/resume/``, BPQ4) n'est lisible
que par jeton de service et couvre TOUTES les sociétés : un administrateur ne
pouvait pas le demander à l'assistant. Cette lecture, réservée aux
administrateurs (403 sinon), le borne à LA SOCIÉTÉ de l'utilisateur :

* ``problemes`` — exactement les lignes de ``journal_problemes.resume_json``
  (même calcul, jamais une copie de la règle), société de l'utilisateur ;
* ``plateforme`` — santé, envois en échec, sauvegardes, tâches, déploiements :
  des faits de TOUTE la plateforme, servis au seul super-utilisateur (``null``
  sinon) ;
* ``assistant`` — questions, erreurs, part de repli, coût et signalements
  (``apps.agent.selectors.resume_assistant``).

Contrat : ``contract_samples/assistant_diagnostic.json``. Aucune donnée client,
aucun corps de requête ; les questions des signalements sont ANONYMISÉES par
l'anonymisation de l'export de l'assistant.
"""
from datetime import timedelta

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsAdminRole, IsAnyRole

from .journal_problemes import resume_json

#: Fenêtre du diagnostic : hier par défaut, une semaine au plus (au-delà, c'est
#: le résumé de service ou la commande serveur).
JOURS_DEFAUT = 1
JOURS_MAX = 7

#: Clés de ``resume_json`` qui décrivent la PLATEFORME entière (pas la société).
CLES_PLATEFORME = (
    'outbox_en_echec', 'outbox_alimentee', 'sauvegardes_en_echec',
    'taches_en_echec', 'deploys_en_echec', 'sante',
)


def diagnostic_json(user, jours=JOURS_DEFAUT, maintenant=None):
    """Le diagnostic de ``user`` (administrateur) sur ``jours`` jours."""
    from apps.agent.selectors import resume_assistant

    maintenant = maintenant or timezone.now()
    societe = user.company
    resume = resume_json(jours, societe, maintenant)
    plateforme = None
    if user.is_superuser:
        # Les faits de plateforme ne dépendent d'aucune société : lus sans filtre.
        complet = resume_json(jours, None, maintenant) if societe else resume
        plateforme = {cle: complet[cle] for cle in CLES_PLATEFORME}
    return {
        'jours': resume['jours'],
        'genere_le': resume['genere_le'],
        'problemes': resume['problemes'],
        'plateforme': plateforme,
        'assistant': resume_assistant(
            societe, maintenant - timedelta(days=jours)),
    }


def _jours(request) -> int:
    valeurs = request.query_params.getlist('jours')
    if not valeurs:
        return JOURS_DEFAUT
    brut = valeurs[0].strip()
    if len(valeurs) > 1 or not brut.isascii() or not brut.isdigit() \
            or not 1 <= int(brut) <= JOURS_MAX:
        raise ParseError(f'jours : entier de 1 à {JOURS_MAX}.')
    return int(brut)


_DIAGNOSTIC_REPONSE = inline_serializer('AssistantDiagnostic', {
    'jours': serializers.IntegerField(),
    'genere_le': serializers.DateTimeField(),
    'problemes': serializers.ListField(child=serializers.DictField()),
    'plateforme': serializers.DictField(allow_null=True),
    'assistant': serializers.DictField(),
})


class DiagnosticAssistantView(APIView):
    """Diagnostic pour l'administrateur (403 sinon) ; société de l'utilisateur."""

    permission_classes = [IsAnyRole, IsAdminRole]

    @extend_schema(
        parameters=[OpenApiParameter(
            'jours', {'type': 'integer', 'minimum': 1, 'maximum': JOURS_MAX},
            required=False)],
        responses=_DIAGNOSTIC_REPONSE)
    def get(self, request):
        return Response(diagnostic_json(request.user, _jours(request)))
