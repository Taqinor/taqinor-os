"""NTOBS10 — page « Confiance » (trust center) : certifications, sous-
traitants, localisation des données.

Contenu 100% SYSTÈME (pas de ``company`` — un seul jeu partagé, comme
``apps.statuspage.ComponentStatus`` côté système). RÈGLE ABSOLUE (checked-
facts-only, déjà appliquée au site vitrine) : aucune certification ni
conformité NON réellement obtenue n'est affichée — chaque entrée doit être
vérifiable, sinon le champ reste vide plutôt que rempli. Le seed
(``seed_trust_center``) ne pose QUE des faits vérifiés connus ; il n'invente
JAMAIS une certification non détenue.

Modèle défini ICI (pas directement dans ``core/models.py``) et réexporté en
bas de ``core/models.py`` — même éclatement que ``core/sla.py``.
"""
from __future__ import annotations

from django.db import models
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import TimestampedModel


class TrustCenterEntry(TimestampedModel):
    """Entrée du trust center public (pas de ``company`` — contenu système)."""

    class Categorie(models.TextChoices):
        CERTIFICATION = 'certification', 'Certification'
        SOUS_TRAITANT = 'sous_traitant', 'Sous-traitant'
        LOCALISATION_DONNEES = 'localisation_donnees', 'Localisation des données'
        POLITIQUE = 'politique', 'Politique'

    categorie = models.CharField(
        'Catégorie', max_length=25, choices=Categorie.choices)
    titre = models.CharField('Titre', max_length=255)
    description = models.TextField('Description', blank=True, default='')
    document_key = models.CharField(
        'Clé document (MinIO)', max_length=500, blank=True, default='',
        help_text='PDF justificatif, optionnel.')
    dernier_audit_le = models.DateField('Dernier audit le', null=True, blank=True)
    ordre_affichage = models.PositiveIntegerField('Ordre', default=100)

    class Meta:
        verbose_name = 'Entrée trust center'
        verbose_name_plural = 'Entrées trust center'
        ordering = ['ordre_affichage', 'titre']

    def __str__(self):
        return f'{self.get_categorie_display()} — {self.titre}'


class TrustCenterEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = TrustCenterEntry
        fields = [
            'id', 'categorie', 'titre', 'description', 'document_key',
            'dernier_audit_le', 'ordre_affichage',
        ]


@api_view(['GET'])
@permission_classes([AllowAny])
def trust_center_public(request):
    """GET /api/django/core/trust-center/ — public, lecture seule, aucune
    donnée société (le modèle lui-même n'en porte aucune)."""
    entries = TrustCenterEntry.objects.all()
    return Response(TrustCenterEntrySerializer(entries, many=True).data)
