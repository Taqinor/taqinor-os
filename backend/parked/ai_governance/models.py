"""Modèles du module « ai_governance » (Groupe NTAI).

MULTI-TENANT : tout modèle ici hérite de ``core.models.TenantModel`` (FK
``company`` + horodatage) — la société est TOUJOURS posée côté serveur, jamais
lue d'un corps de requête.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import TenantModel


class LlmUsageRecord(TenantModel):
    """NTAI1 — Une ligne par appel RÉEL à une capacité IA.

    Sert à répondre, par société, à « qui consomme l'IA, combien, et à quel
    coût ». Écrite best-effort par le puits enregistré dans
    ``apps.py::ready()`` depuis la fondation ``core.ai.usage``.

    INVARIANTS :

      * **Aucune donnée métier.** Ni prompt, ni réponse, ni identifiant d'objet :
        seulement des MÉTRIQUES. Le journal ne peut pas devenir un second
        magasin de données clients.
      * **Société posée côté serveur.** Elle vient du contexte d'appel
        (``core.ai.usage.usage_context``), jamais d'un corps de requête ; sans
        société connue, aucune ligne n'est écrite.
      * **Coût jamais inventé.** ``cout_tarife=False`` signifie « aucun tarif
        configuré pour ce fournisseur » : ``cost_estimated`` vaut alors 0 mais
        c'est un coût INCONNU, pas un coût nul — et l'agrégat le dit.
      * **Chemin NO-OP muet.** Sans fournisseur configuré, rien n'est appelé
        donc rien n'est journalisé (aucune ligne parasite).
    """

    CAPACITE_CHOICES = [
        ('ocr', 'OCR (document)'),
        ('stt', 'Transcription audio'),
        ('vision_qa', 'Contrôle vision'),
        ('llm', 'Génération de texte'),
    ]

    capability = models.CharField(
        max_length=20, choices=CAPACITE_CHOICES,
        help_text='Capacité IA appelée.')
    provider = models.CharField(
        max_length=60, help_text='Clé du fournisseur ayant servi l\'appel.')
    feature_key = models.CharField(
        max_length=120, blank=True, default='',
        help_text='Feature appelante (ex. « ai.rediger ») — texte libre posé '
                  'par la couche appelante, jamais par le client.')
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    #: UNITÉ : le micro-MAD (10⁻⁶ MAD), entier — PAS un DecimalField.
    #: Un appel LLM coûte une FRACTION de centime : à 2 décimales (la règle
    #: monétaire du dépôt, YDATA7) chaque ligne s'arrondirait à 0,00 et le
    #: total mensuel afficherait « gratuit » — un chiffre faux, donc interdit.
    #: L'entier est exact, se somme sans dérive, et la propriété
    #: :attr:`cost_estimated` le rend en MAD pour l'affichage.
    cost_estimated_micro_mad = models.PositiveBigIntegerField(
        default=0,
        help_text='Coût estimé en micro-MAD (10⁻⁶ MAD) — significatif '
                  'UNIQUEMENT si « cout_tarife » est vrai.')
    cout_tarife = models.BooleanField(
        default=False,
        help_text='Un tarif était configuré pour ce fournisseur au moment de '
                  'l\'appel ; sinon le coût est inconnu (et non nul).')
    latency_ms = models.PositiveIntegerField(default=0)
    success = models.BooleanField(default=True)
    message = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Message d\'erreur du fournisseur (jamais le contenu du '
                  'prompt).')

    class Meta:
        verbose_name = "Usage d'une capacité IA"
        verbose_name_plural = "Usages des capacités IA"
        ordering = ['-created_at', '-id']
        indexes = [
            # Noms EXPLICITES (≤30 car.) : sans eux Django dérive un hash qui
            # diverge du nom écrit à la main dans la migration.
            models.Index(fields=['company', '-created_at'],
                         name='ai_gov_usage_co_date_idx'),
            models.Index(fields=['company', 'feature_key'],
                         name='ai_gov_usage_co_feat_idx'),
        ]

    @property
    def cost_estimated(self) -> Decimal:
        """Coût estimé en MAD (dérivé de l'entier micro-MAD, sans perte)."""
        return (Decimal(self.cost_estimated_micro_mad or 0)
                / Decimal('1000000')).quantize(Decimal('0.000001'))

    def __str__(self):
        return f'{self.capability}/{self.provider} ({self.created_at:%Y-%m-%d})'


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


class LlmBudget(TenantModel):
    """NTAI2 — Plafond mensuel de dépense IA d'une société + seuil d'alerte.

    Le budget est le COUPE-CIRCUIT de la facture IA : au-delà de 100 % du
    plafond, ``core.ai.registry.get_provider('llm')`` rend le fournisseur NO-OP
    « budget épuisé » et chaque feature générative dégrade proprement (503
    douce, message FR) au lieu de continuer à facturer. Au franchissement du
    seuil d'alerte, les responsables sont prévenus UNE fois par mois
    (``alerte_periode`` rend l'alerte idempotente).

    Un seul budget par société (contrainte d'unicité) : sans elle, deux lignes
    concurrentes rendraient le coupe-circuit non déterministe.

    Le plafond est comparé à la dépense RÉELLE journalisée (NTAI1). Sans tarif
    configuré pour le fournisseur, la dépense connue reste nulle : le
    coupe-circuit ne se déclenche donc JAMAIS sur un chiffre inventé.
    """

    montant_mensuel_mad = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='Plafond de dépense IA du mois, en MAD.')
    seuil_alerte_pct = models.PositiveSmallIntegerField(
        default=80,
        help_text='Pourcentage du plafond déclenchant une alerte (défaut 80).')
    actif = models.BooleanField(
        default=True,
        help_text="Un budget inactif ne bride rien et n'alerte pas.")
    alerte_periode = models.CharField(
        max_length=7, blank=True, default='',
        help_text='Période « AAAA-MM » de la dernière alerte émise — rend '
                  "l'alerte idempotente sur le mois.")

    class Meta:
        verbose_name = 'Budget IA'
        verbose_name_plural = 'Budgets IA'
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company'], name='uniq_llmbudget_company'),
        ]

    def __str__(self):
        return f'Budget IA {self.montant_mensuel_mad} MAD/mois'


