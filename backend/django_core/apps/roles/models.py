from django.db import models


ALL_PERMISSIONS = [
    'stock_voir',
    'stock_creer',
    'stock_modifier',
    'stock_supprimer',
    'stock_mouvement',
    'crm_voir',
    'crm_creer',
    'crm_modifier',
    'crm_supprimer',
    'ventes_voir',
    'ventes_creer',
    'ventes_modifier',
    'ventes_supprimer',
    'ventes_valider',
    'ventes_pdf',
    'installation_voir',
    'installation_gerer',
    'intervention_gerer',
    'equipement_voir',
    'equipement_gerer',
    'sav_voir',
    'sav_gerer',
    'parametres_voir',
    'parametres_modifier',
    'users_voir',
    'users_gerer',
    'roles_gerer',
    'reporting_voir',
]

RESPONSABLE_PERMISSIONS = [
    'stock_voir',
    'stock_creer',
    'stock_modifier',
    'stock_mouvement',
    'crm_voir',
    'crm_creer',
    'crm_modifier',
    'ventes_voir',
    'ventes_creer',
    'ventes_modifier',
    'ventes_valider',
    'ventes_pdf',
    # La Commerciale gère le flux chantier (création depuis devis, suivi,
    # interventions). L'admin garde le contrôle total (suppression).
    'installation_voir',
    'installation_gerer',
    'intervention_gerer',
    # SAV : la Commerciale consulte le parc d'équipements et ouvre/traite les
    # tickets après-vente. La GESTION du parc (ajout d'équipements) reste admin.
    'equipement_voir',
    'sav_voir',
    'sav_gerer',
    'parametres_voir',
    'users_voir',
    'reporting_voir',
]

UTILISATEUR_PERMISSIONS = [
    'stock_voir',
    'crm_voir',
    'ventes_voir',
    'installation_voir',
    'equipement_voir',
    'sav_voir',
    'parametres_voir',
    'reporting_voir',
]


class Role(models.Model):
    company = models.ForeignKey(
        'authentication.Company',  # app_label.ModelName
        on_delete=models.CASCADE,
        related_name='roles',
    )
    nom = models.CharField(max_length=100)
    permissions = models.JSONField(default=list)
    est_systeme = models.BooleanField(default=False)

    class Meta:
        unique_together = [('company', 'nom')]
        verbose_name = 'Rôle'
        verbose_name_plural = 'Rôles'
        ordering = ['company', 'nom']

    def __str__(self):
        return f'{self.company.nom} — {self.nom}'
