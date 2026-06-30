"""FG268-FG271 — Dossier réglementaire de raccordement (côté ventes).

Couche ADDITIVE, propre à ``ventes``, pour suivre la constitution & le dépôt du
dossier réglementaire d'une affaire (loi 82-21 / ONEE / distributeur / ANRE).
Elle complète — sans la dupliquer ni la fusionner — la couche chantier
(``installations.Installation.dossier_statut/regime_8221``) : on ne touche jamais
l'app installations, le lien éventuel au chantier passe par une FK CHAÎNE.

Modèles :
  * ``RegulatoryDossier`` (FG268) — dossier rattaché à un ``Devis``, avec régime,
    opérateur et dates clés.
  * ``DossierChecklistItem`` (FG268) — checklist par ÉTAPE (dépôt/étude/
    convention/comptage) avec échéance, statut et drapeau de relance.
  * ``DossierExchange`` (FG269) — journal de la navette opérateur
    (envoi/accusé/complément/refus/approbation).
  * ``SubventionDossier`` (FG270) — éligibilité & suivi des subventions
    (MASEN/IRESEN/Tatwir : statut/montant/pièces).
  * ``Regularisation8221`` (FG271) — workflow Article 33 pour les installations
    existantes (drapeau présent) + suivi de la déclaration générée.

Multi-tenancy : ``company`` TOUJOURS forcée côté serveur (jamais lue du corps).
Aucun prix d'achat / marge n'est porté. Ne change aucun statut de devis (RULE
#4) : la chaîne brouillon/envoye/accepte/refuse/expire reste une couche séparée.
"""
from django.conf import settings
from django.db import models


# Codes de régime alignés sur ``Installation.Regime8221`` (FG267). On NE
# redéfinit pas l'énum installations (couche découplée) : on liste les libellés
# localement pour les choix d'affichage.
REGIME_CHOICES = [
    ('non_concerne', "Non concerné (hors loi 82-21)"),
    ('declaration_bt', "Déclaration basse tension"),
    ('accord_raccordement', "Accord de raccordement"),
    ('autorisation_anre', "Autorisation ANRE"),
]


class RegulatoryDossier(models.Model):
    """FG268 — dossier réglementaire de raccordement d'une affaire (ventes)."""

    class Statut(models.TextChoices):
        EN_CONSTITUTION = 'en_constitution', 'En constitution'
        DEPOSE = 'depose', 'Déposé'
        EN_INSTRUCTION = 'en_instruction', 'En instruction'
        COMPLEMENT_DEMANDE = 'complement_demande', 'Complément demandé'
        APPROUVE = 'approuve', 'Approuvé'
        REFUSE = 'refuse', 'Refusé'
        COMPTAGE_POSE = 'comptage_pose', 'Comptage posé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='dossiers_reglementaires', verbose_name='Société')
    # Rattachement principal : le devis de l'affaire (même app).
    devis = models.ForeignKey(
        'ventes.Devis', on_delete=models.CASCADE,
        related_name='dossiers_reglementaires', verbose_name='Devis')
    # Lien OPTIONNEL au chantier (app installations) en FK CHAÎNE — jamais
    # d'import du modèle installations.
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='dossiers_reglementaires_ventes',
        verbose_name='Chantier')
    regime_8221 = models.CharField(
        max_length=24, choices=REGIME_CHOICES, default='non_concerne',
        verbose_name='Régime loi 82-21')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.EN_CONSTITUTION, verbose_name='Statut du dossier')
    operateur = models.CharField(
        max_length=120, blank=True, null=True,
        verbose_name="Opérateur (ONEE / régie / distributeur)")
    reference_dossier = models.CharField(
        max_length=120, blank=True, null=True,
        verbose_name='Référence opérateur')
    date_depot = models.DateField(null=True, blank=True,
                                  verbose_name='Date de dépôt')
    date_decision = models.DateField(null=True, blank=True,
                                     verbose_name='Date de décision')
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='dossiers_reg_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Dossier réglementaire'
        verbose_name_plural = 'Dossiers réglementaires'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='ix_dossier_comp_statut'),
        ]

    def __str__(self):
        return f'Dossier {self.regime_8221} — devis {self.devis_id}'


