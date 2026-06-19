"""N64 / N65 — Tarification ONEE + hypothèses ROI/productible, par société.

Une couche de RÉGLAGES VERSIONNÉS par société pour tout ce qui pilote le calcul
d'économies/ROI d'un projet solaire au Maroc : le barème ONEE résidentiel (TTC),
le modèle de facturation (progressif ≤150 kWh, sélectif au-delà), la classe
« force motrice / agricole » (moins chère), la valorisation du surplus injecté
(par défaut DÉSACTIVÉE — pas de net-metering au Maroc), et les hypothèses de
productible (PVGIS au point GPS exact, repli manuel conservateur hors-ligne).

TOUTE valeur est éditable ; son DÉFAUT codé ici est EXACTEMENT le chiffre
réel/spec courant (barème ONEE 2024 TTC). Rien n'est codé en dur ailleurs :
le service de calcul (``tariff.py``) lit ces réglages. Les hypothèses ROI par
défaut sont CONSERVATRICES (elles sous-estiment les économies).

``company`` est posée CÔTÉ SERVEUR (jamais lue du corps d'une requête). Un seul
enregistrement par société (singleton, comme ``CompanyProfile`` /
``DocumentTemplates``). ``version`` s'incrémente à chaque sauvegarde modifiée
pour tracer quelle révision du barème a servi à un chiffrage.

``app_label`` explicite : ce module n'est pas importé par ``models.py`` (gardé
séparé pour l'indépendance des lanes) ; il est chargé via ``apps.py`` ready().
La table reste ``parametres_tariffsettings`` (additif, une seule migration).

Aucune donnée de prix d'achat / marge : ce sont des tarifs publics de réseau et
des hypothèses d'irradiation, jamais des données client-confidentielles.
"""
from decimal import Decimal

from django.db import models


# ── Barème résidentiel ONEE — défauts TTC (jamais de TVA en plus) ─────────────
# Tranches mensuelles (kWh) → prix MAD/kWh TTC. Spec founder 2024 :
#   0–100   = 0.9010
#   101–150 = 1.0732   (et 151–210 = 1.0732 aussi)
#   211–310 = 1.1676
#   311–510 = 1.3817
#   >510    = 1.5958
# Le service de calcul applique le MODÈLE (progressif ≤150 / sélectif >150 avec
# tolérance 10 kWh décalant les bornes opératoires à 210/310/510). Le barème ici
# n'est que la liste des paliers + prix ; la logique vit dans ``tariff.py``.
DEFAULT_RESIDENTIAL_TIERS = [
    {"max_kwh": 100, "prix_kwh_ttc": "0.9010"},
    {"max_kwh": 150, "prix_kwh_ttc": "1.0732"},
    {"max_kwh": 210, "prix_kwh_ttc": "1.0732"},
    {"max_kwh": 310, "prix_kwh_ttc": "1.1676"},
    {"max_kwh": 510, "prix_kwh_ttc": "1.3817"},
    {"max_kwh": None, "prix_kwh_ttc": "1.5958"},  # None = palier supérieur ouvert
]


