"""Modèles du registre des assurances & sinistres d'entreprise (Groupe NTASS).

Couvre les polices d'ENTREPRISE (RC pro, décennale, multirisque, cyber,
homme-clé) — distinctes des polices VÉHICULE qui restent dans
``flotte.AssuranceVehicule``/``flotte.Sinistre`` (jamais dupliquées ici,
référencées en string-FK via ``ActifCouvert``/``flotte_sinistre_id``) — et des
cautions bancaires marché (``compta.CautionBancaire``/``RetenueGarantie``).

Frontières (voir docs/plans/PLAN_FINANCE.md Groupe NTASS) :
  - ``flotte`` garde ses polices/sinistres véhicule ;
  - le futur NTGRC gardera le registre de risques ERM (string-FK ``risque_ref``) ;
  - ``qhse`` garde les accidents du travail ;
  - le futur NTJUR prendra le relais quand un sinistre devient contentieux
    (string-FK ``dossier_contentieux_ref``) ;
  - le futur NTPRO sera la cible string-FK pour les sites/biens immobiliers.
"""
from django.db import models

from core.models import TenantModel


# ── NTASS1 — Registre des assureurs & courtiers ────────────────────────────

class Assureur(TenantModel):
    """Compagnie d'assurance (NTASS1). Registre scopé société."""

    # SCA4 — socle multi-société via ``TenantModel`` (FK company + timestamps).
    # ``company`` est REdéclarée pour conserver le ``related_name`` historique
    # (motif ARC1 documenté).
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='assureurs', verbose_name='Société')
    raison_sociale = models.CharField(max_length=200, verbose_name='Raison sociale')
    ice = models.CharField(max_length=30, blank=True, default='', verbose_name='ICE')
    telephone = models.CharField(max_length=30, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    adresse = models.TextField(blank=True, default='')
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ['raison_sociale']
        verbose_name = 'Assureur'
        verbose_name_plural = 'Assureurs'

    def __str__(self):
        return self.raison_sociale


class Courtier(TenantModel):
    """Courtier / intermédiaire d'assurance (NTASS1), distinct de l'assureur.

    Registre scopé société. Un courtier n'émet pas les polices lui-même (c'est
    l'assureur) mais intermédie ; ``numero_agrement`` est son numéro d'agrément
    professionnel (ACAPS au Maroc)."""

    # SCA4 — socle ``TenantModel`` ; ``company`` REdéclarée (related_name ARC1).
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='courtiers', verbose_name='Société')
    raison_sociale = models.CharField(max_length=200, verbose_name='Raison sociale')
    numero_agrement = models.CharField(
        max_length=60, blank=True, default='', verbose_name="Numéro d'agrément")
    telephone = models.CharField(max_length=30, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ['raison_sociale']
        verbose_name = 'Courtier'
        verbose_name_plural = 'Courtiers'

    def __str__(self):
        return self.raison_sociale


# ── NTASS2 — Police d'assurance d'entreprise ───────────────────────────────

class PoliceAssurance(TenantModel):
    """Police d'assurance d'ENTREPRISE (NTASS2) — RC pro, décennale,
    multirisque, cyber, homme-clé, transport de marchandises, bris de machine,
    perte d'exploitation… Distincte de ``flotte.AssuranceVehicule`` (véhicule)
    et des cautions bancaires marché (``compta.CautionBancaire``).

    ``statut`` est une machine INDÉPENDANTE (pas ``STAGES.py`` — le funnel CRM
    n'a rien à voir avec le cycle de vie d'une police)."""

    class TypePolice(models.TextChoices):
        RC_PRO = 'rc_pro', 'RC professionnelle'
        DECENNALE = 'decennale', 'Décennale'
        MULTIRISQUE = 'multirisque', 'Multirisque'
        CYBER = 'cyber', 'Cyber'
        HOMME_CLE = 'homme_cle', 'Homme-clé'
        TRANSPORT_MARCHANDISES = (
            'transport_marchandises', 'Transport de marchandises')
        BRIS_MACHINE = 'bris_machine', 'Bris de machine'
        PERTE_EXPLOITATION = 'perte_exploitation', "Perte d'exploitation"
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        ACTIVE = 'active', 'Active'
        SUSPENDUE = 'suspendue', 'Suspendue'
        RESILIEE = 'resiliee', 'Résiliée'
        EXPIREE = 'expiree', 'Expirée'

    # SCA4 — socle ``TenantModel`` ; ``company`` REdéclarée (related_name ARC1).
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='polices_assurance', verbose_name='Société')
    assureur = models.ForeignKey(
        Assureur, on_delete=models.PROTECT,
        related_name='polices', verbose_name='Assureur')
    courtier = models.ForeignKey(
        Courtier, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='polices', verbose_name='Courtier')
    numero_police = models.CharField(
        max_length=80, verbose_name='Numéro de police')
    type_police = models.CharField(
        max_length=30, choices=TypePolice.choices,
        default=TypePolice.AUTRE, verbose_name='Type de police')
    libelle = models.CharField(max_length=200, blank=True, default='')
    date_effet = models.DateField(verbose_name="Date d'effet")
    date_echeance = models.DateField(verbose_name="Date d'échéance")
    tacite_reconduction = models.BooleanField(
        default=False, verbose_name='Tacite reconduction')
    prime_annuelle_ht = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Prime annuelle HT')
    statut = models.CharField(
        max_length=15, choices=Statut.choices, default=Statut.ACTIVE)
    # ARC26 — le contrat scanné n'est plus un FileField brut : il est rattaché
    # via ``records.Attachment`` (cible ``assurances.policeassurance`` déclarée
    # dans ``platform.py``), stocké MinIO comme toute pièce jointe transverse.
    notes = models.TextField(blank=True, default='')
    # NTASS9 — versioning léger : lien vers la police remplacée au renouvellement.
    police_precedente = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='polices_suivantes', verbose_name='Police précédente')
    # NTASS22 — assurance HOMME-CLÉ : string-FK (id brut) vers rh.DossierEmploye
    # (jamais une vraie FK cross-app) ; résolu en libellé via rh.selectors.
    employe_ref = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Employé couvert (homme-clé, string-FK rh)')
    # NTASS23 — police CYBER : clauses IT structurées en JSON libre (plafond
    # ransomware, notification CNDP sous X h, couverture perte de données,
    # prestataire forensic mandaté…). Champ libre, pas de nouveau modèle.
    cyber_clauses = models.JSONField(
        default=dict, blank=True, verbose_name='Clauses cyber (JSON)')
    # ``created_at`` / ``updated_at`` fournis par ``TenantModel`` (SCA4).

    class Meta:
        ordering = ['date_echeance']
        verbose_name = "Police d'assurance"
        verbose_name_plural = "Polices d'assurance"
        unique_together = [('company', 'numero_police')]
        indexes = [
            models.Index(fields=['company', 'statut']),
            models.Index(fields=['company', 'type_police']),
            models.Index(fields=['company', 'date_echeance']),
        ]

    def __str__(self):
        return f'{self.numero_police} ({self.get_type_police_display()})'


