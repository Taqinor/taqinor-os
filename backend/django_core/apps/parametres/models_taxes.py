"""ARC23 — Référentiel des taux de TVA, par société.

Constat : aucun master des taux ; ``taux_tva`` était un Decimal nu dupliqué sur
sept champs de ``ventes/models.py`` (Devis/Facture/Avoir/NoteDebit + leurs
lignes) avec un repli ``taux_tva_effectif`` par modèle. Ce modèle DÉCLARE, par
société, les taux de TVA usuels (marocains : 20/14/10/7/0). D-APAR-1 (APAR44) : il ne désigne PLUS de taux par défaut —
la seule source en est ``CompanyProfile.tva_standard``. Il ne RÉÉCRIT JAMAIS un
taux déjà figé sur un document émis (immutabilité légale — règle #4).

Purement déclaratif et ADDITIF. Gardé dans un fichier dédié
(indépendance de lane) ; enregistré via ``apps.ready()``.
"""
from decimal import Decimal

from django.db import models

from core.models import TenantModel


# Taux de TVA marocains usuels (réforme 2024–2026). D-APAR-1 : le taux par défaut
# d'un nouveau document vient UNIQUEMENT du profil société (``tva_standard``) ;
# le référentiel ne porte que la liste des taux. Source partagée avec
# ``apps.ventes.selectors.TAUX_TVA_REFERENTIEL`` (contrôles/labels).
TAUX_TVA_MAROCAINS = [
    {'code': 'standard', 'libelle': 'Taux normal (20 %)', 'taux': '20'},
    {'code': 'tva14', 'libelle': 'Taux réduit (14 %)', 'taux': '14'},
    {'code': 'panneaux', 'libelle': 'Panneaux photovoltaïques (10 %)',
     'taux': '10'},
    {'code': 'tva7', 'libelle': 'Taux réduit (7 %)', 'taux': '7'},
    {'code': 'exonere', 'libelle': 'Exonéré (0 %)', 'taux': '0'},
]


class TauxTVA(TenantModel):
    """Un taux de TVA de référence par société (code + libellé FR + taux)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        related_name='taux_tva_referentiel')
    # Code technique stable (standard/panneaux/exonere/tva14/tva7…), unique par
    # société — sert de clé d'idempotence au seed.
    code = models.CharField(max_length=32)
    libelle = models.CharField(max_length=120)
    taux = models.DecimalField(max_digits=5, decimal_places=2)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Taux de TVA'
        verbose_name_plural = 'Taux de TVA'
        ordering = ['-taux', 'code']
        # Un seul enregistrement par société + code (idempotence du seed).
        unique_together = [('company', 'code')]
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='param_tauxtva_idx'),
        ]

    def __str__(self):
        return f'{self.company_id}:{self.code} ({self.taux}%)'

    @classmethod
    def taux_pour_code(cls, company, code):
        """Taux actif (Decimal) pour un ``code`` donné, ou None si absent."""
        if company is None:
            return None
        row = cls.objects.filter(
            company=company, actif=True, code=code).first()
        return row.taux if row is not None else None

    @classmethod
    def seed_defaults(cls, company):
        """Seede les taux marocains usuels pour ``company`` (idempotent, additif).

        ``get_or_create`` par (company, code) : rejouable sans doublon et ne
        touche JAMAIS un taux déjà édité (seul le libellé/défaut sont posés à la
        création). Renvoie le nombre de lignes créées."""
        crees = 0
        for entry in TAUX_TVA_MAROCAINS:
            _, created = cls.objects.get_or_create(
                company=company, code=entry['code'],
                defaults={
                    'libelle': entry['libelle'],
                    'taux': Decimal(entry['taux']),
                    'actif': True,
                })
            if created:
                crees += 1
        return crees
