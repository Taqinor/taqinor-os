"""NTSCM9 — Incidents QUALITÉ fournisseur.

Le scorecard fournisseur mesure la ponctualité et le remplissage ; il ne dit
rien de ce qui arrive ABÎMÉ, NON CONFORME, ou SANS SES DOCUMENTS. Ce modèle
est ce chaînon manquant : un incident daté, gradué, chiffré — qui alimente le
scorecard (NTSCM10) et le TCO (NTSCM26).

Références cross-app : ``bon_commande_fournisseur`` et ``retour`` vivent dans
``apps.achats`` (ODX19) → STRING-FK. ``fournisseur``/``produit`` sont des
modèles de ``stock`` (même app) → FK directe autorisée.
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel


class IncidentQualiteFournisseur(TenantModel):
    """Un incident qualité imputable à un fournisseur."""

    class TypeIncident(models.TextChoices):
        NON_CONFORME = 'non_conforme', 'Non conforme'
        ENDOMMAGE = 'endommage', 'Endommagé'
        ERREUR_REFERENCE = 'erreur_reference', 'Erreur de référence'
        DOCUMENTATION_MANQUANTE = (
            'documentation_manquante', 'Documentation manquante')
        AUTRE = 'autre', 'Autre'

    class Gravite(models.TextChoices):
        MINEURE = 'mineure', 'Mineure'
        MAJEURE = 'majeure', 'Majeure'
        CRITIQUE = 'critique', 'Critique'

    fournisseur = models.ForeignKey(
        'stock.Fournisseur', on_delete=models.PROTECT,  # on_delete: PROTECT — un incident est une donnée RÉELLE d'historique qualité, non reconstructible ; on refuse la suppression du fournisseur plutôt que d'effacer son passif
        related_name='incidents_qualite')
    bon_commande_fournisseur = models.ForeignKey(
        'achats.BonCommandeFournisseur', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='incidents_qualite_stock')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='incidents_qualite_fournisseur')
    retour = models.ForeignKey(
        'achats.RetourFournisseur', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='incidents_qualite_stock',
        help_text='Retour fournisseur déclenché par cet incident, si créé.')
    type_incident = models.CharField(
        max_length=30, choices=TypeIncident.choices,
        default=TypeIncident.NON_CONFORME)
    gravite = models.CharField(
        max_length=20, choices=Gravite.choices, default=Gravite.MINEURE)
    quantite_affectee = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True, default='')
    date_incident = models.DateField()
    resolu = models.BooleanField(default=False)
    date_resolution = models.DateField(null=True, blank=True)
    cout_impact_mad = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Coût constaté de l\'incident (MAD). INTERNE — alimente le '
                  'TCO fournisseur (NTSCM26), jamais un document client.')
    declare_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='incidents_qualite_declares')

    class Meta:
        verbose_name = 'Incident qualité fournisseur'
        verbose_name_plural = 'Incidents qualité fournisseur'
        ordering = ['-date_incident', '-id']
        indexes = [
            models.Index(fields=['company', 'fournisseur'],
                         name='idx_incqual_co_fourn'),
            models.Index(fields=['company', 'resolu'],
                         name='idx_incqual_co_resolu'),
        ]

    def __str__(self):
        return f'{self.fournisseur_id} · {self.type_incident} ({self.gravite})'

    @property
    def est_bloquant(self):
        """Un incident CRITIQUE non résolu doit sauter aux yeux du scorecard."""
        return self.gravite == self.Gravite.CRITIQUE and not self.resolu
