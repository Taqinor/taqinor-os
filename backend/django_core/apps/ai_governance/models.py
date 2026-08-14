"""Modèles du module « ai_governance » (Groupe NTAI).

MULTI-TENANT : tout modèle ici hérite de ``core.models.TenantModel`` (FK
``company`` + horodatage) — la société est TOUJOURS posée côté serveur, jamais
lue d'un corps de requête.
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel


class DriftSnapshot(TenantModel):
    """NTAI29 — Photo mensuelle de la distribution des features d'un scorer.

    Sert à détecter une DÉRIVE (drift) : quand la population sur laquelle un
    scorer tourne ne ressemble plus à celle de sa baseline, ses prédictions
    deviennent silencieusement moins fiables. Le ``psi`` (Population Stability
    Index) mesure cet écart par rapport au snapshot de RÉFÉRENCE de la même
    société et du même modèle.

    Purement OFFLINE : aucune donnée ne sort, aucun LLM n'est appelé — le PSI
    est calculé avec la bibliothèque standard (``math.log``).
    """

    #: Le premier snapshot d'un couple (société, modèle) devient la référence
    #: à laquelle les suivants se comparent ; son ``psi`` reste nul.
    modele = models.CharField(
        max_length=60,
        help_text="Nom du scorer surveillé (churn, win_proba, "
                  "retard_paiement…).")
    date = models.DateField(
        help_text='Premier jour de la période observée.')
    distribution_json = models.JSONField(
        default=dict, blank=True,
        help_text='{bucket: proportion} des features d\'entrée observées.')
    psi = models.FloatField(
        default=0.0,
        help_text='Population Stability Index vs la baseline (0 = identique).')
    est_baseline = models.BooleanField(
        default=False,
        help_text='Snapshot de référence auquel les suivants se comparent.')
    alerte_emise = models.BooleanField(
        default=False,
        help_text='Une alerte de dérive a été notifiée pour ce snapshot.')

    class Meta:
        verbose_name = 'Snapshot de dérive'
        verbose_name_plural = 'Snapshots de dérive'
        ordering = ['-date', 'modele']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'modele', 'date'],
                name='uniq_driftsnapshot_company_modele_date'),
        ]
        indexes = [
            # Nom EXPLICITE : sans lui, Django en dérive un hash qui diverge
            # du nom écrit à la main dans la migration (piège connu du dépôt).
            models.Index(fields=['company', 'modele', '-date'],
                         name='ai_gov_drift_co_mod_date_idx'),
        ]

    def __str__(self):
        return f'{self.modele} @ {self.date} (PSI {self.psi:.3f})'


class DocumentAiJob(TenantModel):
    """NTAI17 — Un traitement IA (classification + extraction) d'une pièce GED.

    La pièce est déposée dans la GED ; un job est créé (``en_attente``) et une
    tâche Celery BEST-EFFORT le traite hors requête : elle CLASSE le document
    (réutilise l'heuristique GED34, gratuite et déterministe, puis le provider
    IA s'il est configuré) puis EXTRAIT les champs du gabarit correspondant au
    type détecté (``core.ai.extract_document``).

    INVARIANTS :

      * **Rien n'est écrit dans un modèle métier.** Le résultat vit dans
        ``resultat_json`` et attend une validation humaine (NTAI18) — le job ne
        crée ni facture, ni contrat, ni ligne de stock.
      * **Key-gated.** Sans provider OCR configuré, l'extraction est un no-op
        propre : aucun octet n'est lu du stockage, aucun appel réseau, le job
        finit ``traite`` avec ``extraction_disponible: false``.
      * **Jamais bloquant.** Une erreur est CAPTURÉE dans ``statut='erreur'`` +
        ``message`` ; elle ne remonte jamais à l'écriture documentaire.
    """

    STATUT_EN_ATTENTE = 'en_attente'
    STATUT_TRAITE = 'traite'
    STATUT_ERREUR = 'erreur'
    STATUT_CHOICES = [
        (STATUT_EN_ATTENTE, 'En attente'),
        (STATUT_TRAITE, 'Traité'),
        (STATUT_ERREUR, 'Erreur'),
    ]

    #: FK déclarée par CHAÎNE (``'ged.Document'``) — ``ai_governance`` ne monte
    #: jamais dans les modèles d'une autre app ; les lectures passent par les
    #: ``selectors``/``services`` de la GED.
    document = models.ForeignKey(
        # on_delete: le job n'a aucun sens sans sa pièce — il ne porte qu'une
        # PROPOSITION d'extraction, aucune donnée métier ni comptable. Quand la
        # pièce disparaît, la proposition disparaît avec elle.
        'ged.Document', on_delete=models.CASCADE, related_name='ai_jobs',
        help_text='Pièce GED traitée (le job meurt avec elle).')
    categorie = models.CharField(
        max_length=60, blank=True, default='',
        help_text='Catégorie détectée par la classification (GED34).')
    schema = models.CharField(
        max_length=60, blank=True, default='',
        help_text="Gabarit d'extraction retenu pour la catégorie détectée.")
    statut = models.CharField(
        max_length=20, choices=STATUT_CHOICES, default=STATUT_EN_ATTENTE)
    resultat_json = models.JSONField(
        default=dict, blank=True,
        help_text='Résultat brut proposé (champs extraits) — jamais appliqué '
                  'automatiquement à un modèle métier.')
    confiance = models.FloatField(
        default=0.0,
        help_text='Confiance rapportée par le fournisseur (0 = inconnue).')
    message = models.TextField(
        blank=True, default='',
        help_text="Message d'erreur capturé (statut « erreur »).")
    traite_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Traitement IA de document'
        verbose_name_plural = 'Traitements IA de documents'
        ordering = ['-created_at', '-id']
        indexes = [
            # Noms EXPLICITES (≤30 car.) : sans eux Django dérive un hash qui
            # diverge du nom écrit à la main dans la migration.
            models.Index(fields=['company', 'statut'],
                         name='ai_gov_docjob_co_stat_idx'),
            models.Index(fields=['company', 'document'],
                         name='ai_gov_docjob_co_doc_idx'),
        ]

    def __str__(self):
        return f'Job IA #{self.pk} ({self.statut})'


class ExtractionCorrection(TenantModel):
    """NTAI18 — Un écart entre ce que l'IA a extrait et ce que l'humain valide.

    Chaque champ corrigé lors de la revue laisse une ligne : la valeur PROPOSÉE
    (``valeur_ia``) ET la valeur RETENUE (``valeur_corrigee``). Deux usages :

      * mesurer la qualité RÉELLE d'un gabarit (taux de correction par schéma) ;
      * constituer, sans travail supplémentaire, le « jeu d'or » qui permettra
        plus tard d'évaluer un nouveau modèle sur des cas vrais.

    Une ligne où ``valeur_ia == valeur_corrigee`` est une VALIDATION (l'humain a
    confirmé) ; elle compte dans le dénominateur, pas dans les corrections.
    """

    job = models.ForeignKey(
        # on_delete: la correction documente l'extraction d'un job précis ;
        # sans lui elle ne veut plus rien dire (ce n'est ni une donnée métier
        # ni une pièce comptable).
        DocumentAiJob, on_delete=models.CASCADE, related_name='corrections')
    champ = models.CharField(
        max_length=120, help_text='Clé du champ extrait (ex. « numero_cin »).')
    valeur_ia = models.TextField(
        blank=True, default='', help_text="Valeur proposée par l'extraction.")
    valeur_corrigee = models.TextField(
        blank=True, default='', help_text="Valeur retenue par l'humain.")
    corrige_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ai_extraction_corrections')
    corrige_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Correction d'extraction"
        verbose_name_plural = "Corrections d'extraction"
        ordering = ['-corrige_le', '-id']
        indexes = [
            models.Index(fields=['company', 'job'],
                         name='ai_gov_corr_co_job_idx'),
        ]

    @property
    def est_une_correction(self) -> bool:
        """True quand l'humain a MODIFIÉ la valeur (et non simplement validée)."""
        return (self.valeur_ia or '') != (self.valeur_corrigee or '')

    def __str__(self):
        return f'{self.champ} (job #{self.job_id})'