class TariffSettings(models.Model):
    """Tarif ONEE + hypothèses ROI/productible éditables, par société (singleton).

    Tous les champs portent leur DÉFAUT = chiffre courant/spec. Tant que rien
    n'est édité, ``tariff.py`` calcule avec ces défauts conservateurs.
    """

    company = models.OneToOneField(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='tariff_settings',
    )

    # ── N64 — barème résidentiel ONEE (liste de paliers, prix TTC) ──
    # JSON : [{max_kwh: int|null, prix_kwh_ttc: "0.9010"}, ...] ordonné croissant.
    # NULL/[] → le service applique ``DEFAULT_RESIDENTIAL_TIERS``.
    residential_tiers = models.JSONField(null=True, blank=True)

    # Tolérance (kWh) qui décale les bornes opératoires du mode sélectif
    # (210/310/510 au lieu de 200/300/500). Défaut 10 (spec).
    tolerance_kwh = models.PositiveIntegerField(default=10)

    # Seuil (kWh/mois) à partir duquel on bascule du PROGRESSIF au SÉLECTIF.
    # Défaut 150 (spec : ≤150 progressif, >150 sélectif).
    selective_threshold_kwh = models.PositiveIntegerField(default=150)

    # ── N64 — classe « force motrice / agricole » (séparée, moins chère) ──
    # Tarif unique MAD/kWh TTC pour pompage/force motrice : ~0.90–0.95, JAMAIS
    # le haut barème résidentiel. Défaut conservateur 0.9500.
    force_motrice_prix_kwh_ttc = models.DecimalField(
        max_digits=6, decimal_places=4, default=Decimal('0.9500'))

    # ── N64 — surplus injecté ──
    # Compensation/net-metering du surplus ? Par défaut FAUX (pas de
    # net-metering au Maroc : le surplus vaut zéro, on dimensionne sur
    # l'autoconsommation).
    surplus_injecte_compense = models.BooleanField(default=False)
    # Tarif de rachat du surplus (MAD/kWh) — n'a d'effet QUE si la compensation
    # est activée ci-dessus. Défaut 0 (surplus non valorisé).
    surplus_prix_kwh_ttc = models.DecimalField(
        max_digits=6, decimal_places=4, default=Decimal('0.0000'))

    # ── N64 — hypothèses ROI conservatrices (sous-estiment les économies) ──
    # Part de la production solaire réellement autoconsommée (et donc évitée sur
    # la facture) si rien d'autre n'est connu. Conservateur : 70 %.
    autoconsommation_pct_defaut = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('70.00'))
    # Pertes système globales appliquées au productible (onduleur, câblage,
    # salissure, température). Conservateur : 20 % de pertes.
    pertes_systeme_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('20.00'))

    # ── N65 — productible / irradiation (PVGIS + repli manuel) ──
    # Interroger PVGIS au point GPS exact du site ?
    pvgis_actif = models.BooleanField(default=True)
    # Repli conservateur (kWh/kWc/an) quand PVGIS est indisponible (réseau
    # bloqué) ou désactivé. Maroc : 1500–1900 ; défaut prudent 1500.
    productible_manuel_kwh_kwc = models.DecimalField(
        max_digits=7, decimal_places=1, default=Decimal('1500.0'))
    # Inclinaison & azimut par défaut des modules (convention founder N65 :
    # Sud 0 / Est −90 / Ouest +90 / Nord +180). Toiture marocaine usuelle ~30°.
    inclinaison_defaut_deg = models.PositiveIntegerField(default=30)
    azimut_defaut_deg = models.IntegerField(default=0)

    # ── versionnement (incrémenté à chaque modification effective) ──
    version = models.PositiveIntegerField(default=1)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'parametres'
        verbose_name = 'Tarification & ROI'
        verbose_name_plural = 'Tarifications & ROI'

    def __str__(self):
        return f'Tarification & ROI (v{self.version})'

    @classmethod
    def get(cls, company=None):
        """Retourne (ou crée) l'enregistrement pour une société donnée.

        Sans société, retombe sur l'instance pk=1 (rétro-compat, comme
        ``CompanyProfile.get`` / ``DocumentTemplates.get``)."""
        if company is not None:
            obj, _ = cls.objects.get_or_create(company=company)
            return obj
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def effective_tiers(self):
        """Liste de paliers à utiliser : surcharge si renseignée, sinon défaut.

        Chaque palier = {max_kwh: int|None, prix_kwh_ttc: Decimal}. La liste est
        triée par borne croissante (None = palier ouvert en dernier).
        """
        raw = self.residential_tiers if isinstance(
            self.residential_tiers, list) and self.residential_tiers \
            else DEFAULT_RESIDENTIAL_TIERS
        tiers = []
        for t in raw:
            mk = t.get('max_kwh', None)
            tiers.append({
                'max_kwh': None if mk in (None, '', 0) else int(mk),
                'prix_kwh_ttc': Decimal(str(t.get('prix_kwh_ttc', '0'))),
            })
        # Bornes finies d'abord (croissant), palier ouvert (None) en dernier.
        tiers.sort(key=lambda t: (t['max_kwh'] is None, t['max_kwh'] or 0))
        return tiers
