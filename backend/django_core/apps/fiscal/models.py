"""Modèles de conformité fiscale marocaine (Groupe NTMAR).

Distinct de ``compta.ObligationFiscale`` (XACC9 — vue calendaire ponctuelle des
briques déjà câblées : TVA/acomptes IS/RAS/timbre/état 9421/liasse) : ici
``ObligationFiscale`` est la RÈGLE récurrente par société (périodicité + règle
d'échéance textuelle), et ``calendrier(company, annee)`` (services.py)
matérialise les échéances DATÉES de l'année en ``EcheanceFiscale`` — y compris
des obligations que ``compta`` ne couvre pas encore (CNSS, taxe professionnelle,
droit d'enregistrement). Les deux coexistent sans se dupliquer : ``compta``
reste la source des déclarations réellement déposées (TVA/IS/RAS/timbre), ce
module fournit la vue calendaire COMPLÈTE + les attestations/UBO/veille.
"""
from django.db import models

from core.models import TenantModel


class ObligationFiscale(TenantModel):
    """Règle d'obligation fiscale récurrente par société (NTMAR14)."""

    class Type(models.TextChoices):
        TVA = 'tva', 'TVA'
        IS = 'is', "Impôt sur les sociétés"
        IR = 'ir', "Impôt sur le revenu"
        ACOMPTE_IS = 'acompte_is', 'Acompte IS'
        TIMBRE = 'timbre', 'Droit de timbre'
        RAS = 'ras', 'Retenue à la source'
        CNSS_REF = 'cnss_ref', 'CNSS'
        TAXE_PRO = 'taxe_pro', 'Taxe professionnelle'
        DROIT_ENREGISTREMENT = 'droit_enregistrement', "Droit d'enregistrement"

    class Periodicite(models.TextChoices):
        MENSUELLE = 'mensuelle', 'Mensuelle'
        TRIMESTRIELLE = 'trimestrielle', 'Trimestrielle'
        ANNUELLE = 'annuelle', 'Annuelle'
        PONCTUELLE = 'ponctuelle', 'Ponctuelle'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: tenant — le calendrier fiscal d'une société disparaît avec elle
        related_name='obligations_fiscales_ma', verbose_name='Société')
    type_obligation = models.CharField(
        max_length=24, choices=Type.choices, verbose_name='Type')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    periodicite = models.CharField(
        max_length=14, choices=Periodicite.choices,
        default=Periodicite.MENSUELLE, verbose_name='Périodicité')
    # Règle textuelle informative (ex. « 20 du mois suivant ») — parsée au
    # meilleur effort par ``services._date_limite`` ; un format non reconnu
    # retombe sur un délai par défaut (jamais d'exception bloquante).
    regle_echeance = models.CharField(
        max_length=120, blank=True, default='', verbose_name="Règle d'échéance")
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Obligation fiscale (Maroc)'
        verbose_name_plural = 'Obligations fiscales (Maroc)'
        ordering = ['type_obligation']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'type_obligation'],
                name='uniq_obligation_fiscale_ma_type'),
        ]

    def __str__(self):
        return self.libelle or self.get_type_obligation_display()


class EcheanceFiscale(TenantModel):
    """Échéance DATÉE d'une obligation, pour une période donnée (NTMAR14).

    Générée par ``services.calendrier`` (idempotent : ``get_or_create`` par
    période). ``rappel_envoye_le`` (NTMAR15) marque le rappel déjà envoyé —
    idempotence. ``declaration_type``/``declaration_id`` pointent (string-ref,
    jamais un import de modèle) vers la déclaration source une fois déposée
    (ex. ``compta.DeclarationTVA``)."""

    class Statut(models.TextChoices):
        A_PREPARER = 'a_preparer', 'À préparer'
        DEPOSEE = 'deposee', 'Déposée'
        PAYEE = 'payee', 'Payée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: tenant
        related_name='echeances_fiscales_ma', verbose_name='Société')
    obligation = models.ForeignKey(
        ObligationFiscale,
        on_delete=models.CASCADE,  # on_delete: une échéance n'a pas de sens sans son obligation
        related_name='echeances', verbose_name='Obligation')
    periode_debut = models.DateField(verbose_name='Début de période')
    periode_fin = models.DateField(verbose_name='Fin de période')
    date_limite = models.DateField(verbose_name='Date limite')
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.A_PREPARER,
        verbose_name='Statut')
    declaration_type = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Type de déclaration source')
    declaration_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID de la déclaration source')
    rappel_envoye_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Rappel envoyé le')
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Échéance fiscale'
        verbose_name_plural = 'Échéances fiscales'
        ordering = ['date_limite', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'obligation', 'periode_debut', 'periode_fin'],
                name='uniq_echeance_fiscale_ma_periode'),
        ]

    def __str__(self):
        return f'{self.obligation.get_type_obligation_display()} — {self.date_limite}'


