"""NTWMS37 — Réception à quantité / poids VARIABLE (catch-weight).

Un touret de câble commandé « 1 rouleau de 100 m » arrive rarement à 100,00 m :
la quantité commandée est NOMINALE, la quantité réellement reçue est PESÉE ou
MÉTRÉE. Sans ce relevé, on valorise une entrée sur une quantité qui n'a jamais
existé.

ADAPTATION DE PÉRIMÈTRE (assumée, testée). La tâche demandait deux champs
additifs sur ``LigneReceptionFournisseur`` — modèle d'``apps.achats`` (ODX19),
que cette lane ne possède pas et où elle n'écrit jamais. Le relevé est donc un
SATELLITE de ``stock`` en relation 1-1 avec la ligne (string-FK), exactement
comme ``AffectationCrossDock`` (NTWMS15) porte hors d'``achats`` la décision de
cross-dock. Conséquence utile : ABSENCE de relevé = comportement historique
strictement inchangé pour les 100 % de lignes non variables, sans qu'aucune
colonne par défaut n'ait été posée sur la table de réception.
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel


class PeseeLigneReception(TenantModel):
    """Quantité RÉELLE relevée pour une ligne de réception à unité variable.

    ``unite_variable`` faux (le défaut) reproduit le comportement historique :
    la quantité qui fait foi reste celle de la ligne. Vrai + ``quantite_reelle``
    renseignée : c'est le relevé qui fait foi pour la VALORISATION, jamais pour
    le compte d'unités physiques (un touret reste un touret).
    """

    class UniteMesure(models.TextChoices):
        KG = 'kg', 'Kilogramme'
        METRE = 'm', 'Mètre'
        LITRE = 'l', 'Litre'
        UNITE = 'u', 'Unité'

    ligne_reception = models.OneToOneField(
        'achats.LigneReceptionFournisseur', on_delete=models.CASCADE,  # on_delete: CASCADE — le relevé n'existe QUE pour sa ligne de réception ; sans elle il ne mesure plus rien (composition stricte)
        related_name='pesee_stock')
    unite_variable = models.BooleanField(
        default=False,
        help_text='Faux = comportement historique (la quantité de la ligne '
                  'fait foi).')
    quantite_reelle = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        help_text='Quantité réellement pesée/métrée (vide = non relevée).')
    unite_mesure = models.CharField(
        max_length=4, choices=UniteMesure.choices, default=UniteMesure.KG)
    releve_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pesees_reception_stock')
    note = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Relevé de réception à unité variable'
        verbose_name_plural = 'Relevés de réception à unité variable'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'unite_variable'],
                         name='idx_pesee_co_variable'),
        ]

    def __str__(self):
        return f'Pesée ligne {self.ligne_reception_id} — {self.quantite_reelle}'

    @property
    def est_renseignee(self):
        """Vrai quand le relevé fait foi (variable ET quantité saisie)."""
        return bool(self.unite_variable and self.quantite_reelle is not None)
