"""FG274-FG275 — Mise en service & recette électrique (IEC 62446).

Couche ADDITIVE, propre à ``ventes``, pour la RECETTE d'une installation PV à la
mise en service selon la norme IEC 62446-1 (essais de mise en service des
systèmes PV connectés au réseau) et la capture de courbe I-V par string.

Modèles :
  * ``CommissioningTest`` (FG274) — fiche de recette d'un chantier : essais
    d'isolement, polarité, continuité de la terre, Voc/Isc par string, contrôle
    onduleur. Statut global de conformité.
  * ``IVCurveCapture`` (FG275) — mesure I-V par chaîne (string) comparée aux
    valeurs datasheet : détecte les modules défectueux dès la pose.

Multi-tenancy : ``company`` TOUJOURS forcée côté serveur. Lien au chantier en FK
CHAÎNE (jamais d'import installations). Aucun prix ; ne change aucun statut de
devis (RULE #4).
"""
from django.conf import settings
from django.db import models


class CommissioningTest(models.Model):
    """FG274 — fiche de recette IEC 62446 d'une mise en service."""

    class Resultat(models.TextChoices):
        EN_COURS = 'en_cours', 'En cours'
        CONFORME = 'conforme', 'Conforme'
        NON_CONFORME = 'non_conforme', 'Non conforme'
        RESERVES = 'reserves', 'Conforme avec réserves'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='commissioning_tests', verbose_name='Société')
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='commissioning_tests',
        verbose_name='Chantier')
    devis = models.ForeignKey(
        'ventes.Devis', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='commissioning_tests', verbose_name='Devis')
    date_essai = models.DateField(null=True, blank=True,
                                  verbose_name="Date des essais")
    # ── Essais IEC 62446 (catégorie 1) ──
    # Résistance d'isolement (MΩ) ; seuil de conformité usuel ≥ 1 MΩ.
    isolement_mohm = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name="Résistance d'isolement (MΩ)")
    isolement_ok = models.BooleanField(null=True, blank=True,
                                       verbose_name='Isolement conforme')
    polarite_ok = models.BooleanField(null=True, blank=True,
                                      verbose_name='Polarité correcte')
    # Continuité du conducteur de terre / liaisons équipotentielles (Ω).
    continuite_terre_ohm = models.DecimalField(
        max_digits=8, decimal_places=3, null=True, blank=True,
        verbose_name='Continuité terre (Ω)')
    continuite_terre_ok = models.BooleanField(
        null=True, blank=True, verbose_name='Continuité terre conforme')
    controle_onduleur_ok = models.BooleanField(
        null=True, blank=True, verbose_name='Contrôle onduleur conforme')
    resultat = models.CharField(
        max_length=14, choices=Resultat.choices, default=Resultat.EN_COURS,
        verbose_name='Résultat global')
    technicien = models.CharField(max_length=120, blank=True, null=True,
                                  verbose_name='Technicien')
    observations = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='commissioning_tests_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Fiche de recette (IEC 62446)'
        verbose_name_plural = 'Fiches de recette (IEC 62446)'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'resultat'],
                         name='ix_comm_comp_resultat'),
        ]

    def __str__(self):
        return f'Recette {self.resultat} — chantier {self.chantier_id}'


class IVCurveCapture(models.Model):
    """FG275 — mesure I-V par string comparée aux valeurs datasheet.

    Pour chaque chaîne (string), on relève Voc/Isc/Vmp/Imp/Pmax mesurés et on les
    confronte aux valeurs attendues (datasheet × nombre de modules en série).
    Un écart au-delà d'une tolérance signale un module défectueux dès la pose.
    """

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='iv_curve_captures', verbose_name='Société')
    # Une capture appartient à une fiche de recette (mise en service).
    recette = models.ForeignKey(
        CommissioningTest, on_delete=models.CASCADE,
        related_name='iv_curves', verbose_name='Fiche de recette')
    string_label = models.CharField(
        max_length=60, verbose_name='Chaîne (string)')
    n_modules_serie = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Modules en série')
    # ── Valeurs MESURÉES ──
    voc_mesure_v = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Voc mesurée (V)')
    isc_mesure_a = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Isc mesurée (A)')
    vmp_mesure_v = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Vmp mesurée (V)')
    imp_mesure_a = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Imp mesurée (A)')
    pmax_mesure_w = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Pmax mesurée (W)')
    # ── Valeurs ATTENDUES (datasheet × série) ──
    voc_attendu_v = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Voc attendue (V)')
    isc_attendu_a = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Isc attendue (A)')
    pmax_attendu_w = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Pmax attendue (W)')
    # Écart relatif sur la puissance (%) calculé côté service ; > tolérance =
    # alerte module défectueux.
    ecart_pmax_pct = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name='Écart Pmax (%)')
    defaut_detecte = models.BooleanField(
        default=False, verbose_name='Défaut détecté')
    observations = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Capture I-V (string)'
        verbose_name_plural = 'Captures I-V (string)'
        ordering = ['recette', 'string_label']
        indexes = [
            models.Index(fields=['company', 'recette'],
                         name='ix_ivc_comp_recette'),
        ]

    def __str__(self):
        return f'I-V {self.string_label} (recette {self.recette_id})'
