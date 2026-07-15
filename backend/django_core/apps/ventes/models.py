from django.db import models
from django.conf import settings

# M1 — cross-app FKs use Django's lazy "app.Model" string form so this module
# imports no sibling app's models at load time (breaks the crm⇄ventes /
# stock⇄ventes import cycles without any schema change).


class Devis(models.Model):
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        ENVOYE = 'envoye', 'Envoyé'
        ACCEPTE = 'accepte', 'Accepté'
        REFUSE = 'refuse', 'Refusé'
        EXPIRE = 'expire', 'Expiré'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='devis',
    )
    reference = models.CharField(max_length=50)
    client = models.ForeignKey(
        'crm.Client',
        on_delete=models.PROTECT,
        related_name='devis',
    )
    # Lead d'origine quand le devis part d'un lead (le client est alors résolu
    # automatiquement depuis le lead). Toujours par société, jamais obligatoire.
    lead = models.ForeignKey(
        'crm.Lead',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='devis',
    )
    statut = models.CharField(
        max_length=20,
        choices=Statut.choices,
        default=Statut.BROUILLON,
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_validite = models.DateField(null=True, blank=True)
    taux_tva = models.DecimalField(
        max_digits=5, decimal_places=2, default=20.00
    )
    remise_globale = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='devis_crees',
    )
    fichier_pdf = models.CharField(
        max_length=500, blank=True, null=True
    )
    # ── Envoi explicite (U4) — additif, optionnel. Horodatage du moment où le
    # devis est partagé au client (ex. via WhatsApp). Posé UNE fois lors du
    # passage brouillon → envoyé par le service ventes ; jamais réécrit ensuite.
    date_envoi = models.DateTimeField(null=True, blank=True)

    # ── Acceptation explicite (N25) — additif. Date choisie + nom de la
    # personne qui accepte, consignés dans le chatter du devis. C'est le
    # déclencheur officiel de la création d'un chantier (devis « accepté »).
    date_acceptation = models.DateField(null=True, blank=True)
    accepte_par_nom = models.CharField(max_length=150, blank=True, default='')

    # ── Refus explicite (FG44) — additif. Date + motif de refus capturés lors
    # de l'action « refuser » (symétrique à « accepter »). Le chatter est mis à
    # jour et, si le devis est lié à un lead, l'événement devis_refused est
    # émis via core/events.py pour que le CRM puisse marquer le lead perdu.
    date_refus = models.DateField(null=True, blank=True)
    motif_refus = models.CharField(max_length=255, blank=True, default='')

    # ── Option retenue à l'acceptation (A1) — additif. Pour un devis à deux
    # options (« Sans batterie » / « Avec batterie »), enregistre laquelle le
    # client a choisie ; vide pour un devis à option unique. Cette valeur est
    # autoritative en aval (facture & chantier — A3). N'invente aucun nouveau
    # statut : le devis reste « accepté », on note seulement l'option.
    class OptionAcceptee(models.TextChoices):
        SANS_BATTERIE = 'sans_batterie', 'Sans batterie'
        AVEC_BATTERIE = 'avec_batterie', 'Avec batterie'

    option_acceptee = models.CharField(
        max_length=20, choices=OptionAcceptee.choices, blank=True, default='')

    # ── Multi-marchés (2026-06) — additif, tout optionnel ──
    class ModeInstallation(models.TextChoices):
        RESIDENTIEL = 'residentiel', 'Résidentiel'
        INDUSTRIEL = 'industriel', 'Industriel / Commercial'
        AGRICOLE = 'agricole', 'Agricole (pompage)'

    mode_installation = models.CharField(
        max_length=20, choices=ModeInstallation.choices,
        blank=True, null=True,
    )
    # Paramètres d'étude/simulation stockés avec le devis (kWc, production,
    # autoconsommation/couverture, économies, payback, pompe CV/HMT/débit…).
    etude_params = models.JSONField(blank=True, null=True)
    # ── Échéancier personnalisé (FG46) — additif, tout optionnel ──
    # Liste ordonnée de tranches : [{libelle, type, pct_or_montant}].
    # « type » = 'acompte'|'intermediaire'|'solde'.
    # « pct_or_montant » : float ≥ 0. Si tous les types ont un pct, la somme
    # doit avoisiner 100 (±0.1). La dernière tranche est toujours recalculée
    # en « reste » pour que la somme des factures égale le total TTC du devis
    # au centime près. Vide = comportement historique 3 tranches.
    echeancier = models.JSONField(
        blank=True, null=True,
        verbose_name='Échéancier personnalisé',
        help_text='Liste ordonnée de tranches [{libelle, type, pct_or_montant}].'
                  ' Vide = 3 tranches par défaut.',
    )
    # Acompte persisté séparément pour accès rapide (PDF, dashboard, synthèse).
    # La valeur mémorisée au moment de la sauvegarde — pas recalculée en live.
    acompte_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='Acompte (%)',
        help_text='Pourcentage de la première tranche. Persiste la valeur choisie.',
    )
    acompte_montant = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Acompte (MAD TTC)',
        help_text='Montant TTC de la première tranche. Calculé ou saisi.',
    )
    prix_cible_kwc = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    # ── SCA47 — prix au kWc DÉRIVÉ, gelé à la création (leçon ServiceTitan
    # Price Insights) ──
    # Signal comparable = Total TTC ÷ puissance kWc (le kWc vit déjà dans
    # etude_params). Recomputable aujourd'hui mais le backfiller dans 2 ans
    # coûterait bien plus que le dériver à l'écriture. Écrit UNE SEULE FOIS,
    # quand le kWc est présent ET qu'un total existe (donc null pour le pompage
    # sans kWc — jamais forcé) ; jamais recalculé ensuite (write-once).
    #
    # DONNÉE INTERNE générateur/BI — MÊME RÉGIME que prix_achat : n'apparaît sur
    # AUCUN PDF ni aucune sortie client (alimente NTDATA46/47 + la couche
    # métrique NTDATA7-13, nommées).
    prix_par_kwc = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Prix TTC au kWc, dérivé et gelé à la création (interne '
                  'générateur/BI — jamais sur un PDF/sortie client).')
    # ── Révisions / versionnage (T10) — additif. Un devis envoyé peut être
    # révisé en une nouvelle version qui garde l'historique lisible. La version
    # courante porte is_active=True ; les versions remplacées pointent vers leur
    # remplaçante (superseded_by) et redeviennent en lecture seule côté UI.
    # Approbation de remise (T17) : quand la remise dépasse le seuil société,
    # le passage en « envoyé » exige une approbation admin/propriétaire.
    remise_approuvee = models.BooleanField(default=False)
    remise_approuvee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='remises_approuvees')
    version = models.PositiveIntegerField(default=1)
    version_parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='versions_enfants')
    superseded_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='remplace')
    is_active = models.BooleanField(default=True)
    # FG100 — champs personnalisés (additif, jamais destructif).
    # Les définitions viennent de apps.customfields (module='devis').
    custom_data = models.JSONField(null=True, blank=True)

    # ── FG52 — Devise (multi-currency) — additif, tout optionnel ──
    # « devise » : code ISO 4217 (« MAD » par défaut — comportement inchangé pour
    # tous les devis existants). « taux_change » : taux de conversion MAD→devise
    # saisi à la création (1.0 par défaut = MAD, sans conversion). La devise est
    # uniquement PORTÉE par le document ; les montants restent en MAD en base,
    # le taux de change est un libellé informatif affiché sur le PDF et l'export UBL.
    devise = models.CharField(
        max_length=10, default='MAD',
        verbose_name='Devise',
        help_text='Code ISO 4217 (ex. MAD, EUR, USD). Défaut MAD.',
    )
    taux_change = models.DecimalField(
        max_digits=12, decimal_places=6, default=1,
        verbose_name='Taux de change',
        help_text='1 MAD = X devise (1 = MAD, sans conversion).',
    )

    # ── Q1 — Toiture 3D : layout FINALISÉ (additif, optionnel) ──
    # JSON sérialisé de l'outil roofPro11 (apps/web) une fois la conception
    # validée par Meriem : AreaRecord[] (sommets de toiture, obstacles,
    # roofType, pitch, azimuth), le résultat {panels, kwc, annualKwh, savings}
    # et le renderPlan. SEUL ce layout finalisé (panneaux placés) alimente la
    # proposition — distinct du pin/contour brut du client posé sur le Lead
    # (apps.crm.Lead.roof_point). Vide → comportement historique inchangé.
    roof_layout = models.JSONField(null=True, blank=True)
    # ── Q4 — Rendu 3D de la toiture (clé MinIO, additif, optionnel) ──
    # Clé de l'image PNG « votre installation » (snapshot 3D) stockée dans le
    # bucket PDF, scopée société. Vide → la proposition n'affiche pas de rendu.
    roof_image = models.CharField(max_length=500, blank=True, null=True)
    # ── QJ17 — Layout hash pour la déduplication (from-layout idempotency) ──
    # SHA-256 du layout géométrique (zones + result + scenario) posé lors du
    # premier « Générer ». Null pour les devis antérieurs ou créés sans layout.
    # Longueur 64 = SHA-256 hex (max 63 chars pour l'index Oracle — unused here,
    # mais on plafonne à 64 pour la cohérence). Index ≤ 30 chars : lyt_hash_idx.
    layout_hash = models.CharField(max_length=64, null=True, blank=True, db_index=True)

    # ── QX23be — instantané de MARGE (usage manager UNIQUEMENT) ──
    # Marge HT figée au save/envoi = Σ(HT lignes) − Σ(qté × prix_achat produit).
    # NULLABLE (les devis dont aucun produit lié n'a de prix_achat gardent None).
    # RÈGLE #4 / prix_achat : cette valeur ne DOIT JAMAIS apparaître dans un PDF
    # ou une sortie client — elle n'est exposée que dans la vue liste/générateur
    # côté responsable (voir DevisSerializer.marge_snapshot, manager-only).
    marge_snapshot = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Marge HT figée (interne, manager-only)')

    # VX98 — fraîcheur : horodatage (auto_now) + dernier auteur d'une
    # modification (posé server-side dans perform_update, jamais accepté du
    # corps). Alimente la puce « modifié par X il y a N min » (silencieuse si
    # NULL ou si c'est l'utilisateur courant). updated_by suit le pattern
    # archived_by ; NULL sur les devis antérieurs à la migration.
    updated_at = models.DateTimeField(auto_now=True, null=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='devis_modifies',
    )

    class Meta:
        verbose_name = 'Devis'
        verbose_name_plural = 'Devis'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]
        # SCA39 — index chemin-de-l'argent (sous-ensemble Devis de NTPLT20).
        # (company, statut) couvre les listes filtrées par statut (11+ sites) ;
        # (company, date_creation) couvre la liste par défaut (scopée société,
        # triée -date_creation). Posés SANS verrou d'écriture bloquant via
        # AddIndexConcurrently + lock_timeout (YOPSB6) dans la migration.
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='ventes_devis_co_statut_idx'),
            models.Index(
                fields=['company', 'date_creation'],
                name='ventes_devis_co_datecrea_idx'),
        ]

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        """SCA47 — dérive et GÈLE ``prix_par_kwc`` (Total TTC ÷ kWc) une seule
        fois, dès qu'un kWc (etude_params) et un total existent. Write-once :
        une fois posée, la valeur n'est JAMAIS recalculée (un ``update_fields``
        qui ne la cite pas la laisse intacte). Null pour un devis sans kWc
        (pompage) — jamais forcé. Donnée interne (jamais sur un PDF)."""
        from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
        super().save(*args, **kwargs)
        if self.prix_par_kwc is not None:
            return  # déjà gelée — jamais recalculée.
        kwc = (self.etude_params or {}).get('puissance_kwc')
        try:
            kwc_val = Decimal(str(kwc)) if kwc else Decimal('0')
        except (InvalidOperation, TypeError, ValueError):
            kwc_val = Decimal('0')
        if kwc_val <= 0:
            return  # pas de kWc → reste null (pompage / devis sans étude).
        total = self.total_ttc
        if not total or total <= 0:
            return  # pas encore de lignes → on gèlera au prochain save utile.
        prix = (Decimal(str(total)) / kwc_val).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP)
        # Écriture ciblée (ne touche que cette colonne) — la valeur est gelée.
        type(self).objects.filter(pk=self.pk).update(prix_par_kwc=prix)
        self.prix_par_kwc = prix

    @property
    def total_ht(self):
        return sum(ligne.total_ht for ligne in self.lignes.all())

    @property
    def total_tva(self):
        # ERR71 — TVA réconciliée au centime, par panier de taux, EXACTEMENT
        # comme Facture/échéancier (tva_par_taux) pour que devis et facture
        # s'accordent au centime sur un devis à taux mixtes (10/20). Mono-taux
        # (anciens devis : toutes lignes NULL → un seul panier) → formule
        # d'origine HT×taux, rendu strictement inchangé.
        from decimal import Decimal
        return sum((b['montant'] for b in self.tva_par_taux), Decimal('0'))

    @property
    def tva_par_taux(self):
        """Ventilation TVA par taux (10 % / 20 %), réconciliée au centime.

        Miroir exact de ``Facture.tva_par_taux`` : mono-taux → un panier calculé
        par la formule d'origine (HT × taux, aucun arrondi par panier → figures
        historiques strictement identiques) ; taux mixtes → un panier par taux,
        chaque TVA arrondie au centime, dont la somme est le total TVA.

        DC23 — délègue au selector unique ``tva_buckets`` (une seule logique de
        bucket partagée par Devis/Facture/Avoir + exports DGI/FEC).
        """
        from .selectors import tva_buckets
        return tva_buckets(self.lignes.all(), fallback_taux=self.taux_tva)

    @property
    def total_ttc(self):
        return self.total_ht + self.total_tva