# ── NTASS3 — Chatter police ─────────────────────────────────────────────────
# ARC8 — le chatter de ``PoliceAssurance`` converge sur ``records.Activity``
# (via ``records.services.log_activity`` — voir ``services.py``) : plus aucun
# modèle ``*Activity`` maison. La timeline se lit via ``records.chatter_qs`` et
# se sérialise avec ``records.ChatterActivitySerializer`` (voir ``views.py``).


# ── NTASS4 — Garanties, plafonds & franchises par police ───────────────────

class GarantiePolice(TenantModel):
    """Une garantie d'une ``PoliceAssurance`` avec son plafond/franchise
    propres (NTASS4). Une police porte plusieurs garanties (ex. une DÉCENNALE
    peut avoir 3 garanties à plafonds différents)."""

    # SCA4 — socle ``TenantModel`` ; ``company`` REdéclarée (related_name ARC1).
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='garanties_police', verbose_name='Société')
    police = models.ForeignKey(
        PoliceAssurance, on_delete=models.CASCADE, related_name='garanties')
    libelle_garantie = models.CharField(
        max_length=200, verbose_name='Libellé de la garantie')
    plafond_indemnisation = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name="Plafond d'indemnisation")
    franchise_montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Franchise (montant)')
    franchise_pourcentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='Franchise (%)')
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['id']
        verbose_name = 'Garantie de police'
        verbose_name_plural = 'Garanties de police'
        indexes = [models.Index(fields=['police'])]

    def __str__(self):
        return f'{self.libelle_garantie} ({self.police_id})'


# ── NTASS5 — Échéancier de primes ───────────────────────────────────────────

