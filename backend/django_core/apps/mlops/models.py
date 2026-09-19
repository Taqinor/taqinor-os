"""Modèles du module « mlops » (Groupe NTAI, P3 — MLOps par tenant).

MULTI-TENANT : tout modèle hérite de ``core.models.TenantModel`` (FK
``company`` + horodatage). N'importe AUCUNE app métier — les scorers
(``core/*.py``) et les autres apps lisent ces données via
``apps.mlops.selectors``, jamais ce module directement depuis un import de
modèle.
"""
from django.db import models

from core.models import TenantModel


class ModeleML(TenantModel):
    """NTAI27 — Une VERSION des hyperparamètres/seuils d'un scorer, par
    société.

    Les scorers purs de ``core/*.py`` (churn/win_proba/retard_paiement/
    reappro/anomalie) codent aujourd'hui leurs seuils en dur. Une ligne ici
    propose un jeu de paramètres alternatif pour UN scorer, versionné : au
    plus UNE version ``actif=True`` par (société, scorer) — contrainte posée
    en base, jamais arbitrée en Python seul.
    """

    class Nom(models.TextChoices):
        CHURN = 'churn', 'Risque de churn'
        WIN_PROBA = 'win_proba', 'Probabilité de gain (devis)'
        RETARD_PAIEMENT = 'retard_paiement', 'Retard de paiement'
        REAPPRO = 'reappro', 'Réapprovisionnement (seuil stock)'
        ANOMALIE = 'anomalie', 'Détection d\'anomalie'

    nom = models.CharField(max_length=20, choices=Nom.choices)
    version = models.PositiveIntegerField(
        default=1,
        help_text="Numéro de version (le PLUS RÉCENT n'est pas forcément "
                  "l'actif — voir « actif »).")
    params_json = models.JSONField(
        default=dict, blank=True,
        help_text='Hyperparamètres/seuils de CETTE version (schéma libre, '
                  'propre à chaque scorer — interprété par lui seul).')
    actif = models.BooleanField(
        default=False,
        help_text='Version RÉELLEMENT utilisée par le scorer pour cette '
                  'société (au plus une par scorer).')
    note = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        verbose_name = 'Version de modèle ML'
        verbose_name_plural = 'Versions de modèle ML'
        ordering = ['nom', '-version']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'nom', 'version'],
                name='uniq_mlops_modele_co_nom_ver'),
            # Au plus UNE version active par (société, scorer) — arbitré en
            # base, jamais par un "dernier gagne" applicatif.
            models.UniqueConstraint(
                fields=['company', 'nom'], condition=models.Q(actif=True),
                name='uniq_mlops_modele_actif'),
        ]
        indexes = [
            models.Index(fields=['company', 'nom'],
                         name='mlops_modele_co_nom_idx'),
        ]

    def __str__(self):
        drapeau = ' (actif)' if self.actif else ''
        return f'{self.get_nom_display()} v{self.version}{drapeau}'


class FeatureVector(TenantModel):
    """NTAI30 — Signaux MATÉRIALISÉS d'une entité, consommés par les scorers.

    ``content_type`` — étiquette texte du modèle source (ex. ``'crm.lead'``),
    JAMAIS une FK vers une app métier (même patron que ``core.SearchChunk``,
    NTAI24) : ce module reste lisible depuis n'importe quelle app appelante
    sans lui faire importer de modèle métier. ``object_id`` est l'identifiant
    de l'objet dans SON app.

    Alimenté par ``services.recompute_features`` (best-effort, Celery) ; un
    scorer/sélecteur consomme le vecteur via ``selectors.feature_vector``
    quand présent, et retombe sur un calcul direct sinon (repli inchangé).
    """

    content_type = models.CharField(max_length=60)
    object_id = models.PositiveBigIntegerField()
    features_json = models.JSONField(default=dict, blank=True)
    calcule_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Vecteur de features'
        verbose_name_plural = 'Vecteurs de features'
        ordering = ['content_type', 'object_id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'content_type', 'object_id'],
                name='uniq_mlops_featvec_co_ct_obj'),
        ]
        indexes = [
            models.Index(fields=['company', 'content_type'],
                         name='mlops_featvec_co_ct_idx'),
        ]

    def __str__(self):
        return f'{self.content_type}:{self.object_id}'
