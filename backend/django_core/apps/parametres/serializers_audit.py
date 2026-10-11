"""Sérialiseur du journal d'audit (``SettingsAuditLogSerializer``).

Domaine « Avancé / Journal d'audit ». Extrait de l'ancien ``serializers.py``
sans aucun changement de champ ni de comportement."""
from rest_framework import serializers

from .models import SettingsAuditLog


class SettingsAuditLogSerializer(serializers.ModelSerializer):
    user_nom = serializers.CharField(source='user.username', read_only=True, allow_null=True)

    class Meta:
        model = SettingsAuditLog
        fields = [
            'id', 'section', 'field', 'field_label',
            'old_value', 'new_value', 'user', 'user_nom', 'timestamp',
        ]
        # ENF17 — sérialiseur de SORTIE du journal (aucune écriture API) :
        # l'auteur est posé par le serveur au moment de l'audit, jamais lu
        # d'un corps — la FK utilisateur n'est donc pas inscriptible.
        read_only_fields = ['user']
