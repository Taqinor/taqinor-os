"""
FG282 — Garantie de PRODUCTION par système + compensation de manque.

`ProductionWarranty` modélise l'engagement de production d'un système installé :
une production garantie de référence (kWh/an), une dégradation annuelle garantie
(courbe du fabricant/EPC, %/an) et un tarif de compensation (MAD/kWh) pour
chiffrer un manque. Le service `production_warranty_status` compare la production
réelle (depuis `ProductionReading`) au productible garanti dégradé de l'année
considérée et en déduit l'écart et la compensation due.

STRICTEMENT ADDITIF, multi-tenant : `company` posée côté serveur, jamais lue du
corps. Aucun import d'un autre app domaine.
"""
from django.db import models


class ProductionWarranty(models.Model):
    """Engagement de production garanti d'UN système installé.

    `guaranteed_year1_kwh` = productible garanti la 1re année (kWh/an).
    `degradation_pct_per_year` = dégradation garantie annuelle (ex. 0,5 %/an :
    le garanti de l'année N = year1 × (1 - taux)^(N-1)).
    `start_year` = année de référence (année 1). `compensation_mad_per_kwh` =
    tarif de compensation d'un manque par kWh.
    """

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='production_warranties')
    installation = models.OneToOneField(
        'installations.Installation', on_delete=models.CASCADE,
        related_name='production_warranty')
    guaranteed_year1_kwh = models.DecimalField(max_digits=12, decimal_places=2)
    degradation_pct_per_year = models.DecimalField(
        max_digits=5, decimal_places=2, default=0)
    start_year = models.PositiveIntegerField()
    compensation_mad_per_kwh = models.DecimalField(
        max_digits=8, decimal_places=4, default=0)
    # Tolérance (%) : un manque inférieur à cette part du garanti n'est pas
    # compensé (franchise contractuelle). Défaut 0 = tout manque compté.
    tolerance_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=0)
    note = models.TextField(blank=True, default='')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Garantie de production'
        verbose_name_plural = 'Garanties de production'
        ordering = ['-date_modification']
        indexes = [models.Index(fields=['company', 'installation'])]

    def __str__(self):
        return f'Garantie production #{self.installation_id}'

    def guaranteed_kwh_for_year(self, year):
        """Productible garanti (kWh) pour l'année calendaire `year`,
        dégradé depuis l'année de référence. Avant `start_year` → year1."""
        from decimal import Decimal
        elapsed = max(0, int(year) - int(self.start_year))
        factor = Decimal('1')
        rate = Decimal('1') - (Decimal(str(self.degradation_pct_per_year))
                               / Decimal('100'))
        for _ in range(elapsed):
            factor *= rate
        return Decimal(str(self.guaranteed_year1_kwh)) * factor
