"""apps.credit — Gestion du crédit client (Groupe NTCRD).

Additif — ne modifie AUCUN modèle ventes/crm existant ; toutes les
références vers Client/Devis/BonCommande se font en string-FK
('crm.Client', 'ventes.Devis', 'ventes.BonCommande').
"""
from django.conf import settings
from django.db import models


class LimiteCredit(models.Model):
    """NTCRD2 — limite de crédit (encours max autorisé) par client.

    Un client SANS ``LimiteCredit`` (ou avec ``montant_limite=None``) n'a
    aucune limite définie : comportement actuel inchangé (aucun hold). Une
    entrée par (société, client) — ``unique_together``."""

    class ModeHold(models.TextChoices):
        AUCUN = 'aucun', 'Aucun'
        AVERTISSEMENT = 'avertissement', 'Avertissement'
        BLOCAGE = 'blocage', 'Blocage'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='limites_credit')
    client = models.ForeignKey(
        'crm.Client', on_delete=models.CASCADE,
        related_name='limites_credit')
    # NULL = pas de limite définie pour ce client (aucun blocage n'est
    # jamais déclenché — comportement historique inchangé).
    montant_limite = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Limite de crédit')
    devise = models.CharField(max_length=3, default='MAD')
    mode_hold = models.CharField(
        max_length=20, choices=ModeHold.choices, default=ModeHold.AVERTISSEMENT)
    actif = models.BooleanField(default=True)
    motif_null = models.TextField(
        blank=True, default='',
        help_text='Motif si la limite est volontairement non définie.')
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='limites_credit_creees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Limite de crédit'
        verbose_name_plural = 'Limites de crédit'
        unique_together = [('company', 'client')]
        ordering = ['-date_modification']

    def __str__(self):
        return f'{self.client_id} — {self.montant_limite} {self.devise}'


class ReglageCredit(models.Model):
    """NTCRD3 — réglages crédit par société (1-1), défauts NON bloquants.

    Les défauts reproduisent le comportement actuel (aucun hold tant que le
    founder n'active rien) : ``mode_hold_defaut`` reste ``avertissement``
    (jamais ``blocage`` sans opt-in explicite)."""

    company = models.OneToOneField(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='reglage_credit')
    mode_hold_defaut = models.CharField(
        max_length=20, choices=LimiteCredit.ModeHold.choices,
        default=LimiteCredit.ModeHold.AVERTISSEMENT,
        help_text=(
            'Mode de hold hérité par une LimiteCredit qui ne le surcharge '
            'pas explicitement. Jamais "blocage" par défaut.'))
    inclure_bc_non_factures = models.BooleanField(default=True)
    inclure_devis_en_cours = models.BooleanField(default=False)
    seuil_alerte_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=80,
        help_text="Seuil (% de la limite) déclenchant une alerte avant blocage.")
    # NTCRD21 — seuil d'encours consolidé société déclenchant une alerte au
    # Directeur (0 = désactivé, défaut = comportement actuel inchangé).
    seuil_alerte_exposition_globale = models.DecimalField(
        max_digits=16, decimal_places=2, default=0)
    # NTCRD21 — date de la dernière alerte d'exposition émise (dédup : une
    # seule alerte par jour, pas de spam).
    derniere_alerte_exposition_le = models.DateField(null=True, blank=True)
    # NTCRD29 — devise de référence pour la consolidation multi-devise (défaut
    # MAD = comportement actuel inchangé). La conversion réelle par document
    # (taux déjà stocké sur facture/devis) est appliquée par l'appelant quand
    # un sélecteur ventes expose devise+taux par document.
    devise_consolidation = models.CharField(max_length=3, default='MAD')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Réglage crédit (société)'
        verbose_name_plural = 'Réglages crédit (société)'

    def __str__(self):
        return f'Réglage crédit — {self.company_id}'

    @classmethod
    def get_or_default(cls, company):
        """Renvoie le réglage de ``company`` ou une INSTANCE NON SAUVEGARDÉE
        aux défauts (jamais bloquant) si aucun réglage n'existe encore —
        comportement actuel inchangé tant que le founder n'a rien configuré."""
        try:
            return cls.objects.get(company=company)
        except cls.DoesNotExist:
            return cls(company=company)


