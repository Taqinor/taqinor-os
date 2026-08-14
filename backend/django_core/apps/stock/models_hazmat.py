"""NTWMS38 — Compatibilité casier ↔ classe de danger (hazmat).

``Produit.classe_danger`` (dans ``models.py``) dit CE QU'EST le produit ; ce
module dit QUELS CASIERS l'acceptent. Le rangement guidé (NTWMS2) refuse alors
de suggérer un casier non compatible pour une batterie lithium — le cas réel
du catalogue solaire.

ADAPTATION DE PÉRIMÈTRE (assumée, testée). La tâche demandait un M2M
``Bin.compatible_hazmat``. Les casiers vivent dans ``installations``
(``BinLocation``, FG319) — app que cette lane ne possède pas et où elle
n'écrit jamais (même constat que NTWMS31 pour le ``type_bin`` QUARANTAINE, qui
n'existe pas non plus). La compatibilité est donc portée ICI, une ligne par
couple (casier, classe), le casier référencé en STRING-FK.

RÈGLE DE DÉFAUT — celle qui rend le lot additif : un casier SANS aucune ligne
de compatibilité accepte tout produit NON dangereux et refuse tout produit
dangereux. Aucune société n'a de ligne à l'installation, donc rien ne change
pour les produits ordinaires ; le filtrage ne s'active que le jour où un
produit est explicitement déclaré dangereux.
"""
from django.db import models

from core.models import TenantModel


class CompatibiliteHazmatCasier(TenantModel):
    """Un casier autorisé à recevoir UNE classe de danger."""

    bin = models.ForeignKey(
        'installations.BinLocation', on_delete=models.CASCADE,  # on_delete: CASCADE — l'autorisation ne décrit QUE ce casier ; le casier supprimé, elle n'autorise plus rien (composition stricte)
        related_name='compatibilites_hazmat_stock')
    classe_danger = models.CharField(
        max_length=20,
        help_text='Valeur de Produit.ClasseDanger acceptée dans ce casier.')

    class Meta:
        verbose_name = 'Compatibilité casier ↔ matière dangereuse'
        verbose_name_plural = 'Compatibilités casier ↔ matières dangereuses'
        ordering = ['bin_id', 'classe_danger']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'bin', 'classe_danger'],
                name='stock_hazmatbin_company_bin_classe_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'classe_danger'],
                         name='idx_hazmatbin_co_classe'),
        ]

    def __str__(self):
        return f'{self.bin_id} accepte {self.classe_danger}'
