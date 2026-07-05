"""
XFSM10 — Astreinte / rotation après-heures.

Le roster FG169 (``apps.rh.AffectationRoster``) couvre les shifts NORMAUX ;
rien ne gère l'astreinte nuits/week-ends ni le routage des urgences hors heures
ouvrées. ``Astreinte`` enregistre, sur une fenêtre [date_debut, date_fin]
INCLUSIVE, le technicien D'ASTREINTE d'une société (unique par période/société
— pas de chevauchement, gardé par ``clean()``).

Couche INDÉPENDANTE des trois couches de statuts de l'OS (entonnoir STAGES.py,
statut document ventes, statut chantier) : une astreinte ne touche AUCUN
statut. Exposée en LECTURE SEULE aux autres apps via
``installations.selectors.technicien_astreinte`` (paie notamment — jamais
d'import de ``apps.paie.models`` ici, jamais d'import de ``apps.installations``
depuis paie non plus : la lecture se fait dans l'autre sens, paie appelle CE
sélecteur). Additif & multi-tenant : société posée côté serveur."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Astreinte(models.Model):
    """XFSM10 — période d'astreinte (nuits/week-ends/jours fériés) assignée à
    un technicien. Une seule astreinte active par (société, période) : les
    chevauchements sont refusés (``clean()``)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='astreintes')
    technicien = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='astreintes')
    date_debut = models.DateTimeField()
    date_fin = models.DateTimeField()
    telephone_astreinte = models.CharField(max_length=30, blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='astreintes_creees')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_debut']
        verbose_name = 'Astreinte'
        verbose_name_plural = 'Astreintes'

    def __str__(self):
        return f"Astreinte {self.technicien_id} [{self.date_debut} → {self.date_fin}]"

    def clean(self):
        if self.date_debut and self.date_fin and self.date_debut >= self.date_fin:
            raise ValidationError(
                "La date de fin d'astreinte doit être après la date de début.")
        if self.company_id and self.date_debut and self.date_fin:
            overlap = Astreinte.objects.filter(
                company_id=self.company_id,
                date_debut__lt=self.date_fin,
                date_fin__gt=self.date_debut,
            ).exclude(pk=self.pk)
            if overlap.exists():
                raise ValidationError(
                    "Une astreinte existe déjà sur cette période pour cette société.")
