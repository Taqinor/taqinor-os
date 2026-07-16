"""ARC23 — Référentiel des taux de TVA, par société.

Constat : aucun master des taux ; ``taux_tva`` était un Decimal nu dupliqué sur
sept champs de ``ventes/models.py`` (Devis/Facture/Avoir/NoteDebit + leurs
lignes) avec un repli ``taux_tva_effectif`` par modèle. Ce modèle DÉCLARE, par
société, les taux de TVA usuels (marocains : 20/14/10/7/0) et désigne le taux
STANDARD par défaut. Il alimente les DÉFAUTS à la CRÉATION d'un document ; il ne
RÉÉCRIT JAMAIS un taux déjà figé sur un document émis (immutabilité légale —
règle #4 : le moteur de devis ne fait que rendre les valeurs des lignes).

Purement déclaratif et ADDITIF : sans référentiel, ``default_taux`` renvoie
None et le chemin de création retombe sur le comportement historique
(``CompanyProfile.tva_standard`` / défaut 20). Gardé dans un fichier dédié
(indépendance de lane) ; enregistré via ``apps.ready()``.
"""
from decimal import Decimal

from django.db import models

from core.models import TenantModel


# Taux de TVA marocains usuels (réforme 2024–2026). Le taux STANDARD (20 %) est
# marqué ``defaut=True`` au seed : c'est lui qui alimente le défaut d'un nouveau
# document quand le corps n'en fournit pas. Source partagée avec
# ``apps.ventes.selectors.TAUX_TVA_REFERENTIEL`` (contrôles/labels).
TAUX_TVA_MAROCAINS = [
    {'code': 'standard', 'libelle': 'Taux normal (20 %)', 'taux': '20',
     'defaut': True},
    {'code': 'tva14', 'libelle': 'Taux réduit (14 %)', 'taux': '14',
     'defaut': False},
    {'code': 'panneaux', 'libelle': 'Panneaux photovoltaïques (10 %)',
     'taux': '10', 'defaut': False},
    {'code': 'tva7', 'libelle': 'Taux réduit (7 %)', 'taux': '7',
     'defaut': False},
    {'code': 'exonere', 'libelle': 'Exonéré (0 %)', 'taux': '0',
     'defaut': False},
]


class TauxTVA(TenantModel):
    """Un taux de TVA de référence par société (code + libellé FR + taux)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='taux_tva_referentiel')
    # Code technique stable (standard/panneaux/exonere/tva14/tva7…), unique par
    # société — sert de clé d'idempotence au seed.
    code = models.CharField(max_length=32)
    libelle = models.CharField(max_length=120)
    taux = models.DecimalField(max_digits=5, decimal_places=2)
    # Le taux STANDARD par défaut d'un nouveau document. Un seul par société
    # (garanti par le seed + ``set_defaut``) ; consommé par ``default_taux``.
    defaut = models.BooleanField(default=False)
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
    def default_taux(cls, company):
        """Taux STANDARD par défaut de ``company`` (Decimal) ou None.

        Alimente le DÉFAUT d'un nouveau document quand le corps ne fournit pas
        de ``taux_tva``. None (aucun référentiel actif) → l'appelant retombe sur
        le comportement historique (``CompanyProfile.tva_standard`` / 20).
        JAMAIS utilisé pour réécrire un document existant."""
        if company is None:
            return None
        row = cls.objects.filter(
            company=company, actif=True, defaut=True).first()
        return row.taux if row is not None else None

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
                    'defaut': entry['defaut'],
                    'actif': True,
                })
            if created:
                crees += 1
        return crees
