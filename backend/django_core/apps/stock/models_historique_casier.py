"""NTWMS39 — Historique de versions du plan d'entrepôt (audit léger casier).

« Pourquoi ce casier a-t-il changé de catégorie ? Qui l'a retiré du plan ? » —
sans journal, la réponse est perdue. Ce modèle est le journal MINIMAL d'un
casier : création, modification d'un champ structurant, archivage,
réactivation.

ADAPTATION DE PÉRIMÈTRE (assumée, testée). Les casiers vivent dans
``installations`` (``BinLocation``, FG319) : cette lane ne les modifie jamais.
Le journal est donc porté par ``stock``, alimenté par un RÉCEPTEUR de signal
branché dans ``StockConfig.ready()`` (``apps.get_model`` — jamais un import du
module de modèles d'``installations``). Le champ ``type_bin`` annoncé par la
tâche n'existe pas sur ``BinLocation`` (même constat que NTWMS31) : le journal
suit les champs qui existent réellement — zone, allée, casier, ordre de
parcours, catégorie de stockage, archivage.
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel

# Champs dont un changement mérite une ligne de journal.
CHAMPS_SUIVIS = ('code', 'zone', 'allee', 'casier', 'ordre', 'categorie_id')


class HistoriqueCasier(TenantModel):
    """Une ligne de journal sur un casier : qui, quand, quoi."""

    class Action(models.TextChoices):
        CREATION = 'creation', 'Création'
        MODIFICATION = 'modification', 'Modification'
        ARCHIVAGE = 'archivage', 'Archivage'
        REACTIVATION = 'reactivation', 'Réactivation'

    bin = models.ForeignKey(
        'installations.BinLocation', on_delete=models.CASCADE,  # on_delete: CASCADE — le journal décrit CE casier ; le casier supprimé, ses lignes n'ont plus de sujet (composition stricte)
        related_name='historique_stock')
    action = models.CharField(max_length=20, choices=Action.choices)
    champ = models.CharField(max_length=40, blank=True, default='')
    ancienne_valeur = models.CharField(max_length=200, blank=True, default='')
    nouvelle_valeur = models.CharField(max_length=200, blank=True, default='')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='historiques_casier_stock')

    class Meta:
        verbose_name = 'Historique de casier'
        verbose_name_plural = 'Historiques de casier'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['company', 'bin'],
                         name='idx_histcasier_co_bin'),
        ]

    def __str__(self):
        return f'{self.bin_id} · {self.action} {self.champ}'.strip()
