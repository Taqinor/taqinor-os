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


class AsBuiltPack(models.Model):
    """FG276 — pack documentaire « as-built » d'un chantier réceptionné.

    Enregistrement qui ASSEMBLE les références des pièces du dossier as-built
    (plans, schéma unifilaire, datasheets, numéros de série, photos, PV de
    réception) pour un chantier. Les pièces sont décrites comme des entrées de
    type + libellé + référence (pas de stockage binaire ici : on référence les
    documents déjà produits ailleurs — schéma FG252, fiches FG254, etc.).

    Lien au chantier en FK CHAÎNE (jamais d'import installations). Couche propre
    à ``ventes`` ; aucun prix ; ne change aucun statut de devis (RULE #4).
    """

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='asbuilt_packs', verbose_name='Société')
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='asbuilt_packs',
        verbose_name='Chantier')
    devis = models.ForeignKey(
        'ventes.Devis', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='asbuilt_packs', verbose_name='Devis')
    recette = models.ForeignKey(
        CommissioningTest, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='asbuilt_packs', verbose_name='Fiche de recette')
    titre = models.CharField(max_length=160, blank=True, null=True,
                             verbose_name='Titre du dossier')
    # Liste des pièces assemblées : [{type, libelle, reference}].
    pieces = models.JSONField(
        default=list, blank=True,
        verbose_name='Pièces assemblées (plans/schéma/datasheets/séries/'
                     'photos/PV)')
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='asbuilt_packs_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pack as-built'
        verbose_name_plural = 'Packs as-built'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'chantier'],
                         name='ix_asbuilt_comp_chant'),
        ]

    def __str__(self):
        return f'As-built — chantier {self.chantier_id}'


class AttestationConformite(models.Model):
    """FG277 — attestation/certificat de conformité électrique.

    Attestation liée à un chantier réceptionné : référentiel normatif, mesures
    clés relevées, signataire (nom/qualité/n° habilitation). Peut s'appuyer sur
    une fiche de recette (FG274) existante. Couche propre à ``ventes`` ; aucun
    prix ; ne change aucun statut de devis (RULE #4).
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EMISE = 'emise', 'Émise'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='attestations_conformite', verbose_name='Société')
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='attestations_conformite',
        verbose_name='Chantier')
    recette = models.ForeignKey(
        CommissioningTest, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='attestations_conformite',
        verbose_name='Fiche de recette')
    reference = models.CharField(max_length=40, blank=True, null=True,
                                 verbose_name='Référence attestation')
    referentiel = models.CharField(
        max_length=160, blank=True, null=True,
        verbose_name='Référentiel (NF C 15-100 / IEC 62446 …)')
    # Mesures clés synthétisées : [{libelle, valeur, unite, conforme}].
    mesures = models.JSONField(
        default=list, blank=True, verbose_name='Mesures relevées')
    signataire_nom = models.CharField(max_length=120, blank=True, null=True,
                                      verbose_name='Signataire')
    signataire_qualite = models.CharField(
        max_length=120, blank=True, null=True,
        verbose_name='Qualité du signataire')
    signataire_habilitation = models.CharField(
        max_length=80, blank=True, null=True,
        verbose_name="N° d'habilitation")
    date_emission = models.DateField(null=True, blank=True,
                                     verbose_name="Date d'émission")
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut')
    observations = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='attestations_conformite_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Attestation de conformité'
        verbose_name_plural = 'Attestations de conformité'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='ix_attconf_comp_statut'),
        ]

    def __str__(self):
        return f'Attestation conformité {self.reference or self.pk}'


class TestPerformanceReception(models.Model):
    """FG278 — test de performance de réception (Performance Ratio initial).

    PR mesuré à la mise en service (MES) confronté au PR attendu/contractuel.
    Archivé comme RÉFÉRENCE pour l'O&M et la garantie de production : l'écart
    initial sert de baseline. Couche propre à ``ventes`` ; aucun prix ; ne change
    aucun statut de devis (RULE #4).
    """

    class Verdict(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        ACCEPTE = 'accepte', 'Accepté'
        REFUSE = 'refuse', 'Refusé (sous le seuil)'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='tests_pr_reception', verbose_name='Société')
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='tests_pr_reception',
        verbose_name='Chantier')
    recette = models.ForeignKey(
        CommissioningTest, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tests_pr_reception', verbose_name='Fiche de recette')
    date_mesure = models.DateField(null=True, blank=True,
                                   verbose_name='Date de mesure')
    # Énergie mesurée sur la période d'essai et énergie théorique attendue.
    energie_mesuree_kwh = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Énergie mesurée (kWh)')
    energie_attendue_kwh = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Énergie attendue (kWh)')
    # PR (sans unité, 0–1) : mesuré, attendu/contractuel, seuil d'acceptation.
    pr_mesure = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True,
        verbose_name='PR mesuré')
    pr_attendu = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True,
        verbose_name='PR attendu')
    pr_seuil_acceptation = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True,
        verbose_name="PR seuil d'acceptation")
    # Écart relatif (%) mesuré vs attendu, calculé côté serveur.
    ecart_pct = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name='Écart PR (%)')
    verdict = models.CharField(
        max_length=12, choices=Verdict.choices, default=Verdict.EN_ATTENTE,
        verbose_name='Verdict')
    observations = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='tests_pr_reception_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Test de performance de réception (PR)'
        verbose_name_plural = 'Tests de performance de réception (PR)'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'verdict'],
                         name='ix_prrec_comp_verdict'),
        ]

    def __str__(self):
        return f'PR réception {self.pr_mesure} — chantier {self.chantier_id}'


class AttestationRE(models.Model):
    """FG287 — certificat / attestation d'énergie renouvelable produite.

    Atteste l'énergie verte produite (kWh) et le CO₂ évité (t) sur une période
    pour un système/chantier, signée par un responsable. Réutilise le facteur
    réseau de l'energy report côté service pour dériver le CO₂ — jamais lu du
    corps. Couche propre à ``ventes`` ; aucun prix ; ne change aucun statut de
    devis (RULE #4).
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EMISE = 'emise', 'Émise'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='attestations_re', verbose_name='Société')
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='attestations_re',
        verbose_name='Chantier')
    reference = models.CharField(max_length=40, blank=True, null=True,
                                 verbose_name='Référence attestation')
    periode_debut = models.DateField(null=True, blank=True,
                                     verbose_name='Période début')
    periode_fin = models.DateField(null=True, blank=True,
                                   verbose_name='Période fin')
    energie_kwh = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Énergie renouvelable produite (kWh)')
    # Facteur réseau (kg CO₂/kWh) appliqué et CO₂ évité (t) — dérivés serveur.
    facteur_co2_kg_kwh = models.DecimalField(
        max_digits=6, decimal_places=4, null=True, blank=True,
        verbose_name='Facteur réseau (kg CO₂/kWh)')
    co2_evite_t = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        verbose_name='CO₂ évité (t)')
    signataire_nom = models.CharField(max_length=120, blank=True, null=True,
                                      verbose_name='Signataire')
    date_emission = models.DateField(null=True, blank=True,
                                     verbose_name="Date d'émission")
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut')
    observations = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='attestations_re_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Attestation d'énergie renouvelable"
        verbose_name_plural = "Attestations d'énergie renouvelable"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='ix_attre_comp_statut'),
        ]

    def __str__(self):
        return f'Attestation RE {self.reference or self.pk}'