class AttestationTenant(TenantModel):
    """Attestation fiscale/sociale DU TENANT (nous), avec expiration (NTMAR28).

    Exigée « à jour » par les maîtres d'ouvrage (marchés publics, EPC) : voir
    NTMAR29 (réutilisation dans le dossier de soumission)."""

    class Type(models.TextChoices):
        FISCALE_REGULARITE = 'fiscale_regularite', 'Attestation de régularité fiscale'
        SOCIALE_CNSS = 'sociale_cnss', 'Attestation de régularité CNSS'
        RC = 'rc', 'Registre de commerce'
        PATENTE = 'patente', 'Patente / taxe professionnelle'
        AGREMENT = 'agrement', 'Agrément'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: tenant
        related_name='attestations_tenant', verbose_name='Société')
    type_attestation = models.CharField(
        max_length=24, choices=Type.choices, verbose_name='Type')
    numero = models.CharField(max_length=80, blank=True, default='', verbose_name='Numéro')
    date_emission = models.DateField(null=True, blank=True, verbose_name="Date d'émission")
    date_expiration = models.DateField(null=True, blank=True, verbose_name="Date d'expiration")
    fichier_key = models.CharField(
        max_length=500, blank=True, default='', verbose_name='Clé MinIO du fichier')
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Attestation (tenant)'
        verbose_name_plural = 'Attestations (tenant)'
        ordering = ['type_attestation', '-date_emission']

    def __str__(self):
        return f'{self.get_type_attestation_display()} {self.numero}'


class BeneficiaireEffectif(TenantModel):
    """Bénéficiaire effectif (UBO) déclaré pour la société (NTMAR30)."""

    class TypeControle(models.TextChoices):
        DIRECT = 'direct', 'Contrôle direct'
        INDIRECT = 'indirect', 'Contrôle indirect'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: tenant
        related_name='beneficiaires_effectifs', verbose_name='Société')
    nom = models.CharField(max_length=200, verbose_name='Nom')
    cin_passeport = models.CharField(
        max_length=40, blank=True, default='', verbose_name='CIN / Passeport')
    nationalite = models.CharField(max_length=80, blank=True, default='', verbose_name='Nationalité')
    pourcentage_detention = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, verbose_name='% de détention')
    type_controle = models.CharField(
        max_length=10, choices=TypeControle.choices, default=TypeControle.DIRECT,
        verbose_name='Type de contrôle')
    date_declaration = models.DateField(null=True, blank=True, verbose_name='Date de déclaration')
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Bénéficiaire effectif (UBO)'
        verbose_name_plural = 'Bénéficiaires effectifs (UBO)'
        ordering = ['-pourcentage_detention', 'nom']

    def __str__(self):
        return f'{self.nom} ({self.pourcentage_detention}%)'


class VeilleReglementaire(TenantModel):
    """Entrée de veille réglementaire, saisie manuelle/import (NTMAR32).

    ``company`` NULL = entrée GLOBALE (visible de toutes les sociétés) ;
    posée uniquement par un import/saisie interne, JAMAIS de scraping."""

    class Domaine(models.TextChoices):
        TVA = 'tva', 'TVA'
        IS = 'is', 'IS'
        IR = 'ir', 'IR'
        MARCHES = 'marches', 'Marchés publics'
        CNSS = 'cnss', 'CNSS'
        EINVOICING = 'einvoicing', 'E-invoicing'
        ENVIRONNEMENT = 'environnement', 'Environnement'

    class Statut(models.TextChoices):
        NOUVEAU = 'nouveau', 'Nouveau'
        LU = 'lu', 'Lu'
        TRAITE = 'traite', 'Traité'

    # TenantModel impose ``company`` NOT NULL — NTMAR32 veut une entrée
    # GLOBALE possible : redéclarée ``null=True`` explicitement (dérogation
    # documentée, related_name conservé).
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: tenant (NULL = entrée globale, non liée à une société)
        null=True, blank=True,
        related_name='veilles_reglementaires', verbose_name='Société (vide = globale)')
    domaine = models.CharField(max_length=14, choices=Domaine.choices, verbose_name='Domaine')
    titre = models.CharField(max_length=200, verbose_name='Titre')
    resume = models.TextField(blank=True, default='', verbose_name='Résumé')
    date_effet = models.DateField(null=True, blank=True, verbose_name="Date d'effet")
    source_url = models.URLField(blank=True, default='', verbose_name='Source')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.NOUVEAU,
        verbose_name='Statut')
    # NTMAR33 — lien actionnable vers UN réglage société impacté. Champ texte
    # LIBRE (ex. « CompanyProfile.tva_defaut ») — jamais une FK réelle vers
    # ``parametres`` (foundation exemptée en LECTURE seulement ; aucune
    # écriture de ce lot ne touche ``apps.parametres``).
    parametre_cible = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Paramètre cible')
    impact_traite = models.BooleanField(default=False, verbose_name='Impact traité')
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Veille réglementaire'
        verbose_name_plural = 'Veilles réglementaires'
        ordering = ['-date_effet', '-id']

    def __str__(self):
        return self.titre