class EcheancePrime(TenantModel):
    """Une échéance de paiement de prime d'une ``PoliceAssurance`` (NTASS5).

    ``ecriture_ref`` est une string-FK (id brut, jamais une vraie FK) vers
    ``compta.EcritureComptable`` — la compta reste la SEULE app qui écrit ses
    modèles (voir ``services.proposer_ecriture_prime``, NTASS6)."""

    class Periodicite(models.TextChoices):
        ANNUELLE = 'annuelle', 'Annuelle'
        SEMESTRIELLE = 'semestrielle', 'Semestrielle'
        TRIMESTRIELLE = 'trimestrielle', 'Trimestrielle'
        MENSUELLE = 'mensuelle', 'Mensuelle'

    class Statut(models.TextChoices):
        A_PAYER = 'a_payer', 'À payer'
        PROPOSEE_COMPTA = 'proposee_compta', 'Proposée en compta'
        PAYEE = 'payee', 'Payée'
        EN_RETARD = 'en_retard', 'En retard'

    # SCA4 — socle ``TenantModel`` ; ``company`` REdéclarée (related_name ARC1).
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='echeances_prime', verbose_name='Société')
    police = models.ForeignKey(
        PoliceAssurance, on_delete=models.CASCADE, related_name='echeances_prime')
    date_echeance_paiement = models.DateField(verbose_name="Date d'échéance")
    montant = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    periodicite = models.CharField(
        max_length=15, choices=Periodicite.choices,
        default=Periodicite.ANNUELLE)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.A_PAYER)
    # String-FK (pas de vraie FK cross-app) — voir docstring de la classe.
    ecriture_ref = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Référence écriture comptable')

    class Meta:
        ordering = ['date_echeance_paiement']
        verbose_name = 'Échéance de prime'
        verbose_name_plural = 'Échéances de prime'
        indexes = [
            models.Index(fields=['police', 'date_echeance_paiement']),
            models.Index(fields=['company', 'statut']),
        ]

    def __str__(self):
        return f'{self.police_id} — {self.montant} le {self.date_echeance_paiement}'


# ── NTASS7 — Actifs/sites couverts par police (string-FK transverse) ──────

class ActifCouvert(TenantModel):
    """Un actif (site/véhicule/équipement) couvert par une police (NTASS7).

    ``actif_ref`` est une string-FK (id brut, JAMAIS une vraie FK cross-app) —
    résolue à la volée en libellé lisible via
    ``selectors.resoudre_libelle_actif`` (import paresseux de
    ``flotte.selectors`` pour VEHICULE ; futur ``NTPRO.selectors`` pour SITE).
    ``actif_libelle`` est un SNAPSHOT texte capturé à l'ajout — reste lisible
    même si l'actif source est renommé/supprimé côté app propriétaire."""

    class TypeActif(models.TextChoices):
        SITE = 'site', 'Site'
        VEHICULE = 'vehicule', 'Véhicule'
        EQUIPEMENT = 'equipement', 'Équipement'
        AUTRE = 'autre', 'Autre'

    # SCA4 — socle ``TenantModel`` ; ``company`` REdéclarée (related_name ARC1).
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='actifs_couverts', verbose_name='Société')
    police = models.ForeignKey(
        PoliceAssurance, on_delete=models.CASCADE, related_name='actifs_couverts')
    type_actif = models.CharField(
        max_length=15, choices=TypeActif.choices, default=TypeActif.AUTRE)
    actif_ref = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Référence de l'actif (string-FK)")
    actif_libelle = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Libellé (snapshot)')
    date_ajout = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Actif couvert'
        verbose_name_plural = 'Actifs couverts'
        indexes = [models.Index(fields=['police', 'type_actif'])]

    def __str__(self):
        return f'{self.get_type_actif_display()} — {self.actif_libelle}'


# ── NTASS10 — Déclaration de sinistre transverse (hors véhicule) ──────────

