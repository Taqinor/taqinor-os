"""Modèles du module « conversation_ai » (Groupe NTAI).

MULTI-TENANT : tout modèle hérite de ``core.models.TenantModel`` (FK
``company`` + horodatage) — la société est TOUJOURS posée côté serveur, jamais
lue d'un corps de requête.

DÉCOUPLAGE : les rattachements CRM (lead/client) sont des FK déclarées par
CHAÎNE (``'crm.Lead'``) — ce module n'importe jamais les modèles d'une autre
app ; ses lectures cross-app passent par les ``selectors``/``services`` de la
cible.
"""
from django.db import models

from core.models import TenantModel


class AppelCommercial(TenantModel):
    """NTAI21 — Un enregistrement d'appel commercial téléversé.

    Le fichier audio vit dans le stockage objet (clé ``fichier_key``, préfixée
    par la société — SCA42) ; seul le pointeur vit en base. La transcription
    est faite HORS REQUÊTE par une tâche Celery best-effort.

    KEY-GATED : sans fournisseur STT configuré, l'appel reste au statut
    ``non_transcrit`` — aucun appel réseau, aucun coût, aucune erreur.

    À NE PAS CONFONDRE avec ``voip.Appel`` : celui-là JOURNALISE un appel VoIP
    (direction, numéro, durée, issue) et ne porte ni enregistrement ni
    transcript. Ici c'est l'inverse : un fichier audio déposé par un
    commercial, dont on veut le TEXTE. Les deux modèles restent séparés.
    """

    STATUT_NON_TRANSCRIT = 'non_transcrit'
    STATUT_EN_COURS = 'en_cours'
    STATUT_TRANSCRIT = 'transcrit'
    STATUT_ERREUR = 'erreur'
    STATUT_CHOICES = [
        (STATUT_NON_TRANSCRIT, 'Non transcrit'),
        (STATUT_EN_COURS, 'Transcription en cours'),
        (STATUT_TRANSCRIT, 'Transcrit'),
        (STATUT_ERREUR, 'Erreur'),
    ]

    lead = models.ForeignKey(
        'crm.Lead', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='appels_commerciaux',
        help_text='Lead auquel l\'appel est rattaché (facultatif).')
    client = models.ForeignKey(
        'crm.Client', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='appels_commerciaux',
        help_text='Client auquel l\'appel est rattaché (facultatif).')
    fichier_key = models.CharField(
        max_length=500, blank=True, default='',
        help_text='Clé de l\'objet audio dans le stockage (préfixée société).')
    mime = models.CharField(max_length=120, blank=True, default='')
    duree_s = models.PositiveIntegerField(
        default=0, help_text="Durée de l'appel en secondes (0 = inconnue).")
    transcript = models.TextField(
        blank=True, default='',
        help_text='Transcription produite par le fournisseur STT.')
    statut = models.CharField(
        max_length=20, choices=STATUT_CHOICES, default=STATUT_NON_TRANSCRIT)
    message = models.TextField(
        blank=True, default='',
        help_text="Message d'erreur capturé (statut « erreur »).")
    transcrit_le = models.DateTimeField(null=True, blank=True)
    # NTAI22 — analyse du transcript : {objections, next_steps, produits,
    # sentiment}. Vide tant que personne n'a demandé l'analyse ; stockée pour
    # que l'agrégation de coaching (NTAI23) n'ait jamais à rappeler le LLM.
    analyse_json = models.JSONField(default=dict, blank=True)
    sentiment = models.CharField(
        max_length=10, blank=True, default='',
        help_text='Sentiment global déduit du transcript (positif/neutre/'
                  'negatif) — vide tant que l\'appel n\'est pas analysé.')
    analyse_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Appel commercial'
        verbose_name_plural = 'Appels commerciaux'
        ordering = ['-created_at', '-id']
        indexes = [
            # Noms EXPLICITES (≤30 car.) : sans eux Django dérive un hash qui
            # diverge du nom écrit à la main dans la migration.
            models.Index(fields=['company', 'statut'],
                         name='conv_ai_appel_co_stat_idx'),
            models.Index(fields=['company', 'lead'],
                         name='conv_ai_appel_co_lead_idx'),
        ]

    def __str__(self):
        return f'Appel #{self.pk} ({self.statut})'
