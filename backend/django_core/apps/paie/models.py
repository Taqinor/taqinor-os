"""Modèles de la Paie marocaine (module `apps.paie`).

Socle des paramètres de paie conformes au cadre social marocain :

* ``ParametrePaie`` (PAIE2) — constantes sociales VERSIONNÉES par société et par
  ``date_effet`` : SMIG/SMAG, plafond CNSS, taux CNSS/AMO salarial & patronal,
  taux de la taxe de formation professionnelle. Un nouveau jeu de constantes
  s'ajoute à chaque évolution réglementaire (on ne modifie pas l'historique).
* ``BaremeIR`` / ``TrancheIR`` (PAIE4) — barème de l'Impôt sur le Revenu
  VERSIONNÉ par société et par ``date_effet`` : chaque barème porte ses tranches
  (borne min/max, taux, somme à déduire) ordonnées.

Tout est multi-société : chaque modèle porte un FK ``company`` posé côté serveur
(jamais lu du corps de requête). Aucun comportement existant n'est modifié — ce
module est entièrement additif.
"""
from decimal import Decimal

from django.db import models


# ── PAIE2 — Paramètres sociaux versionnés ──────────────────────────────────

class ParametrePaie(models.Model):
    """Constantes sociales d'une société à une ``date_effet`` donnée.

    Versionné : un jeu par date d'effet (SMIG/SMAG, plafond & taux CNSS/AMO,
    taux de formation professionnelle, frais professionnels et — PAIE5 —
    déduction pour charges de famille). L'historique est immuable — un nouveau
    barème réglementaire crée une nouvelle ligne, jamais une modification.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_parametres',
        verbose_name='Société',
    )
    date_effet = models.DateField(verbose_name="Date d'effet")
    smig = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='SMIG')
    smag = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='SMAG')
    plafond_cnss = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('6000'),
        verbose_name='Plafond CNSS')
    taux_cnss_salarial = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('4.48'),
        verbose_name='Taux CNSS salarial')
    taux_cnss_patronal = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('8.98'),
        verbose_name='Taux CNSS patronal')
    taux_amo_salarial = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('2.26'),
        verbose_name='Taux AMO salarial')
    taux_amo_patronal = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('2.26'),
        verbose_name='Taux AMO patronal')
    taux_formation_pro = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('1.6'),
        verbose_name='Taux formation professionnelle')
    # Frais professionnels (déduction IR) — barème 2026 : 35 % plafonné à
    # 2 500 MAD/mois quand le brut imposable n'excède pas 6 500 MAD/mois,
    # sinon 25 % plafonné à 2 916,67 MAD/mois.
    taux_frais_pro_bas = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('35'),
        verbose_name='Taux frais professionnels (brut ≤ seuil)')
    plafond_frais_pro_bas = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('2500'),
        verbose_name='Plafond frais professionnels (brut ≤ seuil)')
    taux_frais_pro_haut = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('25'),
        verbose_name='Taux frais professionnels (brut > seuil)')
    plafond_frais_pro_haut = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('2916.67'),
        verbose_name='Plafond frais professionnels (brut > seuil)')
    seuil_frais_pro = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('6500'),
        verbose_name='Seuil brut frais professionnels')
    # PAIE5 — Déduction pour charges de famille (déduction sur l'IR).
    # Cadre social marocain : un montant fixe par personne à charge et par mois,
    # plafonné à un nombre maximal de personnes (barème courant ≈ 30 MAD/mois et
    # par personne, plafond 6 → 360 MAD/mois). Valeurs ÉDITABLES par le fondateur.
    deduction_par_personne_a_charge = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('30'),
        verbose_name='Déduction mensuelle par personne à charge')
    plafond_personnes_a_charge = models.PositiveIntegerField(
        default=6,
        verbose_name='Plafond du nombre de personnes à charge')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    # PAIE3 — Validation fondateur des valeurs légales par défaut. Les valeurs
    # 2026 sont préremplies par le seed mais restent ÉDITABLES ; tant que le
    # fondateur ne les a pas confirmées, ce drapeau reste False.
    valide_par_fondateur = models.BooleanField(
        default=False, verbose_name='Validé par le fondateur')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Paramètre de paie'
        verbose_name_plural = 'Paramètres de paie'
        ordering = ['-date_effet']
        unique_together = [('company', 'date_effet')]

    def __str__(self):
        return f'Paramètres paie {self.date_effet}'


# ── PAIE4 — Barème IR versionné ────────────────────────────────────────────

class BaremeIR(models.Model):
    """Barème de l'Impôt sur le Revenu d'une société à une ``date_effet``.

    Versionné : chaque barème porte ses ``TrancheIR`` (cf. ``tranches``). Le
    barème en vigueur est celui dont la ``date_effet`` est la plus récente et
    qui couvre la période de paie.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_baremes_ir',
        verbose_name='Société',
    )
    libelle = models.CharField(
        max_length=120, default='Barème IR', verbose_name='Libellé')
    date_effet = models.DateField(verbose_name="Date d'effet")
    actif = models.BooleanField(default=True, verbose_name='Actif')
    # PAIE3 — barème officiel 2026 préprovisionné par le seed, éditable, en
    # attente de confirmation explicite du fondateur.
    valide_par_fondateur = models.BooleanField(
        default=False, verbose_name='Validé par le fondateur')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Barème IR'
        verbose_name_plural = 'Barèmes IR'
        ordering = ['-date_effet']
        unique_together = [('company', 'date_effet')]

    def __str__(self):
        return f'{self.libelle} {self.date_effet}'


class TrancheIR(models.Model):
    """Tranche d'un ``BaremeIR`` : intervalle de revenu, taux, somme à déduire.

    Le barème mensuel se calcule par tranche : pour un revenu net imposable, on
    applique le ``taux`` de la tranche couvrante puis on retranche
    ``somme_a_deduire`` (formule par tranche du barème marocain).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_tranches_ir',
        verbose_name='Société',
    )
    bareme = models.ForeignKey(
        BaremeIR,
        on_delete=models.CASCADE,
        related_name='tranches',
        verbose_name='Barème',
    )
    borne_min = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Borne minimale')
    borne_max = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Borne maximale')
    taux = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('0'),
        verbose_name='Taux')
    somme_a_deduire = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Somme à déduire')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')

    class Meta:
        verbose_name = "Tranche IR"
        verbose_name_plural = "Tranches IR"
        ordering = ['ordre']

    def __str__(self):
        return f'{self.borne_min}–{self.borne_max} @ {self.taux}%'
