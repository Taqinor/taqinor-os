"""FG25 — politiques d'approbation configurables (au-delà de la remise).

Aujourd'hui la seule approbation de première classe est la remise (seuil sur
``CompanyProfile.discount_approval_threshold``) ; le primitif générique
``automation.AutomationApproval`` n'est pas branché aux autres actions à fort
impact. Ce modèle DÉCLARE, par société, des politiques « type d'action + seuil
+ palier approbateur » que les chemins d'écriture peuvent consulter pour savoir
s'ils doivent passer par une approbation.

Purement déclaratif et ADDITIF : sans politique activée, rien ne change. Garde
dans un fichier dédié (indépendance de lane) ; enregistré via ``apps.ready()``.
"""
from django.db import models


class ApprovalPolicy(models.Model):
    """Une règle d'approbation par société : type d'action + seuil + palier."""

    class ActionType(models.TextChoices):
        # Types d'action à fort impact pouvant exiger une approbation. La remise
        # reste portée par ``CompanyProfile.discount_approval_threshold`` pour la
        # rétro-compatibilité ; on la liste ici pour une déclaration unifiée.
        DISCOUNT = 'discount', 'Remise sur devis'
        QUOTE_AMOUNT = 'quote_amount', 'Montant de devis'
        PURCHASE_ORDER = 'purchase_order', "Bon de commande fournisseur"
        EXPENSE = 'expense', 'Dépense / frais'
        CONTRACT = 'contract', 'Contrat'
        REFUND = 'refund', 'Avoir / remboursement'

    class ApproverTier(models.TextChoices):
        # Palier minimal habilité à approuver (réutilise les paliers existants).
        RESPONSABLE = 'responsable', 'Responsable (ou plus)'
        ADMIN = 'admin', 'Administrateur uniquement'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='approval_policies')
    action_type = models.CharField(
        max_length=20, choices=ActionType.choices)
    # Seuil au-delà duquel l'approbation s'applique (sens dépend du type : % pour
    # la remise, montant pour devis/BC/dépense…). NULL = s'applique toujours.
    seuil = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True)
    approver_tier = models.CharField(
        max_length=20, choices=ApproverTier.choices,
        default=ApproverTier.ADMIN)
    enabled = models.BooleanField(default=True)
    note = models.CharField(max_length=255, blank=True, default='')

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Politique d'approbation"
        verbose_name_plural = "Politiques d'approbation"
        ordering = ['action_type', 'id']
        # Une seule politique par société + type d'action.
        unique_together = [('company', 'action_type')]
        indexes = [
            models.Index(
                fields=['company', 'action_type', 'enabled'],
                name='param_apprpol_idx'),
        ]

    def __str__(self):
        return f'{self.company_id}:{self.action_type}'

    @classmethod
    def requires_approval(cls, company, action_type, amount=None):
        """True si ``action_type`` à ``amount`` exige une approbation pour
        ``company``. Inerte (False) sans politique activée. ``amount=None`` →
        on considère le seuil franchi (action toujours soumise si activée)."""
        if company is None:
            return False
        policy = cls.objects.filter(
            company=company, action_type=action_type, enabled=True).first()
        if policy is None:
            return False
        if policy.seuil is None or amount is None:
            return True
        try:
            from decimal import Decimal
            return Decimal(str(amount)) >= policy.seuil
        except Exception:
            return True