class LigneDevis(models.Model):
    devis = models.ForeignKey(
        Devis, on_delete=models.CASCADE, related_name='lignes'
    )
    produit = models.ForeignKey(
        'stock.Produit',
        on_delete=models.PROTECT,
        related_name='lignes_devis',
    )
    designation = models.CharField(max_length=255)
    quantite = models.DecimalField(max_digits=10, decimal_places=2)
    prix_unitaire = models.DecimalField(
        max_digits=10, decimal_places=2
    )
    remise = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    # TVA par ligne (réforme marocaine 2024–2026 : 10 % panneaux PV, 20 %
    # le reste). NULL = ligne historique → le taux du devis s'applique,
    # rendu strictement inchangé pour les anciens devis.
    taux_tva = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Taux TVA de la ligne (%). Vide = taux global du devis.')

    # ── QJ29 — Multi-propriétés (villas différentes) — additif, tout optionnel ─
    # Partitionne les lignes en groupes par-villa dans UN SEUL document (pas de
    # scission du devis). ``groupe_index`` : 0 = équipement commun, 1..N = villa
    # N ; NULL = ligne historique (chemin mono-système inchangé au bit près).
    # ``groupe_label`` : libellé lisible de la villa (« Villa A »…), vide sinon.
    groupe_index = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Groupe multi-villa : 0 = commun, 1..N = villa N. '
                  'Vide = document mono-système (comportement historique).')
    groupe_label = models.CharField(
        max_length=80, blank=True, default='',
        help_text='Libellé de la villa/du groupe (ex. « Villa A »). '
                  'Vide = pas de groupe.')

    class Meta:
        verbose_name = 'Ligne de Devis'
        verbose_name_plural = 'Lignes de Devis'

    @property
    def total_ht(self):
        return (
            self.quantite * self.prix_unitaire * (1 - self.remise / 100)
        )

    @property
    def taux_tva_effectif(self):
        """Taux réellement appliqué : celui de la ligne, sinon celui du devis."""
        return self.taux_tva if self.taux_tva is not None else self.devis.taux_tva


class DevisActivity(models.Model):
    """Chatter d'un devis (N25) — même patron que InstallationActivity.

    Notes manuelles + événements (acceptation). Utilisateur et société posés
    côté serveur, jamais lus du corps de la requête."""
    class Kind(models.TextChoices):
        CREATION = 'creation', 'Création'
        MODIFICATION = 'modification', 'Modification'
        NOTE = 'note', 'Note'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='devis_activities')
    devis = models.ForeignKey(
        Devis, on_delete=models.CASCADE, related_name='activites')
    kind = models.CharField(max_length=15, choices=Kind.choices)
    field = models.CharField(max_length=100, blank=True, null=True)
    field_label = models.CharField(max_length=150, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='devis_activities')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Activité devis'
        verbose_name_plural = 'Activités devis'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['devis', '-created_at'],
                                name='ventes_devisact_idx')]

    def __str__(self):
        return f"{self.devis_id} {self.kind} {self.field or ''}".strip()


class FactureActivity(models.Model):
    """Chatter d'une facture — même patron que DevisActivity.

    Trace les événements comptables (avoir créé, paiement encaissé) + notes
    éventuelles. Utilisateur et société posés côté serveur, jamais lus du
    corps de la requête."""
    class Kind(models.TextChoices):
        CREATION = 'creation', 'Création'
        MODIFICATION = 'modification', 'Modification'
        NOTE = 'note', 'Note'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='facture_activities')
    facture = models.ForeignKey(
        'facturation.Facture', on_delete=models.CASCADE, related_name='activites')
    kind = models.CharField(max_length=15, choices=Kind.choices)
    field = models.CharField(max_length=100, blank=True, null=True)
    field_label = models.CharField(max_length=150, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='facture_activities')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Activité facture'
        verbose_name_plural = 'Activités facture'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['facture', '-created_at'],
                                name='ventes_factact_idx')]

    def __str__(self):
        return f"{self.facture_id} {self.kind} {self.field or ''}".strip()


class ProformaDocument(models.Model):
    """XFAC10 — trace d'une facture PRO-FORMA générée pour un devis.

    Document NON comptabilisé (aucun impact statuts/GL/numérotation des
    vraies factures) : uniquement un rendu PDF filigrané avec sa PROPRE
    séquence ``PF-`` (via ``utils/references.py``), indépendante de celle des
    factures réelles. Ce modèle sert UNIQUEMENT à garantir cette séquence
    sans collision (même mécanisme highest-used+1 que Facture/Devis) et à
    tracer les émissions dans le chatter du devis — il ne devient JAMAIS une
    facture réelle (la conversion reste `generer-facture`, inchangée)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='proforma_documents')
    reference = models.CharField(max_length=50)
    devis = models.ForeignKey(
        'Devis', on_delete=models.CASCADE, related_name='proformas')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='proformas_creees')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Facture pro-forma'
        verbose_name_plural = 'Factures pro-forma'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference


class FactureSource(models.Model):
    """XFAC11 — table de liaison « facture consolidée ↔ document source ».

    Une facture consolidée (`POST factures/consolider/`) regroupe PLUSIEURS
    devis/BC déjà acceptés d'un même client en UNE facture ; ``Facture.devis``
    reste nullable/unique (chaîne historique inchangée) alors que CETTE table
    trace CHAQUE document source consolidé (traçabilité multi-source), avec le
    sous-total HT de ce document dans la facture regroupée (sert au sous-titre
    « Devis DV-… » sur le PDF)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='facture_sources')
    facture = models.ForeignKey(
        'facturation.Facture', on_delete=models.CASCADE, related_name='sources')
    devis = models.ForeignKey(
        'Devis', on_delete=models.PROTECT, related_name='factures_sources')
    sous_total_ht = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = 'Source de facture consolidée'
        verbose_name_plural = 'Sources de facture consolidée'
        unique_together = [('facture', 'devis')]

    def __str__(self):
        return f'{self.facture_id} ← {self.devis.reference}'


class BonCommande(models.Model):
    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        CONFIRME = 'confirme', 'Confirmé'
        LIVRE = 'livre', 'Livré'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='bons_commande',
    )
    reference = models.CharField(max_length=50)
    devis = models.OneToOneField(
        Devis,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bon_commande',
    )
    # U12 — lien DIRECT vers le lead d'origine, snapshoté à la création depuis
    # le devis source (devis.lead). Additif/optionnel : un BC sans lead reste
    # valide, et on ne perd jamais le lien si le devis est supprimé (SET_NULL).
    # Permet « tous les documents d'un lead » sans traverser le devis (qui peut
    # passer à NULL). related_name distinct (`bons_commande_directs`) pour ne pas
    # entrer en conflit avec un futur reverse `bons_commande` côté Lead.
    lead = models.ForeignKey(
        'crm.Lead',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bons_commande_directs',
    )
    client = models.ForeignKey(
        'crm.Client',
        on_delete=models.PROTECT,
        related_name='bons_commande',
    )
    statut = models.CharField(
        max_length=20,
        choices=Statut.choices,
        default=Statut.EN_ATTENTE,
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_livraison_prevue = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True, null=True)
    # ── FG51 — Preuve de livraison (PV / signature) ───────────────────────────
    # Capturée au moment de « marquer livré » : nom du signataire, note libre,
    # horodatage et, optionnellement, une pièce jointe (PV/bon signé) stockée
    # dans MinIO via records.storage. Tout est additif et optionnel : un BC
    # livré sans preuve reste valide (la facturation n'est jamais bloquée), mais
    # `generer-facture`/`creer-facture` renvoie un avertissement doux quand
    # aucune preuve n'existe pour la tranche matériel. Forme du JSON :
    # {signataire, note, file_key, filename, signed_at}.
    pv_livraison = models.JSONField(null=True, blank=True)
    date_livraison_reelle = models.DateField(null=True, blank=True)

    @property
    def has_proof_of_delivery(self):
        """FG51 — vrai si une preuve de livraison (PV/signature) est consignée."""
        pv = self.pv_livraison or {}
        return bool(pv.get('signataire') or pv.get('file_key'))

    def save(self, *args, **kwargs):
        """U12 — snapshote le lead d'origine depuis le devis source à la création.

        Toute voie de création (action `convertir-bc`, services cross-app…)
        hérite ainsi du lien direct sans avoir à le poser à la main. On ne pose
        le lead que s'il n'est pas déjà fixé (jamais d'écrasement) et qu'un
        devis source le porte — comportement historique strictement inchangé
        pour un BC sans devis ou sans lead."""
        if self.lead_id is None:
            # Résolution INLINE (aucun import de services → préserve le contrat
            # import-linter « modèles de domaine découplés »). Un BC porte son
            # devis directement ; on hérite du lead du devis source s'il existe.
            devis = getattr(self, 'devis', None)
            lead = getattr(devis, 'lead', None) if devis is not None else None
            if lead is not None:
                self.lead = lead
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Bon de Commande'
        verbose_name_plural = 'Bons de Commande'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference

    @property
    def reliquat_par_ligne(self):
        """XSAL12 — quantité restant à livrer par ligne de devis source.

        Un BC sans devis (ou sans livraison partielle) renvoie une liste
        vide — comportement historique inchangé (le statut reste piloté par
        `marquer_livre` seul dans ce cas)."""
        if self.devis_id is None:
            return []
        from django.db.models import Sum
        livre_par_ligne = dict(
            LigneLivraisonBC.objects
            .filter(livraison__bon_commande=self)
            .values_list('ligne_devis_id')
            .annotate(total=Sum('quantite_livree'))
        )
        out = []
        for ligne in self.devis.lignes.all():
            livre = livre_par_ligne.get(ligne.id) or 0
            out.append({
                'ligne_devis_id': ligne.id,
                'designation': ligne.designation,
                'quantite_commandee': ligne.quantite,
                'quantite_livree': livre,
                'reliquat': ligne.quantite - livre,
            })
        return out

    @property
    def est_partiellement_livre(self):
        """XSAL12 — vrai si au moins une livraison partielle existe et qu'il
        reste un reliquat (le BC n'est pas encore `livre`)."""
        if self.statut == self.Statut.LIVRE:
            return False
        reliquats = self.reliquat_par_ligne
        if not reliquats:
            return False
        any_livre = any(r['quantite_livree'] > 0 for r in reliquats)
        any_reliquat = any(r['reliquat'] > 0 for r in reliquats)
        return any_livre and any_reliquat


