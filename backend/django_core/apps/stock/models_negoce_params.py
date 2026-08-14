"""NTDST30 — Paramètres NÉGOCE par société (singleton).

Un seul enregistrement par société : les fonctionnalités de négoce
(consignation, van sales, RFA, ATP) y lisent leurs réglages au lieu de valeurs
codées en dur. Changer un seuil se fait donc SANS redéploiement.

Le singleton est créé À LA DEMANDE (``ParametresNegoce.get(company)``) : aucune
migration de données, aucune société n'est touchée tant que personne n'ouvre
l'écran. Les DÉFAUTS reproduisent exactement le comportement d'avant ce lot.
"""
from django.db import models

from core.models import TenantModel


class ParametresNegoce(TenantModel):
    """Réglages négoce d'une société (un seul par société)."""

    company = models.OneToOneField(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant — le paramétrage d'une société supprimée n'a plus d'objet
        related_name='parametres_negoce_stock', verbose_name='Société')

    consignation_activee = models.BooleanField(
        default=True,
        help_text='Active la consignation client (NTDST3). Désactivée, ses '
                  'endpoints renvoient 403 explicite.')
    van_sales_active = models.BooleanField(
        default=True,
        help_text='Active les tournées de vente / stock embarqué (NTDST14).')
    seuil_alerte_rfa_pct = models.PositiveIntegerField(
        default=80,
        help_text='Progression (%) du seuil de CA déclenchant la première '
                  'alerte RFA.')
    heures_tournee_defaut = models.PositiveIntegerField(
        default=7, help_text='Durée par défaut d\'une tournée (heures).')
    atp_horizon_jours = models.PositiveIntegerField(
        default=30,
        help_text='Fenêtre de recherche des commandes fournisseur confirmées '
                  'pour la disponibilité ATP (NTDST10).')
    seuil_alerte_marge_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Seuil de marge moyenne drop-ship sous lequel alerter '
                  '(NTDST48). Vide = aucune alerte.')
    cout_rupture_jour_mad = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Coût estimé d\'un jour de rupture (MAD) — alimente le TCO '
                  'fournisseur (NTSCM26). Vide = le retard ne pèse rien.')

    class Meta:
        verbose_name = 'Paramètres négoce'
        verbose_name_plural = 'Paramètres négoce'

    def __str__(self):
        return f'Paramètres négoce société {self.company_id}'

    @classmethod
    def get(cls, company):
        """Singleton de la société, créé à la demande avec les défauts.

        ``get_or_create`` sur ``company`` est sûr ici : la relation est
        ``OneToOneField`` (contrainte d'unicité côté base), donc deux requêtes
        concurrentes ne peuvent pas créer deux lignes.
        """
        obj, _ = cls.objects.get_or_create(company=company)
        return obj