class DossierChecklistItem(models.Model):
    """FG268 — pièce/étape du dossier avec échéance et relance.

    L'``etape`` regroupe les pièces par phase de soumission (dépôt, étude,
    convention, comptage). ``relance_due`` est un DRAPEAU calculable/éditable
    (jamais d'envoi automatique — couche relance manuelle, comme le recouvrement).
    """

    class Etape(models.TextChoices):
        DEPOT = 'depot', 'Dépôt'
        ETUDE = 'etude', 'Étude'
        CONVENTION = 'convention', 'Convention'
        COMPTAGE = 'comptage', 'Comptage'

    class Statut(models.TextChoices):
        A_FAIRE = 'a_faire', 'À faire'
        EN_COURS = 'en_cours', 'En cours'
        FOURNI = 'fourni', 'Fourni'
        VALIDE = 'valide', 'Validé'
        NON_APPLICABLE = 'na', 'Non applicable'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='dossier_checklist_items', verbose_name='Société')
    dossier = models.ForeignKey(
        RegulatoryDossier, on_delete=models.CASCADE,
        related_name='checklist_items', verbose_name='Dossier')
    # Code stable de la pièce (aligné sur regulatory_docs.required_documents).
    code = models.CharField(max_length=60, verbose_name='Code pièce/étape')
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    etape = models.CharField(
        max_length=12, choices=Etape.choices, default=Etape.DEPOT,
        verbose_name='Étape de soumission')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.A_FAIRE,
        verbose_name='Statut')
    obligatoire = models.BooleanField(default=True,
                                      verbose_name='Obligatoire')
    date_echeance = models.DateField(null=True, blank=True,
                                     verbose_name="Date limite")
    relance_due = models.BooleanField(
        default=False, verbose_name='Relance à faire')
    ordre = models.PositiveSmallIntegerField(default=0,
                                             verbose_name='Ordre')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pièce de dossier'
        verbose_name_plural = 'Pièces de dossier'
        ordering = ['etape', 'ordre', 'id']
        indexes = [
            models.Index(fields=['company', 'dossier'],
                         name='ix_dosit_comp_dossier'),
        ]

    def __str__(self):
        return f'{self.etape}:{self.code} ({self.statut})'


class DossierExchange(models.Model):
    """FG269 — journal de la navette opérateur (échanges ONEE/distributeur)."""

    class Sens(models.TextChoices):
        ENVOI = 'envoi', 'Envoi (vers opérateur)'
        RECU = 'recu', 'Reçu (de opérateur)'

    class TypeEchange(models.TextChoices):
        DEPOT = 'depot', 'Dépôt de dossier'
        ACCUSE = 'accuse', 'Accusé de réception'
        COMPLEMENT = 'complement', 'Demande de complément'
        REPONSE_COMPLEMENT = 'reponse_complement', 'Réponse au complément'
        REFUS = 'refus', 'Refus'
        APPROBATION = 'approbation', 'Approbation'
        RELANCE = 'relance', 'Relance'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='dossier_exchanges', verbose_name='Société')
    dossier = models.ForeignKey(
        RegulatoryDossier, on_delete=models.CASCADE,
        related_name='exchanges', verbose_name='Dossier')
    sens = models.CharField(
        max_length=5, choices=Sens.choices, default=Sens.ENVOI,
        verbose_name='Sens')
    type_echange = models.CharField(
        max_length=20, choices=TypeEchange.choices,
        default=TypeEchange.AUTRE, verbose_name="Type d'échange")
    date_echange = models.DateField(verbose_name="Date de l'échange")
    objet = models.CharField(max_length=200, blank=True, null=True,
                             verbose_name='Objet')
    detail = models.TextField(blank=True, null=True)
    piece_jointe = models.CharField(
        max_length=500, blank=True, null=True,
        verbose_name='Pièce jointe (chemin/clé)')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='dossier_exchanges_crees')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Échange de dossier"
        verbose_name_plural = "Échanges de dossier"
        ordering = ['-date_echange', '-id']
        indexes = [
            models.Index(fields=['company', 'dossier'],
                         name='ix_dosex_comp_dossier'),
        ]

    def __str__(self):
        return f'{self.sens}:{self.type_echange} {self.date_echange}'