class AffectationPaiement(models.Model):
    """XFAC1 — ventilation d'un paiement (avance/trop-perçu) sur UNE facture.

    Un même ``Paiement`` non affecté peut porter plusieurs lignes
    d'affectation (réparti sur N factures ouvertes du même client). La somme
    des affectations d'un paiement ne peut jamais dépasser son montant (garde
    posée côté service — jamais de sur-affectation)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='affectations_paiement')
    paiement = models.ForeignKey(
        'facturation.Paiement', on_delete=models.CASCADE, related_name='affectations')
    facture = models.ForeignKey(
        'facturation.Facture', on_delete=models.CASCADE, related_name='affectations_paiement')
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    date_affectation = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='affectations_effectuees')

    class Meta:
        verbose_name = 'Affectation de paiement'
        verbose_name_plural = 'Affectations de paiement'
        ordering = ['-date_affectation']

    def __str__(self):
        return f'{self.montant} MAD — {self.paiement_id} → {self.facture.reference}'


class NoteDebit(models.Model):
    """ZFAC4 — note de débit : pendant de l'``Avoir`` qui MAJORE une facture
    déjà émise (surfacturation régularisée, complément non prévu) au lieu de
    la réduire. Miroir structurel d'``Avoir`` (mêmes champs), référence
    préfixée ``ND-`` (jamais ``AVO-``)."""
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EMISE = 'emise', 'Émise'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='notes_debit')
    reference = models.CharField(max_length=50)
    facture = models.ForeignKey(
        'facturation.Facture', on_delete=models.PROTECT, related_name='notes_debit')
    client = models.ForeignKey(
        'crm.Client', on_delete=models.PROTECT, related_name='notes_debit')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    motif = models.TextField(blank=True, default='')
    date_emission = models.DateField(auto_now_add=True)
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2, default=20.00)
    # Montants figés (chemin simple, sans lignes détaillées) — utilisés quand
    # aucune ligne n'est fournie.
    montant_ht = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    montant_tva = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    montant_ttc = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='notes_debit_creees')
    fichier_pdf = models.CharField(max_length=500, blank=True, null=True)

    class Meta:
        verbose_name = 'Note de débit'
        verbose_name_plural = 'Notes de débit'
        ordering = ['-date_emission', '-id']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference

    @property
    def total_ht(self):
        if self.montant_ht is not None:
            return self.montant_ht
        return sum(ligne.total_ht for ligne in self.lignes.all())

    @property
    def total_tva(self):
        if self.montant_tva is not None:
            return self.montant_tva
        from decimal import Decimal
        return sum((b['montant'] for b in self.tva_par_taux), Decimal('0'))

    @property
    def tva_par_taux(self):
        from .selectors import tva_buckets
        frozen = None
        if self.montant_tva is not None:
            frozen = (self.taux_tva, self.total_ht, self.montant_tva)
        return tva_buckets(
            self.lignes.all(), fallback_taux=self.taux_tva, frozen=frozen)

    @property
    def total_ttc(self):
        if self.montant_ttc is not None:
            return self.montant_ttc
        return self.total_ht + self.total_tva


class LigneNoteDebit(models.Model):
    note_debit = models.ForeignKey(
        NoteDebit, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lignes_note_debit')
    designation = models.CharField(max_length=255)
    quantite = models.DecimalField(max_digits=10, decimal_places=2)
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    remise = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    taux_tva = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = 'Ligne de note de débit'
        verbose_name_plural = 'Lignes de note de débit'

    @property
    def total_ht(self):
        return self.quantite * self.prix_unitaire * (1 - self.remise / 100)

    @property
    def taux_tva_effectif(self):
        return (self.taux_tva if self.taux_tva is not None
                else self.note_debit.taux_tva)


class RetenueSubie(models.Model):
    """XFAC4 — Retenue à la source SUBIE par NOUS sur une facture client
    (RAS TVA / RAS honoraires, réforme TVA 2024) : un client (État, grande
    entreprise) retient un pourcentage de notre facture et ne nous verse que le
    net — la facture reste juridiquement soldée (payé + retenue + avoirs =
    TTC) mais on trace la créance d'attestation de retenue à recevoir.

    Miroir de ``compta.RetenueSource`` (FG139 — RAS que NOUS retenons sur nos
    fournisseurs) mais côté RECETTE : ici c'est le CLIENT qui retient sur ce
    qu'il nous doit. Snapshot figé (base/taux/montant) au moment de la saisie.
    """
    class TypeRetenue(models.TextChoices):
        RAS_TVA = 'ras_tva', 'RAS TVA'
        RAS_IS = 'ras_is', 'RAS IS'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='retenues_subies')
    facture = models.ForeignKey(
        'facturation.Facture', on_delete=models.CASCADE, related_name='retenues_subies')
    # Paiement qui a déclenché la constatation de la retenue (le paiement
    # partiel + la retenue soldent ensemble la facture). Optionnel : la
    # retenue peut être saisie avant ou après le paiement lui-même.
    paiement = models.ForeignKey(
        'facturation.Paiement', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='retenues_subies')
    type_retenue = models.CharField(
        max_length=10, choices=TypeRetenue.choices, default=TypeRetenue.RAS_TVA)
    taux = models.DecimalField(max_digits=5, decimal_places=2)
    base = models.DecimalField(max_digits=12, decimal_places=2)
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    attestation_recue = models.BooleanField(default=False)
    attestation_date = models.DateField(null=True, blank=True)
    attestation_fichier = models.CharField(max_length=500, blank=True, null=True)
    note = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='retenues_subies_creees')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Retenue à la source subie'
        verbose_name_plural = 'Retenues à la source subies'
        ordering = ['-date_creation']

    def __str__(self):
        return f'RAS {self.montant} MAD — {self.facture.reference}'


class PromessePaiement(models.Model):
    """XFAC5 — engagement client tracé (« je paie le 15 ») qui SUSPEND les
    relances automatiques de la facture jusqu'à ``date_promise``. Le job beat
    (``scheduled.py relance_reminders``) marque la promesse ``rompue`` si la
    date passe sans encaissement suffisant et reprend les relances avec un
    flag « promesse rompue »."""
    class Statut(models.TextChoices):
        EN_COURS = 'en_cours', 'En cours'
        TENUE = 'tenue', 'Tenue'
        ROMPUE = 'rompue', 'Rompue'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='promesses_paiement')
    facture = models.ForeignKey(
        'facturation.Facture', on_delete=models.CASCADE, related_name='promesses_paiement')
    montant_promis = models.DecimalField(max_digits=12, decimal_places=2)
    date_promise = models.DateField()
    note = models.TextField(blank=True, default='')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.EN_COURS)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='promesses_paiement_creees')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Promesse de paiement'
        verbose_name_plural = 'Promesses de paiement'
        ordering = ['-date_creation']

    def __str__(self):
        return (f'Promesse {self.montant_promis} MAD le {self.date_promise} '
                f'— {self.facture.reference}')


class ParametrageRelanceClient(models.Model):
    """ZFAC8 — réglage PAR CLIENT du responsable de relance + du mode
    (auto/manuel), lu par ``scheduled.relance_reminders``. En mode
    ``manuel``, le cron n'envoie AUCUNE relance automatique pour ce client
    (il apparaît seulement dans la liste manuelle de son responsable).
    Défaut = ``auto`` → comportement historique inchangé pour tout client
    non paramétré (absence de ligne = auto)."""
    class Mode(models.TextChoices):
        AUTO = 'auto', 'Automatique'
        MANUEL = 'manuel', 'Manuel'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='parametrages_relance')
    client = models.OneToOneField(
        'crm.Client', on_delete=models.CASCADE,
        related_name='parametrage_relance')
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='clients_relance_responsable')
    mode = models.CharField(
        max_length=10, choices=Mode.choices, default=Mode.AUTO)
    prochaine_relance_manuelle = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'Paramétrage de relance client'
        verbose_name_plural = 'Paramétrages de relance client'

    def __str__(self):
        return f'{self.client_id} — {self.mode}'


class EmailLog(models.Model):
    """Journal « chatter » des emails sortants ET entrants liés à un client /
    document (devis, facture). Additif, scopé société. C'est la trace
    réutilisée par l'intégration email (N87) et la capture entrante (N88) :
    on consigne ce qui a été envoyé/reçu sur le fil du client/document. La
    société et l'utilisateur sont posés côté serveur, jamais lus du corps de
    la requête.

    Sans clé d'envoi configurée, l'envoi reste un NO-OP (backend console par
    défaut) mais l'entrée EmailLog est tout de même écrite avec
    statut=ENVOYE pour garder la trace lisible côté fil."""
    class Direction(models.TextChoices):
        SORTANT = 'sortant', 'Sortant'
        ENTRANT = 'entrant', 'Entrant'

    class Statut(models.TextChoices):
        ENVOYE = 'envoye', 'Envoyé'
        ECHEC = 'echec', 'Échec'
        RECU = 'recu', 'Reçu'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='email_logs')
    direction = models.CharField(
        max_length=10, choices=Direction.choices, default=Direction.SORTANT)
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.ENVOYE)
    # Cible du fil : client et/ou document. Tous optionnels — un email entrant
    # peut n'être rattaché qu'au client si aucune référence document n'est lue.
    client = models.ForeignKey(
        'crm.Client', on_delete=models.CASCADE, null=True, blank=True,
        related_name='email_logs')
    devis = models.ForeignKey(
        Devis, on_delete=models.CASCADE, null=True, blank=True,
        related_name='email_logs')
    facture = models.ForeignKey(
        'facturation.Facture', on_delete=models.CASCADE, null=True, blank=True,
        related_name='email_logs')
    to_email = models.CharField(max_length=254, blank=True, default='')
    from_email = models.CharField(max_length=254, blank=True, default='')
    sujet = models.CharField(max_length=300, blank=True, default='')
    corps = models.TextField(blank=True, default='')
    # Référence document reconnue dans un message entrant (ex. FAC-…/DEV-…).
    reference = models.CharField(max_length=80, blank=True, default='')
    # Nom de la pièce jointe envoyée (PDF), le cas échéant.
    piece_jointe = models.CharField(max_length=255, blank=True, default='')
    erreur = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='email_logs')

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Email'
        indexes = [
            models.Index(fields=['client', '-created_at'],
                         name='ventes_emaillog_cli_idx'),
            models.Index(fields=['facture', '-created_at'],
                         name='ventes_emaillog_fac_idx'),
        ]

    def __str__(self):
        return f'{self.get_direction_display()} {self.to_email or self.from_email}'


# ── Liens publics tokenisés (Envoyer par WhatsApp) ───────────────────────────
import secrets  # noqa: E402
from datetime import timedelta  # noqa: E402
from django.utils import timezone  # noqa: E402

SHARE_LINK_TTL_DAYS = 30


def _default_share_token():
    return secrets.token_urlsafe(32)


def _default_share_expiry():
    return timezone.now() + timedelta(days=SHARE_LINK_TTL_DAYS)


class ShareLink(models.Model):
    """Lien public, lecture seule, expirant (30 j) vers le PDF CLIENT d'un devis
    ou d'une facture. Jeton long et imprévisible. Aucun login pour le client,
    aucune autre donnée accessible, jamais de prix d'achat ni de marge (le PDF
    client ne les contient pas)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='share_links')
    token = models.CharField(
        max_length=64, unique=True, default=_default_share_token,
        editable=False)
    devis = models.ForeignKey(
        Devis, on_delete=models.CASCADE, null=True, blank=True,
        related_name='share_links')
    facture = models.ForeignKey(
        'facturation.Facture', on_delete=models.CASCADE, null=True, blank=True,
        related_name='share_links')
    # QS3 — lien tokenisé vers le PDF d'un Bon de Commande FOURNISSEUR (stock).
    # String-FK (ventes → stock) : ventes n'importe pas les modèles de stock.
    # Additif/nullable : les liens existants (devis/facture) sont inchangés. Ce
    # PDF montre légitimement les PRIX D'ACHAT au FOURNISSEUR — le jeton reste
    # imprévisible + expirant, et le lien n'est JAMAIS exposé dans l'UI client.
    bon_commande_fournisseur = models.ForeignKey(
        'achats.BonCommandeFournisseur', on_delete=models.CASCADE,
        null=True, blank=True, related_name='share_links')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_default_share_expiry)
    # QJ1 — Suivi d'ouverture : première et dernière consultation + compteur.
    # Tous nullable/default=0 → additive, aucune valeur sur les liens existants.
    first_viewed_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Première consultation')
    last_viewed_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Dernière consultation')
    view_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Nombre de consultations')
    # ── XSAL16 — Analytics d'engagement par section de la proposition ──
    # JSON additif, agrégé par section : {"prix": {"seconds": 120, "hits": 3},
    # "etude": {...}, ...}. Alimenté par des beacons POST côté proposition web
    # (WEB_PLAN WJ — moitié web hors périmètre ERP). Vide/absent = comportement
    # QJ1 inchangé (aucun affichage supplémentaire).
    engagement = models.JSONField(null=True, blank=True)
    # Horodatage du premier engagement PROFOND (seuil dépassé sur au moins une
    # section) — sert à ne loguer QU'UNE FOIS la note chatter « a commencé à
    # lire en détail ».
    deep_engagement_logged_at = models.DateTimeField(null=True, blank=True)
    # ── QX30be — moteur de relance déclenchée par le COMPORTEMENT ──
    # Liste des déclencheurs d'engagement déjà notifiés (idempotence) :
    # ex. ["not_opened_24h", "opened_not_signed_48h", "reopened_3x"]. Additif/
    # nullable → aucun lien existant n'en porte (comportement inchangé).
    engagement_triggers_fired = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['token'])]

    def __str__(self):
        if self.devis_id:
            cible = 'devis'
        elif self.facture_id:
            cible = 'facture'
        elif self.bon_commande_fournisseur_id:
            cible = 'bcf'
        else:
            cible = '?'
        return f'ShareLink {self.token[:8]}… ({cible})'

    @property
    def is_valid(self):
        return self.expires_at > timezone.now()

    @property
    def engagement_summary(self):
        """XSAL16 — résumé lisible par section : « a passé 2 min sur le prix,
        n'a pas ouvert l'étude ». Vide sans beacon (comportement QJ1
        inchangé, aucune donnée personnelle stockée — juste des sections/
        durées)."""
        data = self.engagement or {}
        return {
            section: {
                'seconds': int(v.get('seconds', 0) or 0),
                'hits': int(v.get('hits', 0) or 0),
            }
            for section, v in data.items()
        }

    @classmethod
    def for_devis(cls, devis):
        """Réutilise un lien encore valide pour ce devis, sinon en crée un."""
        link = cls.objects.filter(
            devis=devis, expires_at__gt=timezone.now()
        ).order_by('-expires_at').first()
        return link or cls.objects.create(company=devis.company, devis=devis)

    @classmethod
    def for_facture(cls, facture):
        link = cls.objects.filter(
            facture=facture, expires_at__gt=timezone.now()
        ).order_by('-expires_at').first()
        return link or cls.objects.create(
            company=facture.company, facture=facture)

    @classmethod
    def for_bon_commande_fournisseur(cls, bcf):
        """QS3 — Réutilise (ou crée) un lien tokenisé vers le PDF d'un BCF.

        La société vient du BCF (jamais du corps de requête). Le lien est
        destiné au FOURNISSEUR (il peut légitimement voir les prix d'achat),
        mais reste imprévisible + expirant et n'est jamais surfacé dans l'UI
        client. ``bcf`` peut être l'objet ou un id."""
        bcf_id = getattr(bcf, 'pk', bcf)
        company = getattr(bcf, 'company', None)
        link = cls.objects.filter(
            bon_commande_fournisseur_id=bcf_id, expires_at__gt=timezone.now()
        ).order_by('-expires_at').first()
        if link is not None:
            return link
        return cls.objects.create(
            company=company, bon_commande_fournisseur_id=bcf_id)