class DeclarationSinistre(TenantModel):
    """Sinistre TRANSVERSE (hors véhicule — le sinistre véhicule reste
    ``flotte.Sinistre`` FLOTTE25, référencé ici en string-FK optionnel
    ``flotte_sinistre_id`` quand un sinistre véhicule implique AUSSI une
    police d'entreprise, ex. RC après collision) (NTASS10).

    ``reference`` (numéro de dossier, ex. ``SIN-2026-001``) est générée
    RACE-SAFE via ``core.numbering`` (plus-haut-utilisé+1 par société+année,
    savepoint+retry) — JAMAIS ``count()+1`` (CLAUDE.md)."""

    class TypeSinistre(models.TextChoices):
        DOMMAGE_MATERIEL = 'dommage_materiel', 'Dommage matériel'
        RESPONSABILITE_CIVILE = 'responsabilite_civile', 'Responsabilité civile'
        DECENNALE = 'decennale', 'Décennale'
        CYBER = 'cyber', 'Cyber'
        VOL = 'vol', 'Vol'
        INCENDIE = 'incendie', 'Incendie'
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        DECLARE = 'declare', 'Déclaré'
        EN_EXPERTISE = 'en_expertise', 'En expertise'
        INDEMNISE = 'indemnise', 'Indemnisé'
        REFUSE = 'refuse', 'Refusé'
        CLOS = 'clos', 'Clos'

    # SCA4 — socle ``TenantModel`` ; ``company`` REdéclarée (related_name ARC1).
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='declarations_sinistre', verbose_name='Société')
    police = models.ForeignKey(
        PoliceAssurance, on_delete=models.PROTECT,
        related_name='declarations_sinistre')
    # Numéro de dossier — race-safe (core.numbering), ex. SIN-2026-001.
    reference = models.CharField(max_length=40, blank=True, default='')
    date_survenance = models.DateField(verbose_name='Date de survenance')
    date_declaration = models.DateField(
        auto_now_add=True, verbose_name='Date de déclaration')
    nature_sinistre = models.TextField(blank=True, default='')
    type_sinistre = models.CharField(
        max_length=25, choices=TypeSinistre.choices,
        default=TypeSinistre.AUTRE)
    montant_estime_degats = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Montant estimé des dégâts')
    statut = models.CharField(
        max_length=15, choices=Statut.choices, default=Statut.DECLARE)
    description = models.TextField(blank=True, default='')
    # String-FK optionnelle — jamais dupliquée avec flotte.Sinistre (FLOTTE25).
    flotte_sinistre_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Sinistre véhicule lié (flotte)')
    # NTASS15 — string-FK (id brut) vers le futur registre de risques ERM
    # (NTGRC) ; résolue en libellé à la volée, no-op tant que l'app n'existe pas.
    risque_ref = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Risque ERM lié (string-FK NTGRC)')
    # NTASS16 — bascule vers contentieux : string-FK (id brut) vers le futur
    # module NTJUR, posée EN RETOUR par NTJUR quand il reprend le dossier ;
    # ``conteste`` marque un sinistre refusé escaladé, sans créer le dossier ici.
    dossier_contentieux_ref = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Dossier contentieux lié (string-FK NTJUR)')
    conteste = models.BooleanField(default=False, verbose_name='Contesté')
    # ``created_at`` / ``updated_at`` fournis par ``TenantModel`` (SCA4).

    class Meta:
        ordering = ['-date_survenance']
        verbose_name = 'Déclaration de sinistre'
        verbose_name_plural = 'Déclarations de sinistre'
        unique_together = [('company', 'reference')]
        indexes = [
            models.Index(fields=['company', 'statut']),
            models.Index(fields=['company', 'type_sinistre']),
        ]

    def __str__(self):
        return f'{self.reference} ({self.get_type_sinistre_display()})'


# ── NTASS11 — Chatter sinistre ──────────────────────────────────────────────
# ARC8 — le chatter de ``DeclarationSinistre`` converge sur ``records.Activity``
# (via ``records.services.log_activity`` — voir ``services.py``) : plus aucun
# modèle ``*Activity`` maison. La timeline se lit via ``records.chatter_qs``.


# ── NTASS12 — Suivi d'indemnisation vs franchise ───────────────────────────

