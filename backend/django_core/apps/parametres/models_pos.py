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
from decimal import Decimal

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
    # NTRET23 — Click & Collect (XPOS15) : délai (jours) avant libération
    # automatique d'une réservation jamais retirée. NULL/0 = désactivé —
    # aucune réservation n'expire jamais (comportement historique inchangé).
    delai_expiration_click_collect_jours = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Click & Collect : délai (jours) avant libération "
                  "automatique d'une réservation non retirée. Vide/0 = "
                  "désactivé.")
    # NTRET25 — arrondi caisse (espèces uniquement, jamais carte/virement) :
    # arrondit le montant dû en espèces au pas configuré. Désactivé par
    # défaut — comportement historique inchangé (aucun arrondi appliqué).
    arrondi_caisse_actif = models.BooleanField(default=False)
    arrondi_caisse_pas = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal('0.05'),
        help_text="Pas d'arrondi caisse en espèces (MAD), ex. 0.05 ou 0.10.")
    # NTRET32 — seuil (MAD, écart absolu) déclenchant une alerte proactive au
    # gérant/directeur sur un écart de clôture anormal (espèces OU TPE).
    # NULL/0 = désactivé — comportement actuel inchangé (aucune notification).
    seuil_alerte_ecart_caisse = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Seuil (MAD, écart absolu) déclenchant une alerte de '
                  'clôture anormale. Vide/0 = désactivé.')

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