PAYMENT_LINK_TTL_DAYS = 30


def _default_payment_token():
    return secrets.token_urlsafe(32)


def _default_payment_expiry():
    return timezone.now() + timedelta(days=PAYMENT_LINK_TTL_DAYS)


class PaymentLink(models.Model):
    """FG53 — lien « Payer en ligne » d'une facture.

    Scaffolding swappable (cf. monitoring/providers) : un fournisseur de
    paiement est sélectionné par clé ; le DÉFAUT est NoOp (« manuel »), sans
    dépendance ni appel réseau ni coût. Le lien public expose le minimum (montant
    dû, référence facture) et un webhook idempotent enregistre un ``Paiement``
    quand le fournisseur confirme l'encaissement. Tant qu'aucun fournisseur réel
    n'est configuré, le lien reste un squelette inerte : aucune passerelle live
    n'est câblée ici.

    Le jeton est long/imprévisible/expirant (30 j), comme ShareLink. Aucune
    donnée interne (prix d'achat/marge) n'est jamais exposée."""

    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        PAYE = 'paye', 'Payé'
        EXPIRE = 'expire', 'Expiré'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='payment_links')
    facture = models.ForeignKey(
        'facturation.Facture', on_delete=models.CASCADE, related_name='payment_links')
    token = models.CharField(
        max_length=64, unique=True, default=_default_payment_token,
        editable=False)
    # Clé du fournisseur (registre payments.providers). 'noop' = défaut inerte.
    provider = models.CharField(max_length=40, default='noop')
    # Montant figé à la création du lien (= reste à payer au moment T).
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE)
    # Référence retournée par le fournisseur (idempotence du webhook).
    provider_ref = models.CharField(max_length=200, blank=True, default='')
    paiement = models.ForeignKey(
        'facturation.Paiement', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='payment_links')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_default_payment_expiry)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Lien de paiement'
        verbose_name_plural = 'Liens de paiement'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['token'])]

    def __str__(self):
        return f'PaymentLink {self.token[:8]}… ({self.facture.reference})'

    @property
    def is_valid(self):
        return (self.statut == self.Statut.EN_ATTENTE
                and self.expires_at > timezone.now())


import hashlib  # noqa: E402


