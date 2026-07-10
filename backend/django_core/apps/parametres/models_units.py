"""ARC27 — Référentiel des unités de mesure, par société.

Constat : ``stock.Produit.unite_stock`` est un CharField libre (défaut
``'unité'``, XSTK15) ; aucune table d'unités. ``ConditionnementProduit``
convertit déjà vers cette unité unique (design sain). Ce modèle DÉCLARE, par
société, les unités de mesure usuelles (code + libellé FR + actif). Le CharField
``unite_stock`` reste MAÎTRE ; une FK optionnelle ``unite`` sur ``Produit`` en
est le MIROIR (backfillé). Additif : zéro impact sur les mouvements existants.

Gardé dans un fichier dédié (indépendance de lane) ; enregistré via
``apps.ready()``.
"""
from django.db import models

from core.models import TenantModel


# Unités de mesure usuelles (code stable + libellé FR affichable). ``code`` est
# la valeur portée par ``Produit.unite_stock`` (rétro-compat : 'unité' reste le
# code par défaut historique). Source seedée au signup + backfillée.
UNITES_MESURE_DEFAUT = [
    {'code': 'unité', 'libelle': 'Unité'},
    {'code': 'm', 'libelle': 'Mètre'},
    {'code': 'm²', 'libelle': 'Mètre carré'},
    {'code': 'm³', 'libelle': 'Mètre cube'},
    {'code': 'kg', 'libelle': 'Kilogramme'},
    {'code': 'L', 'libelle': 'Litre'},
    {'code': 'h', 'libelle': 'Heure'},
    {'code': 'jour', 'libelle': 'Jour'},
    {'code': 'jeu', 'libelle': 'Jeu'},
    {'code': 'lot', 'libelle': 'Lot'},
]


class UniteMesure(TenantModel):
    """Une unité de mesure de référence par société (code + libellé FR)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='unites_mesure_referentiel')
    # Code technique = valeur portée par ``Produit.unite_stock`` (clé de miroir).
    code = models.CharField(max_length=20)
    libelle = models.CharField(max_length=80)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Unité de mesure'
        verbose_name_plural = 'Unités de mesure'
        ordering = ['code']
        # Un seul enregistrement par société + code (idempotence seed/backfill).
        unique_together = [('company', 'code')]
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='param_unite_idx'),
        ]

    def __str__(self):
        return f'{self.company_id}:{self.code}'

    @classmethod
    def libelle_pour_code(cls, company, code):
        """Libellé FR de l'unité active ``code`` de ``company``, ou None.

        Alimente l'AFFICHAGE (générateur de devis / fiche produit) quand une
        unité du référentiel correspond au ``Produit.unite_stock``. None (aucune
        unité référencée) → l'appelant affiche le code brut (comportement
        historique). N'altère JAMAIS ``unite_stock`` lui-même."""
        if company is None or not code:
            return None
        row = cls.objects.filter(
            company=company, actif=True, code=code).first()
        return row.libelle if row is not None else None

    @classmethod
    def seed_defaults(cls, company):
        """Seede les unités usuelles pour ``company`` (idempotent, additif).

        ``get_or_create`` par (company, code) : rejouable sans doublon et ne
        retouche jamais une unité existante. Renvoie le nombre de lignes
        créées."""
        crees = 0
        for entry in UNITES_MESURE_DEFAUT:
            _, created = cls.objects.get_or_create(
                company=company, code=entry['code'],
                defaults={'libelle': entry['libelle'], 'actif': True})
            if created:
                crees += 1
        return crees