class IndemnisationSinistre(TenantModel):
    """Suivi de l'indemnisation d'une ``DeclarationSinistre`` (NTASS12).

    ``franchise_appliquee`` est COPIÉE (snapshot, jamais une FK) depuis la
    ``GarantiePolice`` concernée au moment du calcul — reste stable même si la
    garantie change plus tard. ``reste_a_charge`` = ``montant_reclame`` −
    ``montant_indemnise`` (propriété calculée, pas stockée)."""

    # SCA4 — socle ``TenantModel`` ; ``company`` REdéclarée (related_name ARC1).
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='indemnisations_sinistre', verbose_name='Société')
    declaration = models.OneToOneField(
        DeclarationSinistre, on_delete=models.CASCADE,
        related_name='indemnisation')
    montant_reclame = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    franchise_appliquee = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Franchise appliquée (snapshot)')
    montant_indemnise = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    date_versement = models.DateField(null=True, blank=True)
    # NTASS13 — string-FK vers compta.EcritureComptable (jamais une vraie FK).
    ecriture_ref = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Référence écriture comptable')
    # ``created_at`` / ``updated_at`` fournis par ``TenantModel`` (SCA4).

    class Meta:
        verbose_name = 'Indemnisation de sinistre'
        verbose_name_plural = 'Indemnisations de sinistre'

    @property
    def reste_a_charge(self):
        return self.montant_reclame - self.montant_indemnise

    def __str__(self):
        return f'{self.declaration_id} — indemnisé {self.montant_indemnise}'


# ── NTASS17 — Attestations d'assurance émises par NOS assureurs (GED) ──────

class AttestationAssurance(TenantModel):
    """Attestation d'assurance que NOUS détenons en tant qu'ASSURÉ (NTASS17),
    exigée par les maîtres d'ouvrage BTP (miroir de l'attestation fournisseur
    NTP2P7, côté « nous sommes l'assuré »).

    ARC26 — l'attestation scannée est rattachée via ``records.Attachment``
    (cible ``assurances.attestationassurance`` déclarée dans ``platform.py``),
    stockée MinIO comme toute pièce jointe transverse."""

    class Statut(models.TextChoices):
        VALIDE = 'valide', 'Valide'
        EXPIREE = 'expiree', 'Expirée'

    # SCA4 — socle ``TenantModel`` ; ``company`` REdéclarée (related_name ARC1).
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='attestations_assurance', verbose_name='Société')
    police = models.ForeignKey(
        PoliceAssurance, on_delete=models.CASCADE, related_name='attestations')
    date_emission = models.DateField(verbose_name="Date d'émission")
    date_validite = models.DateField(verbose_name='Date de validité')
    emise_pour = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Émise pour (client / marché)')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.VALIDE)
    # ``created_at`` / ``updated_at`` fournis par ``TenantModel`` (SCA4).

    class Meta:
        ordering = ['-date_validite']
        verbose_name = "Attestation d'assurance"
        verbose_name_plural = "Attestations d'assurance"
        indexes = [
            models.Index(fields=['company', 'statut']),
            models.Index(fields=['police', '-date_validite']),
        ]

    def __str__(self):
        return f'Attestation {self.police_id} → {self.emise_pour}'.strip()


# ── NTASS19 — Checklist conformité assurance par marché/appel d'offres ─────

class ExigenceAssuranceMarche(TenantModel):
    """Exigence d'assurance d'un marché/appel d'offres (NTASS19).

    ``marche_ref`` est une string-FK (id brut) vers ``apps/ao`` (ou un
    devis/contrat) — jamais une vraie FK cross-app. Le service
    ``verifier_conformite_assurance_marche`` croise les polices ACTIVES de la
    société avec les exigences et pose ``statut_verification``."""

    class StatutVerification(models.TextChoices):
        A_VERIFIER = 'a_verifier', 'À vérifier'
        CONFORME = 'conforme', 'Conforme'
        NON_CONFORME = 'non_conforme', 'Non conforme'

    # SCA4 — socle ``TenantModel`` ; ``company`` REdéclarée (related_name ARC1).
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='exigences_assurance_marche', verbose_name='Société')
    marche_ref = models.PositiveIntegerField(
        verbose_name='Référence du marché (string-FK)')
    # Même jeu de choix que PoliceAssurance.type_police (réutilisé, jamais
    # redéclaré — la conformité croise sur ce type).
    type_police_requis = models.CharField(
        max_length=30, choices=PoliceAssurance.TypePolice.choices,
        verbose_name='Type de police requis')
    montant_couverture_minimum = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Couverture minimum exigée')
    statut_verification = models.CharField(
        max_length=15, choices=StatutVerification.choices,
        default=StatutVerification.A_VERIFIER)
    # ``created_at`` / ``updated_at`` fournis par ``TenantModel`` (SCA4).

    class Meta:
        ordering = ['id']
        verbose_name = "Exigence d'assurance de marché"
        verbose_name_plural = "Exigences d'assurance de marché"
        indexes = [models.Index(fields=['company', 'marche_ref'])]

    def __str__(self):
        return f'Marché {self.marche_ref} — {self.get_type_police_requis_display()}'