class DevisSignature(models.Model):
    """QJ10 — Enregistrement IMMUABLE de signature électronique (loi 53-05).

    Créé UNE SEULE FOIS au moment de l'acceptation de la proposition.
    Ne peut jamais être modifié (pas de méthode save() de mise à jour ;
    l'idempotence est portée par le service qui interdit un deuxième enregistrement
    sur un devis déjà signé). Scopé société, jamais de prix d'achat/marge exposé.
    Champs :
    - signataire_nom   : nom saisi par le client (texte libre, ≤150 chars)
    - consentement_explicite : le client a coché « J'accepte » (True requis)
    - ip_address       : IP du navigateur client à l'instant de la soumission
    - user_agent       : User-Agent HTTP du navigateur (≤512 chars, tronqué)
    - content_hash     : SHA-256 hex du payload canonique du devis (données
                         commerciales : référence, lignes, totaux, client) — le
                         moteur ne rend qu'ici la proposition ; ce hash est le
                         sceau du document signé, sans aucune donnée interne
                         (prix d'achat / marge) — CONFORME règle #4.
    - signed_at        : horodatage UTC de la signature
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='devis_signatures',
    )
    devis = models.OneToOneField(
        Devis,
        on_delete=models.CASCADE,
        related_name='signature',
    )
    signataire_nom = models.CharField(max_length=150)
    consentement_explicite = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(
        null=True, blank=True,
        verbose_name='Adresse IP',
    )
    user_agent = models.CharField(
        max_length=512, blank=True, default='',
        verbose_name='User-Agent',
    )
    # SHA-256 hex du payload canonique (référence + lignes + totaux + client).
    # Ne contient JAMAIS prix_achat ni marge.
    content_hash = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Hash du contenu signé (SHA-256)',
    )
    signed_at = models.DateTimeField(
        verbose_name='Horodatage de signature',
    )
    # QJ22 — Artefact PDF signé (clé MinIO du PDF de la proposition acceptée).
    # Stocké une fois à l'acceptation via le moteur premium existant. Nullable :
    # les signatures antérieures à QJ22 n'ont pas de PDF stocké (valeur None →
    # comportement pré-QJ22 strictement inchangé). Jamais de prix_achat/marge.
    signed_pdf_key = models.CharField(
        max_length=500, blank=True, null=True,
        verbose_name='Clé MinIO du PDF signé',
    )

    # ── QX9 — preuve de signature électronique réelle (loi 43-20) ──
    # Champs ADDITIFS/nullable : les signatures antérieures n'en portent aucun
    # (comportement inchangé). Jamais de prix_achat/marge. ``signature_image``
    # = data-URL PNG du tracé manuscrit (ou clé MinIO) ; ``consent_esign`` = le
    # client a explicitement coché « je consens à signer électroniquement » ;
    # ``signed_at_client`` = horodatage navigateur (distinct de ``signed_at``
    # serveur, pour l'audit) ; ``on_behalf_of`` = précision facultative WJ87.
    signature_image = models.TextField(
        blank=True, default='',
        verbose_name='Image de la signature (data-URL / clé MinIO)')
    consent_esign = models.BooleanField(
        default=False,
        verbose_name='Consentement explicite e-signature (43-20)')
    signed_at_client = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Horodatage client de la signature')
    on_behalf_of = models.CharField(
        max_length=150, blank=True, default='',
        verbose_name='Signe au nom de (facultatif)')

    class Meta:
        verbose_name = 'Signature électronique'
        verbose_name_plural = 'Signatures électroniques'
        ordering = ['-signed_at']
        indexes = [
            models.Index(fields=['devis'],
                         name='ventes_devissig_dev_idx'),
        ]

    def __str__(self):
        return f'Signature {self.devis_id} — {self.signataire_nom}'

    @staticmethod
    def compute_content_hash(devis):
        """SHA-256 du payload canonique du devis (sans aucune donnée interne).

        Le hash couvre : référence, client (nom/email), date_creation,
        lignes (designation/qte/pu_ht/remise), taux_tva, remise_globale.
        JAMAIS prix_achat ni marge. Déterministe et reproductible.
        """
        client = getattr(devis, 'client', None)
        client_str = ''
        if client is not None:
            client_str = f'{getattr(client, "nom", "")}|{getattr(client, "email", "")}'
        lignes = list(devis.lignes.order_by('id').values(
            'designation', 'quantite', 'prix_unitaire', 'remise'))
        lignes_str = '|'.join(
            f"{lg['designation']}:{lg['quantite']}:{lg['prix_unitaire']}:{lg['remise']}"
            for lg in lignes
        )
        payload = (
            f"ref={devis.reference}|"
            f"client={client_str}|"
            f"created={devis.date_creation}|"
            f"tva={devis.taux_tva}|"
            f"remise={devis.remise_globale}|"
            f"lignes={lignes_str}"
        )
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()


# ── QJ16 — Reusable quote presets ────────────────────────────────────────────

class DevisPreset(models.Model):
    """A company-scoped saved quote configuration (« modèle de devis »).

    A preset captures the line configuration of an existing Devis so a user
    can apply it to a new quote in one click instead of rebuilding from the
    catalogue.  It stores lines as a JSON snapshot (never live references) so
    the preset remains stable after the source devis is edited.

    Multi-tenancy: ``company`` is always forced server-side; never accepted
    from the request body.  Querysets are always filtered by
    ``request.user.company``.

    Price-less products are excluded at apply-time (same guard as the
    auto-fill / build_devis_from_layout service): a preset line whose product
    no longer carries a sell price is skipped, not applied.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='devis_presets',
        verbose_name='Société',
    )
    nom = models.CharField(
        max_length=150,
        verbose_name='Nom du modèle',
        help_text='Ex. « Standard 6 kWc résidentiel ».',
    )
    description = models.TextField(
        blank=True, default='',
        verbose_name='Description',
        help_text='Note libre sur ce modèle (optionnel).',
    )
    mode_installation = models.CharField(
        max_length=20,
        choices=Devis.ModeInstallation.choices,
        blank=True, null=True,
        verbose_name='Mode d\'installation',
    )
    taux_tva = models.DecimalField(
        max_digits=5, decimal_places=2, default=20,
        verbose_name='Taux TVA (%)',
    )
    remise_globale = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='Remise globale (%)',
    )
    # Snapshot of lines: list of
    # {produit_id, designation, quantite, prix_unitaire, remise, taux_tva}.
    # produit_id is nullable in the snapshot (product may have been deleted).
    lignes_snapshot = models.JSONField(
        verbose_name='Lignes (snapshot)',
        help_text='Snapshot JSON des lignes du devis source.',
    )
    # etude_params snapshot — preserves pompage / industrial study data
    # so presets for those modes carry the right sizing defaults.
    etude_params_snapshot = models.JSONField(
        blank=True, null=True,
        verbose_name='Paramètres étude (snapshot)',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='devis_presets_crees',
        verbose_name='Créé par',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Modèle de devis'
        verbose_name_plural = 'Modèles de devis'
        ordering = ['nom']
        indexes = [
            models.Index(fields=['company', 'nom'], name='ventes_preset_co_nom_idx'),
        ]

    def __str__(self):
        return f'{self.nom} ({getattr(self.company, "nom", self.company_id)})'


# ── QJ4 — Suivi automatique de devis envoyé (relance cadencée) ───────────────

# Cadence par défaut : j+2, j+5, j+10 après date_envoi.
# Modifiable via le paramètre DEVIS_NUDGE_DAYS dans les settings Django
# (liste d'entiers). La cadence s'arrête dès que le devis passe « accepté »
# ou « refusé ».
DEVIS_NUDGE_DEFAULT_DAYS = [2, 5, 10]


class DevisNudgeLog(models.Model):
    """Trace d'une relance automatique envoyée au vendeur pour un devis.

    Un enregistrement par (devis, niveau) garantit qu'un niveau ne se déclenche
    jamais deux fois (idempotence). La relance est adressée AU VENDEUR
    (created_by), pas au client — soit un draft wa.me, soit un email SendGrid
    si configuré. Scopé société (multi-tenant).

    Champs :
    - devis       : FK vers le Devis concerné (scopé société)
    - niveau      : indice 0-based du jour de relance (0 = j+2, 1 = j+5, 2 = j+10)
    - jours       : nombre de jours après date_envoi de ce niveau (ex. 2)
    - canal       : 'email' | 'wa_draft' (indique comment la relance a été traitée)
    - created_at  : horodatage UTC de l'envoi
    """
    class Canal(models.TextChoices):
        EMAIL = 'email', 'Email'
        WA_DRAFT = 'wa_draft', 'WhatsApp draft (wa.me)'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='devis_nudge_logs',
    )
    devis = models.ForeignKey(
        Devis,
        on_delete=models.CASCADE,
        related_name='nudge_logs',
    )
    niveau = models.PositiveSmallIntegerField(
        verbose_name='Niveau (indice 0-based)',
        help_text='0 = premier palier, 1 = deuxième, etc.',
    )
    jours = models.PositiveSmallIntegerField(
        verbose_name='Jours après envoi',
        help_text='Nombre de jours après date_envoi de ce palier.',
    )
    canal = models.CharField(
        max_length=10,
        choices=Canal.choices,
        default=Canal.WA_DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Relance automatique devis'
        verbose_name_plural = 'Relances automatiques devis'
        ordering = ['-created_at']
        unique_together = [('devis', 'niveau')]
        indexes = [
            models.Index(fields=['devis', 'niveau'], name='ventes_nudge_dev_niv_idx'),
        ]

    def __str__(self):
        return (
            f'NudgeLog devis={self.devis_id} niveau={self.niveau}'
            f' j+{self.jours} [{self.canal}]'
        )


# ── FG245 — Éditeur de calepinage toiture (placement panneaux) ───────────────


class RoofLayout(models.Model):
    """Calepinage toiture : placement réaliste des modules sur un pan de toit.

    Persiste une conception de calepinage attachée à un Devis : la surface
    utile du toit, les retraits de sécurité (marges sur les bords), la taille
    d'un module et la liste des panneaux placés (position + orientation). Le
    nombre réaliste de panneaux (``panel_count``) est calculé côté serveur à
    partir de cette géométrie, jamais accepté tel quel depuis la requête, pour
    figer un compte cohérent avec la surface disponible.

    Multi-tenancy : ``company`` est toujours forcée côté serveur (depuis le
    devis lié ou l'utilisateur) ; jamais lue du corps de la requête. Les
    querysets sont toujours filtrés par ``request.user.company``.

    RULE #4 / status preservation : ce modèle ne RENDU rien et ne change aucun
    statut de devis — il ne fait que persister une géométrie de calepinage,
    couche additive et séparée du PDF premium (`quote_engine/`) et de
    `/proposal`.
    """

    class Orientation(models.TextChoices):
        PORTRAIT = 'portrait', 'Portrait'
        PAYSAGE = 'paysage', 'Paysage'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='ventes_roof_layouts',
        verbose_name='Société',
    )
    # Un calepinage est rattaché à un devis (le devis porte déjà la société).
    # SET_NULL pour qu'un calepinage survive à la suppression d'un brouillon.
    devis = models.ForeignKey(
        'ventes.Devis',
        on_delete=models.CASCADE,
        related_name='ventes_roof_layouts',
        null=True, blank=True,
        verbose_name='Devis',
    )
    nom = models.CharField(
        max_length=150, blank=True, default='',
        verbose_name='Nom du calepinage',
        help_text='Ex. « Pan sud — toiture tôle ».',
    )
    # ── Géométrie du pan de toit (mètres) ──
    largeur_m = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        verbose_name='Largeur du pan (m)',
    )
    hauteur_m = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        verbose_name='Hauteur / longueur du pan (m)',
    )
    # Retrait de sécurité appliqué sur chaque bord du pan (marge incendie /
    # accès). Réduit la surface réellement calepinable.
    retrait_m = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        verbose_name='Retrait de sécurité (m)',
        help_text='Marge libre sur chaque bord du pan.',
    )
    # ── Dimensions d'un module (mètres) ──
    module_largeur_m = models.DecimalField(
        max_digits=6, decimal_places=3, default=1.134,
        verbose_name='Largeur module (m)',
    )
    module_hauteur_m = models.DecimalField(
        max_digits=6, decimal_places=3, default=2.278,
        verbose_name='Hauteur module (m)',
    )
    # Jeu (espacement) entre deux modules adjacents.
    espacement_m = models.DecimalField(
        max_digits=6, decimal_places=3, default=0.02,
        verbose_name='Espacement entre modules (m)',
    )
    orientation = models.CharField(
        max_length=10, choices=Orientation.choices,
        default=Orientation.PORTRAIT,
        verbose_name='Orientation des modules',
    )
    puissance_module_wc = models.PositiveIntegerField(
        default=0,
        verbose_name='Puissance unitaire module (Wc)',
        help_text='Pour déduire le kWc total du calepinage (0 = inconnu).',
    )
    # Liste des panneaux placés : [{x, y, w, h, orientation}], coordonnées en
    # mètres relatives au coin du pan. Posée par l'éditeur web et/ou par le
    # calcul auto. Reste cohérente avec ``panel_count`` recalculé côté serveur.
    panels = models.JSONField(
        default=list, blank=True,
        verbose_name='Panneaux placés',
    )
    # Nombre réaliste de panneaux — TOUJOURS recalculé côté serveur depuis la
    # géométrie ; jamais accepté du corps de la requête (lecture seule API).
    panel_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Nombre de panneaux',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ventes_roof_layouts_crees',
        verbose_name='Créé par',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Calepinage toiture'
        verbose_name_plural = 'Calepinages toiture'
        ordering = ['-updated_at']
        indexes = [
            models.Index(
                fields=['company', 'devis'],
                name='ventes_roof_co_dev_idx',
            ),
        ]

    def __str__(self):
        return f'Calepinage #{self.pk} ({self.panel_count} modules)'

    # ── Calcul du calepinage ──────────────────────────────────────────────

    def compute_grid(self):
        """Compte réaliste de modules tenant sur le pan, retraits déduits.

        Calepinage rectangulaire simple : la surface utile (pan moins retrait
        sur chaque bord) est pavée par des modules dans l'orientation choisie,
        en tenant compte de l'espacement entre modules. Renvoie un dict
        {cols, rows, count} ; ne fait AUCUN effet de bord (n'écrit pas le
        modèle). Tout ≤ 0 → zéro module (jamais d'erreur).
        """
        usable_w = float(self.largeur_m) - 2 * float(self.retrait_m)
        usable_h = float(self.hauteur_m) - 2 * float(self.retrait_m)
        if usable_w <= 0 or usable_h <= 0:
            return {'cols': 0, 'rows': 0, 'count': 0}

        if self.orientation == self.Orientation.PAYSAGE:
            mod_w = float(self.module_hauteur_m)
            mod_h = float(self.module_largeur_m)
        else:
            mod_w = float(self.module_largeur_m)
            mod_h = float(self.module_hauteur_m)
        if mod_w <= 0 or mod_h <= 0:
            return {'cols': 0, 'rows': 0, 'count': 0}

        gap = max(0.0, float(self.espacement_m))
        # N modules sur un axe : N*mod + (N-1)*gap <= usable
        #  => N <= (usable + gap) / (mod + gap)
        cols = int((usable_w + gap) // (mod_w + gap))
        rows = int((usable_h + gap) // (mod_h + gap))
        cols = max(0, cols)
        rows = max(0, rows)
        return {'cols': cols, 'rows': rows, 'count': cols * rows}

    def build_panels(self):
        """Génère la liste des panneaux placés depuis la grille calculée.

        Coordonnées en mètres, origine au coin retrait du pan. Chaque panneau :
        {x, y, w, h, orientation}. Pur calcul, aucun effet de bord.
        """
        grid = self.compute_grid()
        if self.orientation == self.Orientation.PAYSAGE:
            mod_w = float(self.module_hauteur_m)
            mod_h = float(self.module_largeur_m)
        else:
            mod_w = float(self.module_largeur_m)
            mod_h = float(self.module_hauteur_m)
        gap = max(0.0, float(self.espacement_m))
        margin = float(self.retrait_m)
        panels = []
        for r in range(grid['rows']):
            for c in range(grid['cols']):
                panels.append({
                    'x': round(margin + c * (mod_w + gap), 3),
                    'y': round(margin + r * (mod_h + gap), 3),
                    'w': round(mod_w, 3),
                    'h': round(mod_h, 3),
                    'orientation': self.orientation,
                })
        return panels

    def recompute(self, rebuild_panels=True):
        """Recalcule ``panel_count`` (et optionnellement ``panels``) en place.

        Si ``panels`` a été fourni explicitement (placement manuel par
        l'éditeur), on respecte ce placement : le compte est alors la longueur
        de la liste fournie, pas la grille. Sinon, on dérive panneaux + compte
        de la géométrie. N'enregistre PAS (l'appelant fait .save()).
        """
        if self.panels and not rebuild_panels:
            self.panel_count = len(self.panels)
            return self.panel_count
        grid = self.compute_grid()
        if rebuild_panels:
            self.panels = self.build_panels()
        self.panel_count = grid['count']
        return self.panel_count

    @property
    def puissance_kwc(self):
        """kWc total déduit du compte de panneaux × puissance unitaire."""
        if not self.puissance_module_wc:
            return None
        return round(self.panel_count * self.puissance_module_wc / 1000.0, 3)


class FicheTechnique(models.Model):
    """FG254 / DC35 — fiche technique normalisée d'un module ou onduleur.

    Bibliothèque de fiches techniques (datasheets) rattachées à un produit du
    catalogue (``stock.Produit`` via FK chaîne, jamais d'import du modèle stock
    — couche découplée M1). Cette fiche NE RE-STOCKE PAS les attributs déjà
    portés par ``Produit`` (marque, description, garantie, courbe de pompe…) :
    elle ne porte que les PARAMÈTRES ÉLECTRIQUES NORMALISÉS utiles au
    dimensionnement (Pmax/Voc/Isc + coefficient de température) et, optionnel,
    une référence vers le PDF datasheet constructeur.

    Multi-tenancy : ``company`` toujours forcée côté serveur (depuis le produit
    lié ou l'utilisateur), jamais lue du corps. Querysets filtrés par société.

    Couche additive séparée du PDF premium (`quote_engine/`) et de `/proposal` ;
    ne change aucun statut de devis (RULE #4). Aucun prix / prix d'achat / marge
    n'est porté ici.
    """

    class TypeFiche(models.TextChoices):
        PANNEAU = 'panneau', 'Module PV (panneau)'
        ONDULEUR = 'onduleur', 'Onduleur'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='ventes_fiches_techniques',
        verbose_name='Société',
    )
    # Un produit du catalogue porte au plus UNE fiche normalisée par société.
    produit = models.ForeignKey(
        'stock.Produit',
        on_delete=models.CASCADE,
        related_name='fiches_techniques',
        verbose_name='Produit',
    )
    type_fiche = models.CharField(
        max_length=10, choices=TypeFiche.choices,
        default=TypeFiche.PANNEAU,
        verbose_name='Type de fiche',
    )
    # ── Paramètres électriques normalisés (STC) ──
    # Panneau : pmax = puissance crête (Wc) ; onduleur : pmax = puissance AC (W).
    pmax_w = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Pmax (W)',
        help_text='Panneau : puissance crête Wc ; onduleur : puissance AC W.',
    )
    voc_v = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Voc (V)', help_text='Tension circuit ouvert (STC).',
    )
    isc_a = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Isc (A)', help_text='Courant de court-circuit (STC).',
    )
    vmp_v = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Vmp (V)', help_text='Tension au point de puissance max.',
    )
    imp_a = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Imp (A)', help_text='Courant au point de puissance max.',
    )
    # Coefficient de température du Voc (%/°C), typiquement négatif.
    coef_temp_voc = models.DecimalField(
        max_digits=6, decimal_places=4, null=True, blank=True,
        verbose_name='Coef. température Voc (%/°C)',
    )
    # Datasheet PDF constructeur (chemin/clé de stockage, comme Devis.fichier_pdf).
    datasheet_pdf = models.CharField(
        max_length=500, blank=True, null=True,
        verbose_name='Datasheet PDF',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='fiches_techniques_creees',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Fiche technique'
        verbose_name_plural = 'Fiches techniques'
        # Une seule fiche normalisée par produit et par société.
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'produit'],
                name='uniq_fiche_company_produit'),
        ]
        indexes = [
            models.Index(fields=['company', 'type_fiche'],
                         name='ix_fiche_comp_type'),
        ]

    def __str__(self):
        return f'Fiche {self.type_fiche} — produit {self.produit_id}'


