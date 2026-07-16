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
from django.conf import settings
from django.db import models


# ── NTASS1 — Registre des assureurs & courtiers ────────────────────────────

class Assureur(models.Model):
    """Compagnie d'assurance (NTASS1). Registre scopé société."""

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


class Courtier(models.Model):
    """Courtier / intermédiaire d'assurance (NTASS1), distinct de l'assureur.

    Registre scopé société. Un courtier n'émet pas les polices lui-même (c'est
    l'assureur) mais intermédie ; ``numero_agrement`` est son numéro d'agrément
    professionnel (ACAPS au Maroc)."""

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

class PoliceAssurance(models.Model):
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
    document_police = models.FileField(
        upload_to='assurances/polices/%Y/%m/', null=True, blank=True,
        verbose_name='Contrat scanné')
    notes = models.TextField(blank=True, default='')
    # NTASS9 — versioning léger : lien vers la police remplacée au renouvellement.
    police_precedente = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='polices_suivantes', verbose_name='Police précédente')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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


# ── NTASS3 — Chatter dédié « PoliceActivity » (pattern DevisActivity/
# ContratActivity/crm.LeadActivity) ─────────────────────────────────────────

class PoliceActivity(models.Model):
    """Historique « chatter » d'une ``PoliceAssurance`` (NTASS3).

    Deux familles d'entrées : automatiques (transitions de ``statut``,
    ``date_echeance``, ``prime_annuelle_ht`` — champ/ancienne valeur/nouvelle
    valeur, posées côté serveur) et manuelles (notes libres)."""

    class Kind(models.TextChoices):
        CREATION = 'creation', 'Création'
        MODIFICATION = 'modification', 'Modification'
        NOTE = 'note', 'Note'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='police_activities')
    police = models.ForeignKey(
        PoliceAssurance, on_delete=models.CASCADE, related_name='activites')
    kind = models.CharField(max_length=15, choices=Kind.choices)
    champ = models.CharField(max_length=100, blank=True, null=True)
    champ_label = models.CharField(max_length=150, blank=True, null=True)
    ancienne_valeur = models.TextField(blank=True, null=True)
    nouvelle_valeur = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='police_activities')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Activité police'
        verbose_name_plural = 'Activités police'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['police', '-created_at'])]

    def __str__(self):
        return f'{self.police_id} {self.kind} {self.champ or ""}'.strip()


# ── NTASS4 — Garanties, plafonds & franchises par police ───────────────────

class GarantiePolice(models.Model):
    """Une garantie d'une ``PoliceAssurance`` avec son plafond/franchise
    propres (NTASS4). Une police porte plusieurs garanties (ex. une DÉCENNALE
    peut avoir 3 garanties à plafonds différents)."""

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