class PromptTemplate(TenantModel):
    """NTAI5 — Surcharge société du prompt d'une feature IA.

    Le défaut vit dans le CODE (``core.ai.prompts.register_default_prompt``) ;
    cette table ne porte que ce qu'une société a choisi de changer. Aucune
    ligne = comportement byte-identique à l'avant-NTAI5.

    ``cle`` identifie la feature (``'ai.rediger.email'``) et est unique PAR
    SOCIÉTÉ : deux sociétés peuvent surcharger la même feature différemment,
    et aucune ne voit celle de l'autre.

    Chaque changement de ``corps`` fige une :class:`PromptTemplateVersion` :
    on peut toujours dire quel texte a produit un brouillon donné.
    """

    cle = models.CharField(
        max_length=120,
        help_text="Clé de la feature IA surchargée (ex. « ai.rediger.email »).")
    label = models.CharField(
        max_length=160, blank=True, default='',
        help_text='Libellé lisible affiché dans l\'écran de paramétrage.')
    corps = models.TextField(
        help_text='Corps du prompt, avec des placeholders {{champ}}.')
    capability = models.CharField(
        max_length=20, blank=True, default='llm',
        help_text='Capacité concernée (llm/ocr/stt/vision_qa).')
    actif = models.BooleanField(
        default=True,
        help_text='Une surcharge inactive laisse le défaut code s\'appliquer.')

    class Meta:
        verbose_name = 'Gabarit de prompt'
        verbose_name_plural = 'Gabarits de prompt'
        ordering = ['cle']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'cle'], name='uniq_prompttemplate_co_cle'),
        ]
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='ai_gov_prompt_co_actif_idx'),
        ]

    def __str__(self):
        return self.label or self.cle


class PromptTemplateVersion(TenantModel):
    """NTAI5 — Photo IMMUABLE d'un corps de prompt à un instant donné.

    Écrite par le serveur à chaque changement de corps ; jamais modifiée
    ensuite (aucune route d'écriture ne l'expose). Le numéro est attribué côté
    serveur, par gabarit.
    """

    template = models.ForeignKey(
        # on_delete: une version n'a de sens que rattachée à son gabarit ;
        # ce n'est ni une donnée métier ni une pièce comptable.
        PromptTemplate, on_delete=models.CASCADE, related_name='versions')
    numero = models.PositiveIntegerField(default=1)
    corps = models.TextField(blank=True, default='')
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ai_prompt_versions')
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Version de gabarit de prompt'
        verbose_name_plural = 'Versions de gabarit de prompt'
        ordering = ['-numero', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['template', 'numero'],
                name='uniq_prompttemplateversion_num'),
        ]

    def __str__(self):
        return f'{self.template_id} v{self.numero}'


class AiFeatureToggle(TenantModel):
    """NTAI7 — Consentement IA d'une société, feature par feature.

    Une société peut refuser l'IA sur un périmètre précis (« pas d'IA sur les
    données RH ») sans renoncer au reste. **Le défaut est ACTIF** : l'absence
    de ligne veut dire « rien n'a été refusé », donc le comportement reste
    byte-identique à l'avant-NTAI7. Couper une feature est une décision
    explicite, jamais un effet de bord.

    Le refus est strictement scopé société : couper « ai.rediger » chez l'un
    ne change rien chez l'autre.
    """

    feature_key = models.CharField(
        max_length=120,
        help_text='Clé de la feature IA (ex. « ai.rediger »), telle qu\'elle '
                  'apparaît aussi dans le journal d\'usage.')
    actif = models.BooleanField(
        default=True,
        help_text='Décoché = la feature devient inopérante pour cette société.')
    motif = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Pourquoi la société a coupé cette feature (traçabilité).')

    class Meta:
        verbose_name = 'Consentement IA'
        verbose_name_plural = 'Consentements IA'
        ordering = ['feature_key']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'feature_key'],
                name='uniq_aifeaturetoggle_co_key'),
        ]

    def __str__(self):
        return f'{self.feature_key} ({"actif" if self.actif else "coupé"})'