# FG268-FG271 — dossier réglementaire de raccordement (modèles déportés dans
# models_regulatory.py pour garder ce module lisible ; ré-exportés ici pour que
# Django les découvre et que `from apps.ventes.models import …` fonctionne).
from .models_regulatory import (  # noqa: E402,F401
    RegulatoryDossier,
    DossierChecklistItem,
    DossierExchange,
    SubventionDossier,
    Regularisation8221,
)

# FG274-FG275 — mise en service & recette IEC 62446 (modèles déportés dans
# models_commissioning.py).
from .models_commissioning import (  # noqa: E402,F401
    CommissioningTest,
    IVCurveCapture,
    AsBuiltPack,                # FG276
    AttestationConformite,      # FG277
    TestPerformanceReception,   # FG278
    AttestationRE,              # FG287
)


# ── XFSM19 — Rapprochement des encaissements terrain par technicien ─────────
# FG124 (compta.Caisse/MouvementCaisse) couvre les DÉPENSES de caisse ; rien
# ne réconcilie les espèces/chèques COLLECTÉS SUR LE TERRAIN par un
# technicien contre les factures — critique dans le résidentiel marocain
# cash. Les Paiement lus/rapprochés ici vivent DÉJÀ dans ventes (même app,
# import direct) : aucune frontière cross-app n'est franchie par ce modèle.
class RemiseEncaissement(models.Model):
    """Déclaration + clôture d'une collecte d'encaissements terrain.

    Le technicien déclare sa collecte du jour (des ``Paiement`` déjà
    enregistrés, mode espèces/chèque) ; le responsable la clôture avec un
    bordereau PDF. ``montant_declare`` vs la somme des lignes donne l'écart —
    jamais silencieux (alerté si ≠ 0)."""
    class Statut(models.TextChoices):
        OUVERTE = 'ouverte', 'Ouverte'
        CLOTUREE = 'cloturee', 'Clôturée'
        VALIDEE = 'validee', 'Validée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='remises_encaissement')
    technicien = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='remises_encaissement')
    reference = models.CharField(max_length=50, blank=True, default='')
    date_collecte = models.DateField()
    montant_declare = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text=(
            'Montant total déclaré par le technicien pour cette '
            'collecte (avant rapprochement des lignes).'))
    statut = models.CharField(
        max_length=15, choices=Statut.choices, default=Statut.OUVERTE)
    note = models.TextField(blank=True, default='')
    fichier_pdf = models.CharField(max_length=500, blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='remises_encaissement_creees')
    date_creation = models.DateTimeField(auto_now_add=True)
    cloture_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='remises_encaissement_cloturees')
    date_cloture = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Remise d\'encaissement terrain'
        verbose_name_plural = 'Remises d\'encaissement terrain'
        ordering = ['-date_collecte', '-id']

    def __str__(self):
        return f'Remise {self.reference or self.id} — {self.technicien}'

    @property
    def montant_lignes(self):
        from decimal import Decimal
        return sum(
            (ligne.paiement.montant for ligne in self.lignes.select_related(
                'paiement').all()), Decimal('0'))

    @property
    def ecart(self):
        return self.montant_declare - self.montant_lignes


class LigneRemiseEncaissement(models.Model):
    """Une ligne = un ``Paiement`` (espèces/chèque) rattaché à cette remise.

    Une fois la remise clôturée, ses lignes sont VERROUILLÉES (aucune
    modification/suppression — appliqué côté service)."""
    remise = models.ForeignKey(
        RemiseEncaissement, on_delete=models.CASCADE, related_name='lignes')
    paiement = models.ForeignKey(
        'facturation.Paiement', on_delete=models.PROTECT,
        related_name='lignes_remise_encaissement')

    class Meta:
        verbose_name = 'Ligne de remise d\'encaissement'
        verbose_name_plural = 'Lignes de remise d\'encaissement'
        unique_together = [('remise', 'paiement')]

    def __str__(self):
        return f'{self.remise_id} — paiement {self.paiement_id}'


# ── XCTR22 — Mandat de paiement récurrent (tokenisation carte) ──────────────
# Key-gated OFF par défaut : tant qu'aucun mandat actif n'existe pour un
# client (le cas par défaut, aucun fournisseur de tokenisation n'étant câblé),
# rien ne change au cycle de facturation récurrente existant (XCTR5/XCTR20).
class MandatPaiement(models.Model):
    """Mandat de prélèvement carte (tokenisation), proposé depuis le portail
    client (XCTR14). AUCUN PAN n'est jamais stocké — seul un token OPAQUE du
    fournisseur (+ 4 derniers chiffres/expiration pour l'affichage)."""
    class Statut(models.TextChoices):
        ACTIF = 'actif', 'Actif'
        EXPIRE = 'expire', 'Expiré'
        REVOQUE = 'revoque', 'Révoqué'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='mandats_paiement')
    client = models.ForeignKey(
        'crm.Client', on_delete=models.PROTECT,
        related_name='mandats_paiement')
    provider = models.CharField(max_length=40, default='noop')
    # Token OPAQUE renvoyé par le fournisseur — jamais un PAN.
    token = models.CharField(max_length=200, blank=True, default='')
    derniers_chiffres = models.CharField(max_length=4, blank=True, default='')
    expiration_mois = models.CharField(
        max_length=7, blank=True, default='',
        help_text='MM/AAAA, affichage seulement.')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.ACTIF)
    # Loi 09-08 — consentement horodaté explicite du client à la tokenisation.
    consentement_horodate = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Mandat de paiement récurrent'
        verbose_name_plural = 'Mandats de paiement récurrent'
        ordering = ['-created_at']

    def __str__(self):
        return f'Mandat {self.client_id} ({self.get_statut_display()})'

    @property
    def is_actif(self):
        return self.statut == self.Statut.ACTIF and bool(self.token)


