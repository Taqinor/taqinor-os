"""NTRET8 — Paramètres POS dédiés (onglet Paramètres → Point de vente).

Regroupe la config retail qui n'avait pas de foyer dédié :
  * taux horaire main-d'œuvre COMPTOIR (``ParametresPos.taux_horaire_comptoir``)
    — distinct de ``CompanyProfile.taux_horaire_sav`` (XFSM1) : un tarif SAV
    et un tarif comptoir peuvent légitimement diverger, jamais confondus ;
  * boutiques actives (``BoutiquePos``) — la liste des
    ``stock.EmplacementStock`` marquées « point de vente physique », avec
    adresse/horaires propres au reçu de caisse et une surface (m², NTRET16).

Le seuil de remise ligne comptoir RÉUTILISE tel quel
``CompanyProfile.discount_approval_threshold`` (T17, déjà partagé avec les
devis) — jamais dupliqué ici. La config imprimante/TPE RÉUTILISE
``pos.ConfigMaterielPOS`` (XPOS18) — jamais dupliquée ici non plus.

``BoutiquePos.emplacement`` référence ``stock.EmplacementStock`` par FK
CHAÎNE (``'stock.EmplacementStock'``) : ceci reste une lecture — aucune
migration ni modèle de ``apps/stock`` n'est jamais touché ici."""
from django.db import models

from core.models import TenantModel


class ParametresPos(TenantModel):
    """Un enregistrement par société (1-1) — onglet Paramètres → Point de
    vente. Valeurs vides/NULL par défaut = comportement actuel inchangé."""

    company = models.OneToOneField(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: composition — l'objet n'existe que dans sa societe
        related_name='parametres_pos')
    # Distinct de CompanyProfile.taux_horaire_sav (XFSM1) : NULL = aucun taux
    # configuré, aucune ligne main-d'œuvre auto-chiffrée côté comptoir.
    taux_horaire_comptoir = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Taux horaire main-d'œuvre comptoir (MAD/heure).")

    class Meta:
        verbose_name = 'Paramètres POS'
        verbose_name_plural = 'Paramètres POS'

    def __str__(self):
        return f'ParametresPos ({self.company_id})'

    @classmethod
    def get(cls, company):
        """Retourne (ou crée) l'enregistrement pour cette société — même
        patron que ``CompanyProfile.get``."""
        obj, _ = cls.objects.get_or_create(company=company)
        return obj


class BoutiquePos(TenantModel):
    """Une boutique physique active (NTRET8) : marque un
    ``stock.EmplacementStock`` EXISTANT comme point de vente, avec une
    adresse/des horaires propres au reçu (l'emplacement stock lui-même ne
    porte ni l'un ni l'autre)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: composition — l'objet n'existe que dans sa societe
        related_name='boutiques_pos')
    emplacement = models.OneToOneField(
        'stock.EmplacementStock', on_delete=models.CASCADE,  # on_delete: composition — la boutique EST cet emplacement de stock (1-1)
        related_name='boutique_pos')
    actif = models.BooleanField(default=True)
    adresse = models.TextField(blank=True, default='')
    horaires = models.CharField(max_length=255, blank=True, default='')
    # NTRET16 — surface (m²), pour le KPI « ventes au m² » du tableau de bord
    # retail (CA / surface). NULL = surface non renseignée (le KPI l'omet).
    surface_m2 = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Surface de vente (m²) — alimente le KPI ventes/m² (NTRET16).')

    class Meta:
        verbose_name = 'Boutique (point de vente)'
        verbose_name_plural = 'Boutiques (points de vente)'
        ordering = ['emplacement__nom']

    def __str__(self):
        return f'BoutiquePos ({self.emplacement_id})'