class SubventionDossier(models.Model):
    """FG270 — éligibilité & suivi d'un dossier de subvention/incitation."""

    class Programme(models.TextChoices):
        MASEN = 'masen', 'MASEN'
        IRESEN = 'iresen', 'IRESEN'
        TATWIR = 'tatwir', 'Tatwir (PME)'
        AUTRE = 'autre', 'Autre programme'

    class Statut(models.TextChoices):
        A_QUALIFIER = 'a_qualifier', 'À qualifier'
        ELIGIBLE = 'eligible', 'Éligible'
        NON_ELIGIBLE = 'non_eligible', 'Non éligible'
        DEPOSE = 'depose', 'Déposé'
        ACCORDE = 'accorde', 'Accordé'
        REFUSE = 'refuse', 'Refusé'
        VERSE = 'verse', 'Versé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='subvention_dossiers', verbose_name='Société')
    devis = models.ForeignKey(
        'ventes.Devis', on_delete=models.CASCADE,
        related_name='subvention_dossiers', verbose_name='Devis')
    programme = models.CharField(
        max_length=10, choices=Programme.choices,
        default=Programme.AUTRE, verbose_name='Programme')
    statut = models.CharField(
        max_length=14, choices=Statut.choices,
        default=Statut.A_QUALIFIER, verbose_name='Statut')
    montant_demande = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Montant demandé (MAD)')
    montant_accorde = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Montant accordé (MAD)')
    reference = models.CharField(max_length=120, blank=True, null=True,
                                 verbose_name='Référence dossier')
    eligibilite_note = models.TextField(
        blank=True, null=True, verbose_name="Note d'éligibilité")
    # Pièces requises/fournies, liste JSON [{code,label,fourni}].
    pieces = models.JSONField(default=list, blank=True,
                              verbose_name='Pièces')
    date_depot = models.DateField(null=True, blank=True,
                                  verbose_name='Date de dépôt')
    date_decision = models.DateField(null=True, blank=True,
                                     verbose_name='Date de décision')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='subvention_dossiers_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Dossier de subvention'
        verbose_name_plural = 'Dossiers de subvention'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='ix_subv_comp_statut'),
        ]

    def __str__(self):
        return f'Subvention {self.programme} — devis {self.devis_id}'


class Regularisation8221(models.Model):
    """FG271 — workflow de régularisation Article 33 (installations existantes).

    Pour une installation EXISTANTE à régulariser (drapeau présent côté
    chantier), suit l'avancement de la régularisation 82-21 et conserve la
    DÉCLARATION générée (chemin/clé du PDF, jamais le rendu). Ne touche pas
    l'app installations : lien chantier en FK chaîne.
    """

    class Statut(models.TextChoices):
        A_REGULARISER = 'a_regulariser', 'À régulariser'
        DECLARATION_GENEREE = 'declaration_generee', 'Déclaration générée'
        DEPOSEE = 'deposee', 'Déposée'
        REGULARISEE = 'regularisee', 'Régularisée'
        REFUSEE = 'refusee', 'Refusée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='regularisations_8221', verbose_name='Société')
    devis = models.ForeignKey(
        'ventes.Devis', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='regularisations_8221', verbose_name='Devis')
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='regularisations_8221_ventes',
        verbose_name='Chantier')
    regime_8221 = models.CharField(
        max_length=24, choices=REGIME_CHOICES, default='declaration_bt',
        verbose_name='Régime visé')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.A_REGULARISER, verbose_name='Statut')
    puissance_kwc = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Puissance (kWc)')
    date_mise_en_service_initiale = models.DateField(
        null=True, blank=True,
        verbose_name='Date de mise en service initiale')
    declaration_pdf = models.CharField(
        max_length=500, blank=True, null=True,
        verbose_name='Déclaration générée (chemin/clé)')
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='regularisations_8221_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Régularisation 82-21 (Art. 33)'
        verbose_name_plural = 'Régularisations 82-21 (Art. 33)'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='ix_reg33_comp_statut'),
        ]

    def __str__(self):
        return f'Régularisation Art.33 — {self.regime_8221} ({self.statut})'