class TentativeDebitMandat(models.Model):
    """XCTR22 — file d'exceptions/dunning du débit automatique par mandat.

    Une ligne par TENTATIVE de débit (succès ou échec) sur une période de
    facturation donnée — garde anti double-débit : jamais deux débits
    RÉUSSIS pour le même ``(mandat, periode)``."""
    class Statut(models.TextChoices):
        REUSSI = 'reussi', 'Réussi'
        ECHEC = 'echec', 'Échec'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='tentatives_debit_mandat')
    mandat = models.ForeignKey(
        MandatPaiement, on_delete=models.CASCADE,
        related_name='tentatives')
    periode = models.CharField(max_length=20)
    statut = models.CharField(max_length=10, choices=Statut.choices)
    motif_echec = models.CharField(max_length=255, blank=True, default='')
    paiement = models.ForeignKey(
        'facturation.Paiement', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tentatives_debit_mandat')
    date_tentative = models.DateTimeField(auto_now_add=True)
    prochaine_retentative = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'Tentative de débit (mandat)'
        verbose_name_plural = 'Tentatives de débit (mandat)'
        ordering = ['-date_tentative']

    def __str__(self):
        return f'{self.mandat_id} / {self.periode} — {self.statut}'


class ListePrix(models.Model):
    """XSAL1 — Liste de prix clients (détail / revendeur / export).

    Un « prix négocié client » = une liste dédiée assignée à ce client via
    ``crm.Client.liste_prix`` (string-FK additive). Le prix affiché reste
    toujours HT/TTC selon le mode du générateur — cette liste ne porte que le
    prix unitaire choisi par le vendeur, jamais ``prix_achat``."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='listes_prix')
    nom = models.CharField(max_length=150)
    devise = models.CharField(max_length=10, default='MAD')
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Liste de prix'
        verbose_name_plural = 'Listes de prix'
        ordering = ['-created_at']

    def __str__(self):
        return self.nom

    @property
    def est_active(self):
        """Vrai si la liste n'est pas archivée et est dans sa fenêtre de
        validité (bornes optionnelles, ouvertes si non renseignées)."""
        if self.archived:
            return False
        today = timezone.now().date()
        if self.date_debut and today < self.date_debut:
            return False
        if self.date_fin and today > self.date_fin:
            return False
        return True


class LignePrixListe(models.Model):
    """XSAL1 — Prix unitaire d'un produit dans une liste de prix.

    ``produit`` est une string-FK vers ``stock.Produit`` (M3 : aucune
    liaison directe entre modèles de domaine). Unique (liste, produit) :
    un produit n'a qu'un seul prix par liste."""
    liste = models.ForeignKey(
        ListePrix, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,
        related_name='lignes_liste_prix')
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'Ligne de liste de prix'
        verbose_name_plural = 'Lignes de liste de prix'
        unique_together = [('liste', 'produit')]

    def __str__(self):
        return f'{self.liste_id} / produit {self.produit_id}'


class RegleListePrix(models.Model):
    """XSAL2 — Règle de prix / palier de quantité sur une liste de prix.

    Portée : produit précis (``produit``), catégorie (``categorie_nom``,
    string-ref stock — jamais d'import de ``stock.models``), marque
    (``marque``, string libre — miroir de ``Produit.marque``) ou tout le
    catalogue (aucune portée renseignée). ``prix_applicable()`` retient la
    règle la plus spécifique satisfaite par la quantité (priorité décroissante
    : produit > catégorie > marque > catalogue, puis ``priorite`` explicite,
    puis palier le plus élevé atteint). Aucune règle ne touche
    ``prix_achat``."""
    class TypeRegle(models.TextChoices):
        PRIX_FIXE = 'prix_fixe', 'Prix fixe'
        REMISE_PCT = 'remise_pct', 'Remise %'
        FORMULE_SUR_PRIX_VENTE = 'formule_sur_prix_vente', 'Formule sur prix de vente'

    liste = models.ForeignKey(
        ListePrix, on_delete=models.CASCADE, related_name='regles')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE, null=True, blank=True,
        related_name='regles_liste_prix')
    categorie_nom = models.CharField(max_length=150, blank=True, default='')
    marque = models.CharField(max_length=100, blank=True, default='')
    type_regle = models.CharField(max_length=25, choices=TypeRegle.choices)
    valeur = models.DecimalField(
        max_digits=10, decimal_places=4,
        help_text='Prix fixe (MAD), % de remise, ou coefficient formule selon type_regle.')
    quantite_min = models.DecimalField(
        max_digits=10, decimal_places=2, default=1,
        help_text='Palier : quantité minimale pour que la règle s\'applique.')
    priorite = models.PositiveIntegerField(
        default=0, help_text='Priorité explicite (plus haut = préféré) à portée égale.')
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Règle de liste de prix'
        verbose_name_plural = 'Règles de liste de prix'
        ordering = ['-priorite', '-quantite_min']

    def __str__(self):
        return f'{self.liste_id} / {self.type_regle} (min {self.quantite_min})'

    @property
    def specificite(self):
        """Rang de spécificité de portée : produit > catégorie > marque > catalogue."""
        if self.produit_id:
            return 3
        if self.categorie_nom:
            return 2
        if self.marque:
            return 1
        return 0

    def matches_produit(self, produit):
        if self.produit_id:
            return produit.pk == self.produit_id
        if self.categorie_nom:
            cat = getattr(produit, 'categorie', None)
            return bool(cat) and cat.nom == self.categorie_nom
        if self.marque:
            return (produit.marque or '') == self.marque
        return True


class PlanCommission(models.Model):
    """XSAL6 — Plan de commission par commercial (au-delà du mode société
    unique `CompanyProfile.commission_mode`).

    ``owner`` nul = plan par défaut de la société (fallback quand un
    commercial n'a pas de plan dédié). ``base`` détermine sur quoi le taux/
    montant s'applique : CA des devis signés, marge interne (ADMIN-ONLY —
    calculée depuis ``prix_achat``, jamais exposée aux non-admins) ou MAD par
    kWc installé. ``paliers`` (JSON optionnel) permet une accélération du taux
    une fois un seuil d'atteinte d'objectif dépassé — la lecture de
    l'atteinte se fait via ``apps.crm.selectors`` (jamais d'import direct de
    ``apps.crm.models``). Le rapport (`reporting/insights.commissions`)
    résout le plan du commercial : plan dédié → plan par défaut société →
    ``CompanyProfile.commission_mode`` actuel (comportement historique
    inchangé quand aucun plan n'existe)."""
    class Base(models.TextChoices):
        CA_DEVIS_SIGNE = 'ca_devis_signe', 'CA des devis signés'
        MARGE_INTERNE = 'marge_interne', 'Marge interne (admin uniquement)'
        PAR_KWC = 'par_kwc', 'MAD par kWc installé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='plans_commission')
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True,
        blank=True, related_name='plans_commission',
        help_text='Vide = plan par défaut de la société.')
    base = models.CharField(max_length=20, choices=Base.choices)
    taux_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='% appliqué à la base (mode ca_devis_signe / marge_interne).')
    montant_par_kwc = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='MAD par kWc installé (mode par_kwc).')
    # Paliers d'accélération : [{"seuil_atteinte_pct": 100, "taux": 5}, ...]
    # adossés à l'atteinte crm.ObjectifCommercial (lue via crm.selectors).
    paliers = models.JSONField(null=True, blank=True)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Plan de commission'
        verbose_name_plural = 'Plans de commission'
        ordering = ['-created_at']

    def __str__(self):
        who = f'owner={self.owner_id}' if self.owner_id else 'défaut société'
        return f'PlanCommission({who}, {self.base})'

    def taux_effectif(self, atteinte_pct=None):
        """Taux/montant après application du palier d'accélération le plus
        haut ATTEINT (``atteinte_pct`` fourni par l'appelant, résolu via
        ``crm.selectors``). Sans palier ou sans atteinte fournie : le taux de
        base, comportement inchangé."""
        base_valeur = (
            self.montant_par_kwc if self.base == self.Base.PAR_KWC
            else self.taux_pct
        )
        if not self.paliers or atteinte_pct is None:
            return base_valeur
        eligible = [
            p for p in self.paliers
            if atteinte_pct >= p.get('seuil_atteinte_pct', 0)
        ]
        if not eligible:
            return base_valeur
        best = max(eligible, key=lambda p: p.get('seuil_atteinte_pct', 0))
        return best.get('taux', base_valeur)


class LivraisonBC(models.Model):
    """XSAL12 — Livraison partielle d'un bon de commande client.

    Une ligne par événement de livraison (ex. « panneaux livrés le 3 juin »).
    Le décompte réel par ligne de BC vit sur ``LigneLivraisonBC`` ; le solde
    (reliquat) et le passage automatique à ``livre`` sont calculés à la
    demande depuis l'ensemble des livraisons du BC — jamais stockés en dur
    pour rester toujours cohérents avec ``LigneDevis.quantite`` source."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='livraisons_bc')
    bon_commande = models.ForeignKey(
        BonCommande, on_delete=models.CASCADE, related_name='livraisons')
    date_livraison = models.DateField()
    note = models.CharField(max_length=255, blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='livraisons_bc_creees')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Livraison (BC)'
        verbose_name_plural = 'Livraisons (BC)'
        ordering = ['-date_livraison', '-created_at']

    def __str__(self):
        return f'Livraison {self.bon_commande_id} du {self.date_livraison}'


class LigneLivraisonBC(models.Model):
    """XSAL12 — Quantité livrée pour une ligne de devis donnée, dans une
    livraison partielle. ``ligne_devis`` référence la ligne du devis source
    du BC (même app, FK directe autorisée)."""
    livraison = models.ForeignKey(
        LivraisonBC, on_delete=models.CASCADE, related_name='lignes')
    ligne_devis = models.ForeignKey(
        LigneDevis, on_delete=models.CASCADE,
        related_name='lignes_livraison_bc')
    quantite_livree = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'Ligne de livraison (BC)'
        verbose_name_plural = 'Lignes de livraison (BC)'

    def __str__(self):
        return f'{self.livraison_id} / ligne {self.ligne_devis_id} = {self.quantite_livree}'


# ── ODX17 — MODULE FACTURATION (déplacé) ─────────────────────────────────────
# Facture, LigneFacture, Paiement, Avoir, LigneAvoir, FollowupLevel et
# RelanceLog vivent désormais dans ``apps.facturation`` (équivalent Odoo
# Invoicing, séparé de Sales). ODX17 les a sortis de ventes en préservant à
# l'IDENTIQUE leurs tables (``db_table = 'ventes_<model>'``) via des
# migrations ``SeparateDatabaseAndState`` (state-only, zéro SQL). Ce
# ré-export garde le code/migrations historiques
# (``from apps.ventes.models import Facture``, admin, tests, générer-facture,
# échéanciers, reporting, compta, publicapi…) fonctionnels ; à retirer en
# ODX22 une fois tous les appelants re-pointés sur ``apps.facturation``.
from apps.facturation.models import (  # noqa: E402,F401
    Avoir,
    Facture,
    FollowupLevel,
    LigneAvoir,
    LigneFacture,
    Paiement,
    RelanceLog,
)


# ── FG209–221 — CONFIGURATION DE VENTE (rapatriée de compta, ODX14) ─────────
# Ces modèles (quotation templates / pricelists / online quotes façon Odoo
# Sales) vivaient dans ``apps.compta.models``. ODX14 les déplace ICI en
# préservant à l'IDENTIQUE leurs tables physiques
# (``db_table = 'compta_<model>'``) via des migrations
# ``SeparateDatabaseAndState`` (state-only, zéro SQL) — même recette que
# ODX9/ODX11/ODX12/ODX13. ``apps.compta.models`` garde un shim de ré-export
# (``from apps.ventes.models import CodePromotion, …``) pour tout le code
# existant (serializers/views/services compta, migrations historiques).
# Invariants : /proposal reste l'unique voie PDF devis (DocumentProposition =
# ANNEXE du même moteur, jamais un 2ᵉ chemin, règle #4) ; l'e-catalogue
# n'expose JAMAIS prix_achat ; toute numérotation reste sur references.py.
from decimal import Decimal  # noqa: E402
from django.core.exceptions import ValidationError  # noqa: E402


class CodePromotion(models.Model):
    """Code de remise daté applicable à un devis (FG209), traçable au ROI.

    Exemple « -5 % Aïd » valable du… au… Le taux est plafonné 0–100 %. Le
    compteur ``nb_utilisations`` et ``ca_genere`` permettent de mesurer le ROI.
    L'application au devis est faite côté ventes ; ici on définit/valide le code.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='codes_promotion',
        verbose_name='Société',
    )
    code = models.CharField(max_length=40, verbose_name='Code')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    taux_remise = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Taux de remise (%)')
    date_debut = models.DateField(verbose_name='Valable du')
    date_fin = models.DateField(verbose_name='Valable au')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    nb_utilisations = models.PositiveIntegerField(
        default=0, verbose_name="Nombre d'utilisations")
    ca_genere = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='CA généré (TTC)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Code de promotion'
        verbose_name_plural = 'Codes de promotion'
        db_table = 'compta_codepromotion'
        ordering = ['-date_creation']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'],
                name='uniq_code_promotion',
            ),
        ]

    def __str__(self):
        return f'{self.code} (-{self.taux_remise} %)'

    def clean(self):
        super().clean()
        if self.taux_remise is not None and (
                self.taux_remise < 0 or self.taux_remise > 100):
            raise ValidationError(
                'Le taux de remise doit être entre 0 et 100 %.')
        if (self.date_debut and self.date_fin
                and self.date_fin < self.date_debut):
            raise ValidationError(
                'La date de fin doit être postérieure à la date de début.')


class ModeleDevis(models.Model):
    """Modèle de devis réutilisable par marché (FG210).

    Exemples : « Résidentiel 5 kWc », « Pompage 3 CV ». Les lignes-types sont
    décrites en JSON (désignation/quantité/prix indicatif) : une amorce que le
    commercial charge dans le générateur de devis. Ne crée aucun document ; ne
    touche pas le modèle Devis.
    """
    class Marche(models.TextChoices):
        RESIDENTIEL = 'residentiel', 'Résidentiel'
        INDUSTRIEL = 'industriel', 'Industriel/Commercial'
        AGRICOLE = 'agricole', 'Agricole (pompage)'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='modeles_devis',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=200, verbose_name='Nom du modèle')
    marche = models.CharField(
        max_length=12, choices=Marche.choices, default=Marche.RESIDENTIEL,
        verbose_name='Marché')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    lignes_type = models.JSONField(
        default=list, blank=True, verbose_name='Lignes-types (JSON)')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Modèle de devis'
        verbose_name_plural = 'Modèles de devis'
        db_table = 'compta_modeledevis'
        ordering = ['marche', 'nom']

    def __str__(self):
        return f'{self.nom} ({self.marche})'