class ConditionPaiementSegment(models.Model):
    """NTCRD13 — conditions de paiement par segment client.

    ``segment`` est un TEXTE LIBRE (``Client.segment`` NTSRV10 n'existe pas
    encore — repli additif) : le résolveur choisit la condition du segment du
    client, sinon repli sur les réglages société actuels (AUCUN changement du
    comportement par défaut). ``mode_hold_override`` permet à un segment « grand
    compte » d'être plus permissif que le défaut société."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='conditions_paiement_segment')
    segment = models.CharField(max_length=100)
    delai_paiement_jours = models.PositiveIntegerField(default=0)
    pct_acompte_defaut = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="% d'acompte par défaut pour ce segment (vide = défaut société).")
    mode_hold_override = models.CharField(
        max_length=20, choices=LimiteCredit.ModeHold.choices,
        blank=True, default='',
        help_text='Surcharge le mode de hold pour ce segment (vide = défaut société).')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Condition de paiement par segment'
        verbose_name_plural = 'Conditions de paiement par segment'
        unique_together = [('company', 'segment')]
        ordering = ['segment']

    def __str__(self):
        return f'{self.segment} — {self.delai_paiement_jours} j'


class SegmentClientCredit(models.Model):
    """NTCRD13 — affectation locale d'un client à un segment crédit (repli
    additif tant que ``Client.segment`` NTSRV10 n'existe pas). Un client sans
    affectation = aucun segment = comportement société par défaut inchangé."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='segments_client_credit')
    client = models.OneToOneField(
        'crm.Client', on_delete=models.CASCADE,
        related_name='segment_credit')
    segment = models.CharField(max_length=100)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Segment crédit du client'
        verbose_name_plural = 'Segments crédit des clients'

    def __str__(self):
        return f'{self.client_id} → {self.segment}'


class DerogationCredit(models.Model):
    """NTCRD9 — dérogation crédit : demande → approbation/rejet Directeur/
    Administrateur. Reprend le PATTERN (jamais le modèle) de
    ``contrats.selectors.resoudre_regle_approbation`` — pas de lien métier
    direct avec ``apps.contrats``, donc aucun import."""

    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        APPROUVEE = 'approuvee', 'Approuvée'
        REJETEE = 'rejetee', 'Rejetée'
        EXPIREE = 'expiree', 'Expirée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='derogations_credit')
    client = models.ForeignKey(
        'crm.Client', on_delete=models.CASCADE,
        related_name='derogations_credit')
    # NTCRD28 — devis/BC concerné (contexte, optionnel — string-FK, jamais
    # un import de apps.ventes.models).
    devis = models.ForeignKey(
        'ventes.Devis', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='derogations_credit')
    montant_demande = models.DecimalField(max_digits=14, decimal_places=2)
    motif = models.TextField(blank=True, default='')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE)
    demandeur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='derogations_credit_demandees')
    approuvee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='derogations_credit_decidees')
    date_decision = models.DateTimeField(null=True, blank=True)
    # Validité de 30 jours par défaut à compter de l'APPROBATION (posée au
    # moment de l'approbation, pas à la création).
    valide_jusqu_au = models.DateTimeField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Dérogation crédit'
        verbose_name_plural = 'Dérogations crédit'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Dérogation {self.client_id} — {self.montant_demande} ({self.statut})'

    @property
    def est_valide(self):
        """Vrai si APPROUVEE et non expirée (``valide_jusqu_au`` dans le futur
        ou non posée)."""
        from django.utils import timezone
        if self.statut != self.Statut.APPROUVEE:
            return False
        if self.valide_jusqu_au is None:
            return True
        return timezone.now() <= self.valide_jusqu_au


class PoliceAssuranceCredit(models.Model):
    """NTCRD16 — police d'assurance-crédit : REGISTRE DÉCLARATIF (aucune
    intégration/appel API assureur — Allianz Trade/Coface/Atradius saisis à la
    main). company-scopé."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='polices_assurance_credit')
    assureur = models.CharField(max_length=150)
    numero_police = models.CharField(max_length=100, blank=True, default='')
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    franchise = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True)
    taux_couverture_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Taux de couverture assureur (ex. 90 %).')
    plafond_global = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True,
        help_text='Encours max garanti, tous clients confondus.')
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Police d'assurance-crédit"
        verbose_name_plural = "Polices d'assurance-crédit"
        ordering = ['-date_debut', '-id']

    def __str__(self):
        return f'{self.assureur} — {self.numero_police}'


class EncoursGarantiClient(models.Model):
    """NTCRD17 — quota garanti par l'assureur pour UN client, sous une police.
    Un client sans encours garanti déclaré est simplement « non couvert »
    (aucune hypothèse silencieuse)."""

    class StatutAgrement(models.TextChoices):
        ACCORDE = 'accorde', 'Accordé'
        REFUSE = 'refuse', 'Refusé'
        EN_ATTENTE = 'en_attente', 'En attente'
        REDUIT = 'reduit', 'Réduit'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='encours_garantis_client')
    police = models.ForeignKey(
        PoliceAssuranceCredit, on_delete=models.CASCADE,
        related_name='encours_garantis')
    client = models.ForeignKey(
        'crm.Client', on_delete=models.CASCADE,
        related_name='encours_garantis_credit')
    montant_garanti = models.DecimalField(max_digits=14, decimal_places=2)
    date_agrement = models.DateField(null=True, blank=True)
    statut_agrement = models.CharField(
        max_length=20, choices=StatutAgrement.choices,
        default=StatutAgrement.EN_ATTENTE)
    reference_assureur = models.CharField(max_length=100, blank=True, default='')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Encours garanti client'
        verbose_name_plural = 'Encours garantis client'
        unique_together = [('police', 'client')]
        ordering = ['-date_agrement', '-id']

    def __str__(self):
        return f'{self.client_id} — {self.montant_garanti} ({self.police_id})'
