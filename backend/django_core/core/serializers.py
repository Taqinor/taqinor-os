"""Sérialiseurs de la couche fondation ``core``.

FG368 — forme de sortie des jobs planifiés (lecture seule, infra globale).
FG369 — forme de sortie des modèles de workflow installables (catalogue).
"""
from rest_framework import serializers


class ScheduledJobSerializer(serializers.Serializer):
    """Job planifié normalisé (cf. ``core.jobs.list_jobs``)."""
    name = serializers.CharField()
    task = serializers.CharField()
    schedule = serializers.CharField(allow_blank=True)
    enabled = serializers.BooleanField()
    source = serializers.CharField()
    last_run = serializers.CharField(allow_null=True, required=False)


class WorkflowTemplateStepSerializer(serializers.Serializer):
    """Étape d'un modèle de workflow (FG369, lecture seule)."""
    ordre = serializers.IntegerField()
    nom = serializers.CharField()
    type_approbation = serializers.CharField()
    sla_heures = serializers.IntegerField(allow_null=True)
    role_requis = serializers.CharField(allow_blank=True)
    escalade_vers = serializers.CharField(allow_blank=True)


class WorkflowTemplateSerializer(serializers.Serializer):
    """Modèle de workflow installable (FG369, catalogue — lecture seule)."""
    code = serializers.CharField()
    nom = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    nb_etapes = serializers.IntegerField()
    steps = WorkflowTemplateStepSerializer(many=True)