class SessionGuidedSelling(models.Model):
    """Session d'un assistant pas-à-pas de configuration de devis (FG211).

    Persiste les réponses d'un commercial junior au fil des étapes ; un service
    valide la cohérence (ex. kWc vs onduleur) et propose une composition. Ne
    crée pas le devis lui-même.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='sessions_guided_selling',
        verbose_name='Société',
    )
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sessions_guided_selling',
        verbose_name='Auteur',
    )
    marche = models.CharField(
        max_length=12, default='residentiel', verbose_name='Marché')
    reponses = models.JSONField(
        default=dict, blank=True, verbose_name='Réponses (JSON)')
    composition = models.JSONField(
        default=dict, blank=True,
        verbose_name='Composition proposée (JSON)')
    complet = models.BooleanField(default=False, verbose_name='Complète')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Session de configuration guidée'
        verbose_name_plural = 'Sessions de configuration guidée'
        db_table = 'compta_sessionguidedselling'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Guided selling {self.id} ({self.marche})'


class DemandeApprobationConfig(models.Model):
    """Demande d'approbation d'une composition de devis non-standard (FG213).

    Quand la composition sort des règles (ex. kWc/onduleur incohérents), elle
    part en validation. Le devis est référencé par id opaque (ventes). Workflow :
    en_attente → approuvée/refusée, traçable (qui, quand, motif).
    """
    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        APPROUVEE = 'approuvee', 'Approuvée'
        REFUSEE = 'refusee', 'Refusée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='approbations_config',
        verbose_name='Société',
    )
    devis_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Devis (id ventes)')
    devis_reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence devis')
    motif = models.TextField(
        verbose_name='Motif de la non-conformité')
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE,
        verbose_name='Statut')
    demandeur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approbations_demandees',
        verbose_name='Demandeur',
    )
    decideur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approbations_decidees',
        verbose_name='Décideur',
    )
    commentaire_decision = models.TextField(
        blank=True, default='', verbose_name='Commentaire de décision')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')
    date_decision = models.DateTimeField(
        null=True, blank=True, verbose_name='Décidée le')

    class Meta:
        verbose_name = "Demande d'approbation de configuration"
        verbose_name_plural = "Demandes d'approbation de configuration"
        db_table = 'compta_demandeapprobationconfig'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Approbation {self.devis_reference or self.devis_id} ({self.statut})'


class ECatalogue(models.Model):
    """Page catalogue publique tokenisée, prix public TTC SEULEMENT (FG214).

    Jeton long/imprévisible/expirant. Le rendu n'expose JAMAIS le prix d'achat
    (``prix_achat``) ni aucune marge — uniquement le prix public TTC, lu via les
    selectors de stock. La sélection de produits est stockée en liste d'ids
    opaques (jamais un FK cross-app vers stock).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='ecatalogues',
        verbose_name='Société',
    )
    titre = models.CharField(
        max_length=200, default='Catalogue', verbose_name='Titre')
    token = models.CharField(
        max_length=64, unique=True, db_index=True,
        verbose_name='Token public')
    produit_ids = models.JSONField(
        default=list, blank=True,
        verbose_name='Produits exposés (ids stock)')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    expire_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Expire le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'E-catalogue public'
        verbose_name_plural = 'E-catalogues publics'
        db_table = 'compta_ecatalogue'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.titre} ({self.token[:8]}…)'


class DocumentProposition(models.Model):
    """Annexe réutilisable attachable à un PDF de proposition (FG215).

    Lettre de couverture, page de références, garanties… Le document est un
    bloc de contenu (titre + corps + pièce jointe optionnelle) que le
    commercial sélectionne pour enrichir un devis. Purement additif : ne touche
    NI le générateur de devis NI le moteur PDF — c'est une bibliothèque
    d'annexes côté compta/marketing.
    """
    class TypeDocument(models.TextChoices):
        LETTRE = 'lettre', 'Lettre de couverture'
        REFERENCES = 'references', 'Références / réalisations'
        GARANTIES = 'garanties', 'Garanties'
        AUTRE = 'autre', 'Autre annexe'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='documents_proposition',
        verbose_name='Société',
    )
    titre = models.CharField(max_length=200, verbose_name='Titre')
    type_document = models.CharField(
        max_length=12, choices=TypeDocument.choices,
        default=TypeDocument.AUTRE, verbose_name='Type de document')
    contenu = models.TextField(
        blank=True, default='', verbose_name='Contenu (texte)')
    fichier = models.FileField(
        upload_to='compta/propositions/', null=True, blank=True,
        verbose_name='Pièce jointe')
    ordre = models.PositiveIntegerField(
        default=0, verbose_name="Ordre d'affichage")
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Document de proposition'
        verbose_name_plural = 'Documents de proposition'
        db_table = 'compta_documentproposition'
        ordering = ['type_document', 'ordre', 'titre']

    def __str__(self):
        return f'{self.titre} ({self.type_document})'


class SimulationPublique(models.Model):
    """Simulation kWc/économies lancée publiquement → lead pré-rempli (FG216).

    Le visiteur dimensionne un kit (puissance souhaitée / facture mensuelle) et
    laisse ses coordonnées ; on stocke la simulation et, si demandé, on crée un
    lead pré-rempli via le SERVICE crm (jamais ses modèles). La création de
    lead est gardée par un flag (NO-OP par défaut) — voir
    ``services.creer_lead_depuis_simulation``.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='simulations_publiques',
        verbose_name='Société',
    )
    nom_prospect = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Nom du prospect')
    telephone = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Téléphone')
    email = models.EmailField(
        blank=True, default='', verbose_name='Email')
    puissance_kwc = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Puissance estimée (kWc)')
    facture_mensuelle = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Facture mensuelle (MAD)')
    economie_annuelle = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Économie annuelle estimée (MAD)')
    parametres = models.JSONField(
        default=dict, blank=True, verbose_name='Paramètres de simulation')
    lead_cree = models.BooleanField(
        default=False, verbose_name='Lead créé')
    lead_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du lead créé')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Simulation publique'
        verbose_name_plural = 'Simulations publiques'
        db_table = 'compta_simulationpublique'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Simulation {self.puissance_kwc} kWc ({self.nom_prospect})'


class SimulationFinancement(models.Model):
    """Bloc mensualités crédit/leasing rattaché à un devis (FG217).

    Calcule la mensualité d'un crédit amortissable (montant, durée, taux
    annuel) pour l'afficher au client. N'altère PAS le devis ni son total : le
    devis est référencé par id (jamais un FK cross-app vers ventes). Le calcul
    est fait côté service (``services.calcul_mensualite``) au save.
    """
    class Type(models.TextChoices):
        CREDIT = 'credit', 'Crédit amortissable'
        LEASING = 'leasing', 'Leasing / LOA'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='simulations_financement',
        verbose_name='Société',
    )
    devis_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du devis')
    devis_reference = models.CharField(
        max_length=60, blank=True, default='', verbose_name='Référence devis')
    type_financement = models.CharField(
        max_length=10, choices=Type.choices, default=Type.CREDIT,
        verbose_name='Type de financement')
    montant_finance = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Montant financé (MAD)')
    duree_mois = models.PositiveIntegerField(
        default=12, verbose_name='Durée (mois)')
    taux_annuel = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('0.000'),
        verbose_name='Taux annuel (%)')
    mensualite = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Mensualité estimée (MAD)')
    cout_total_credit = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Coût total du crédit (MAD)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Simulation de financement'
        verbose_name_plural = 'Simulations de financement'
        db_table = 'compta_simulationfinancement'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.type_financement} {self.montant_finance} MAD / {self.duree_mois} mois'

    def clean(self):
        super().clean()
        if self.duree_mois is not None and self.duree_mois <= 0:
            raise ValidationError('La durée doit être strictement positive.')
        if self.taux_annuel is not None and self.taux_annuel < 0:
            raise ValidationError('Le taux annuel ne peut pas être négatif.')


class OffreFinancement(models.Model):
    """Catalogue d'offres de financement sélectionnables sur un devis (FG218).

    Une offre = un partenaire/banque + ses conditions (taux, durée min/max,
    montant min/max, apport). Sert d'amorce à ``SimulationFinancement`` : le
    commercial choisit l'offre, puis simule.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='offres_financement',
        verbose_name='Société',
    )
    partenaire = models.CharField(
        max_length=200, verbose_name='Banque / partenaire')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name="Libellé de l'offre")
    taux_annuel = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('0.000'),
        verbose_name='Taux annuel (%)')
    duree_min_mois = models.PositiveIntegerField(
        default=12, verbose_name='Durée minimale (mois)')
    duree_max_mois = models.PositiveIntegerField(
        default=84, verbose_name='Durée maximale (mois)')
    montant_min = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Montant minimal (MAD)')
    montant_max = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Montant maximal (MAD)')
    apport_min_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Apport minimal (%)')
    actif = models.BooleanField(default=True, verbose_name='Active')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Offre de financement'
        verbose_name_plural = 'Offres de financement'
        db_table = 'compta_offrefinancement'
        ordering = ['partenaire', 'taux_annuel']

    def __str__(self):
        return f'{self.partenaire} — {self.taux_annuel} %'


class LigneIncitation(models.Model):
    """Incitation/subvention déductible affichée sur un devis (FG219).

    Montant déductible (Tatwir, MASEN…) qui réduit le coût client : on affiche
    coût brut → aide → coût net. N'altère PAS le total du devis (statut
    PRÉSERVÉ, CLAUDE.md règle #4) : c'est un encart informatif. Devis référencé
    par id.
    """
    class Programme(models.TextChoices):
        TATWIR = 'tatwir', 'Tatwir'
        MASEN = 'masen', 'MASEN'
        IRESEN = 'iresen', 'IRESEN'
        AUTRE = 'autre', 'Autre dispositif'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='lignes_incitation',
        verbose_name='Société',
    )
    devis_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du devis')
    devis_reference = models.CharField(
        max_length=60, blank=True, default='', verbose_name='Référence devis')
    programme = models.CharField(
        max_length=10, choices=Programme.choices, default=Programme.AUTRE,
        verbose_name='Programme')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    montant_aide = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name="Montant de l'aide (MAD)")
    cout_brut = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Coût brut (MAD)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Ligne d'incitation"
        verbose_name_plural = "Lignes d'incitation"
        db_table = 'compta_ligneincitation'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.programme} -{self.montant_aide} MAD'

    @property
    def cout_net(self):
        """Coût net après déduction de l'aide (jamais négatif)."""
        net = (self.cout_brut or Decimal('0.00')) - (
            self.montant_aide or Decimal('0.00'))
        return net if net > 0 else Decimal('0.00')

    def clean(self):
        super().clean()
        if self.montant_aide is not None and self.montant_aide < 0:
            raise ValidationError("Le montant de l'aide ne peut pas être négatif.")


class EcheancierPaiement(models.Model):
    """Échéancier de tranches sur une facture (FG220), type Tayssir.

    Plan de paiement échelonné rattaché à une facture (référencée par id, jamais
    un FK cross-app vers ventes) : N tranches avec dates/montants et suivi des
    versements. ``montant_regle`` / ``reste_a_payer`` agrègent les tranches.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='echeanciers_paiement',
        verbose_name='Société',
    )
    facture_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id de la facture')
    facture_reference = models.CharField(
        max_length=60, blank=True, default='', verbose_name='Référence facture')
    montant_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Montant total (MAD)')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Échéancier de paiement'
        verbose_name_plural = 'Échéanciers de paiement'
        db_table = 'compta_echeancierpaiement'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Échéancier {self.facture_reference} ({self.montant_total} MAD)'


class TranchePaiement(models.Model):
    """Une tranche d'un échéancier de paiement (FG220)."""
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='tranches_paiement',
        verbose_name='Société',
    )
    echeancier = models.ForeignKey(
        EcheancierPaiement,
        on_delete=models.CASCADE,
        related_name='tranches',
        verbose_name='Échéancier',
    )
    numero = models.PositiveIntegerField(default=1, verbose_name='N° tranche')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Montant (MAD)')
    date_echeance = models.DateField(verbose_name="Date d'échéance")
    montant_regle = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Montant réglé (MAD)')
    date_reglement = models.DateField(
        null=True, blank=True, verbose_name='Date de règlement')
    paye = models.BooleanField(default=False, verbose_name='Payée')

    class Meta:
        verbose_name = 'Tranche de paiement'
        verbose_name_plural = 'Tranches de paiement'
        db_table = 'compta_tranchepaiement'
        ordering = ['echeancier', 'numero']
        constraints = [
            models.UniqueConstraint(
                fields=['echeancier', 'numero'],
                name='uniq_tranche_numero',
            ),
        ]

    def __str__(self):
        return f'Tranche {self.numero} — {self.montant} MAD'
