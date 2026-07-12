"""Mixin réutilisable pour un ``destroy()`` de ViewSet DRF cohérent sur un
modèle de configuration « gardé » (protégé et/ou en usage).

VX241(b) — 7 modèles gardés « en usage » (LeadTag, MotifPerte, Canal,
ChecklistTemplate, ChecklistEtapeModele, SafetyChecklistSlot, StageModele)
avaient CHACUN leur propre ``destroy()`` réimplémentant le même patron (garde
+ 409 FR) SANS jamais écrire de ligne ``AuditLog`` — aucun n'est dans
``apps.audit.signals.TRACKED_MODELS`` (ce sont des tables de configuration,
pas des objets métier « racine »), donc leur suppression était totalement
invisible au Journal. Ce mixin factorise le patron en UN seul endroit.

Note d'architecture : ce module vit sous ``apps.core`` (un espace de noms
utilitaire, PAS une app Django enregistrée — pas de ``models.py``/``apps.py``)
et non sous le paquet racine ``core`` (la couche de fondation contrainte par
``.importlinter`` : ``core-foundation-is-a-base-layer`` lui interdit
d'importer ``apps.audit``). ``apps.core`` n'est visé par aucun contrat
import-linter — l'import différé de ``apps.audit`` ci-dessous est donc sûr,
exactement comme ``apps/crm/views.py`` importe déjà directement
``apps.audit.recorder``.
"""
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.response import Response


class UsageGuardedDestroyMixin:
    """``destroy()`` cohérent : le sous-classeur fournit
    ``destroy_guard_message(obj)`` (renvoie un message FR de blocage, ou
    ``None``/``''`` pour laisser passer). Le mixin gère la 409 ET, à la
    suppression effective, écrit une ligne ``AuditLog`` DELETE via
    ``apps.audit.recorder.record()`` — puisque ce modèle n'est pas dans
    ``TRACKED_MODELS`` (donc aucun signal générique ne le journalise), c'est
    le SEUL endroit qui pose cette ligne."""

    def destroy_guard_message(self, obj):
        """À surcharger : renvoie un message FR de blocage, ou None/''."""
        return None

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        message = self.destroy_guard_message(obj)
        if message:
            return Response({'detail': message}, status=status.HTTP_409_CONFLICT)
        # Capturés AVANT l'appel : Model.delete() remet `pk` à None sur
        # l'instance Python après coup — journaliser APRÈS coup écrirait une
        # ligne avec un object_id vide.
        content_type = ContentType.objects.get_for_model(obj.__class__)
        object_id = str(obj.pk)
        object_repr = str(obj)
        company = getattr(obj, 'company', None)
        response = super().destroy(request, *args, **kwargs)
        if response.status_code == status.HTTP_204_NO_CONTENT:
            from apps.audit import recorder
            from apps.audit.models import AuditLog
            recorder.record(
                AuditLog.Action.DELETE, content_type=content_type,
                object_id=object_id, object_repr=object_repr, company=company,
                detail=f'Suppression : {object_repr}')
        return response
