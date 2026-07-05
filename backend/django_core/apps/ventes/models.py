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

    class Meta:
        verbose_name = 'Devis'
        verbose_name_plural = 'Devis'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference

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
        'Facture', on_delete=models.CASCADE, related_name='activites')
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
        'Facture', on_delete=models.CASCADE, related_name='sources')
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


class Facture(models.Model):
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EMISE = 'emise', 'Émise'
        PAYEE = 'payee', 'Payée'
        EN_RETARD = 'en_retard', 'En retard'
        ANNULEE = 'annulee', 'Annulée'

    # ── Type de facture (échéancier devis → factures, 2026-06-13) ──
    # ACOMPTE = première tranche ; INTERMEDIAIRE = tranche du milieu
    # (livraison matériel) ; SOLDE = dernière tranche ; COMPLETE = facture
    # classique 100 % (chaîne historique BC → facture, lignes recopiées).
    class TypeFacture(models.TextChoices):
        ACOMPTE = 'acompte', 'Acompte'
        INTERMEDIAIRE = 'intermediaire', 'Intermédiaire'
        SOLDE = 'solde', 'Solde'
        COMPLETE = 'complete', 'Facture complète'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='factures',
    )
    reference = models.CharField(max_length=50)
    bon_commande = models.OneToOneField(
        BonCommande,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='facture',
    )
    # Lien direct vers le devis quand la facture vient de l'échéancier
    # (acompte/tranches). La chaîne historique BC → facture reste intacte ;
    # ce FK est additif et optionnel. SET_NULL pour ne jamais perdre une
    # facture émise si le devis est supprimé.
    devis = models.ForeignKey(
        Devis,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='factures',
    )
    # U12 — lien DIRECT vers le lead d'origine, snapshoté à la création depuis
    # le devis source (devis.lead, ou bon_commande.devis.lead pour la chaîne
    # BC → facture). Additif/optionnel : une facture sans lead reste valide, et
    # on ne perd jamais le lien si le devis est supprimé (SET_NULL). Permet de
    # lister « toutes les factures d'un lead » sans traverser le devis (qui peut
    # passer à NULL). related_name distinct (`factures_directes`) pour ne pas
    # entrer en conflit avec un futur reverse `factures` côté Lead.
    lead = models.ForeignKey(
        'crm.Lead',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='factures_directes',
    )
    type_facture = models.CharField(
        max_length=20,
        choices=TypeFacture.choices,
        default=TypeFacture.COMPLETE,
    )
    # Part de l'échéancier représentée par cette tranche (en % du TTC devis).
    pourcentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
    )
    # Libellé d'une facture sans lignes (ex. « Acompte 30 % sur devis … »).
    libelle = models.CharField(max_length=255, blank=True, null=True)
    # Montants figés à la création pour les tranches (source unique = totaux
    # du devis × pourcentage). NULL = facture classique → totaux calculés
    # depuis les lignes, rendu strictement inchangé pour l'existant.
    montant_ht = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
    )
    montant_tva = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
    )
    montant_ttc = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
    )
    client = models.ForeignKey(
        'crm.Client',
        on_delete=models.PROTECT,
        related_name='factures',
    )
    statut = models.CharField(
        max_length=20,
        choices=Statut.choices,
        default=Statut.BROUILLON,
    )
    date_emission = models.DateField(auto_now_add=True)
    date_echeance = models.DateField(null=True, blank=True)
    taux_tva = models.DecimalField(
        max_digits=5, decimal_places=2, default=20.00
    )
    remise_globale = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    note = models.TextField(blank=True, null=True)
    # ── Conformité Article 145 CGI (N11) — additif, optionnel ──
    # date_livraison = date de la livraison/prestation (mention obligatoire) ;
    # conditions_paiement = conditions et mode de règlement (mention obligatoire).
    # Tous deux optionnels : leur absence ne fait qu'AVERTIR, jamais bloquer.
    date_livraison = models.DateField(null=True, blank=True)
    conditions_paiement = models.TextField(blank=True, default='')
    # ── Relances / recouvrement (workstream E) — additif ──
    # Date de la prochaine relance prévue (posée à l'enregistrement d'une
    # relance) ; exclu_relances retire la facture des listes d'impayés.
    prochaine_relance = models.DateField(null=True, blank=True)
    exclu_relances = models.BooleanField(default=False)
    # XFAC5 — exclusion des relances avec EXPIRATION (contrairement au
    # booléen éternel ci-dessus). NULL = pas d'expiration programmée
    # (comportement historique inchangé). Une promesse de paiement active
    # pose aussi cette date automatiquement (voir PromessePaiement).
    exclu_relances_jusquau = models.DateField(null=True, blank=True)

    # XFAC12 — escompte pour règlement anticipé (ex. 2/10 net 30). Les deux
    # champs sont nullable : NULL/absent = comportement actuel inchangé
    # (aucun escompte). Proposés depuis un réglage société (surchargeables
    # par facture) à la création côté serializer/vue — le modèle reste
    # purement additif ici.
    escompte_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Taux d'escompte (%) si réglé sous escompte_jours.")
    escompte_jours = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Nombre de jours depuis l'émission pour bénéficier de "
                  "l'escompte.")

    # ── XFAC13 — abandon de créance (write-off) ──
    # Trace un solde définitif d'une créance irrécouvrable/négligeable : la
    # facture passe « payée » sans encaissement complémentaire. NULL/vide =
    # comportement actuel inchangé (aucun abandon). ``abandon_auto`` distingue
    # un abandon manuel (motif choisi par un responsable) d'un abandon proposé
    # automatiquement sous la tolérance société à l'encaissement (XFAC13).
    class MotifAbandon(models.TextChoices):
        IRRECOUVRABLE = 'irrecouvrable', 'Irrécouvrable'
        GESTE_COMMERCIAL = 'geste_commercial', 'Geste commercial'
        ECART_REGLEMENT = 'ecart_reglement', 'Écart de règlement'
        LIQUIDATION = 'liquidation', 'Liquidation'

    abandon_motif = models.CharField(
        max_length=20, choices=MotifAbandon.choices, blank=True, default='')
    abandon_montant = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Résiduel soldé par abandon (MAD).')
    abandon_date = models.DateTimeField(null=True, blank=True)
    abandon_auto = models.BooleanField(
        default=False,
        help_text="Abandon proposé automatiquement sous la tolérance "
                  "d'écart de règlement société (par opposition à un "
                  "abandon manuel motivé).")
    abandon_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='factures_abandonnees',
    )

    # ── XFAC18 — statut de REVUE (ségrégation des tâches, style Odoo 19) ──
    # Statut de TRAVAIL additif, distinct du cycle ``Statut`` existant : quand
    # le réglage société ``revue_factures_active`` est OFF (défaut), ce champ
    # reste vide et n'affecte rien (comportement actuel byte-identique). ON,
    # une facture créée par un utilisateur du tier limité démarre « à
    # valider » et ``emettre`` exige un valideur DIFFÉRENT du créateur.
    class RevueStatut(models.TextChoices):
        A_VALIDER = 'a_valider', 'À valider'
        VALIDEE = 'validee', 'Validée'

    revue_statut = models.CharField(
        max_length=15, choices=RevueStatut.choices, blank=True, default='')

    # ── Statut de télédéclaration DGI (N39) — purement INFORMATIF, posé à la
    # main. Prépare le modèle de données pour un futur flux DGI sans aucun
    # appel externe aujourd'hui. Défaut « Non soumise » = comportement actuel.
    class StatutTeledeclaration(models.TextChoices):
        NON_SOUMISE = 'non_soumise', 'Non soumise'
        SOUMISE = 'soumise', 'Soumise'
        VALIDEE = 'validee', 'Validée'

    statut_teledeclaration = models.CharField(
        max_length=15, choices=StatutTeledeclaration.choices,
        default=StatutTeledeclaration.NON_SOUMISE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='factures_creees',
    )
    fichier_pdf = models.CharField(
        max_length=500, blank=True, null=True
    )
    # ── Export structuré UBL 2.1 (N38) — clé MinIO du dernier XML généré.
    # Purement préparatoire (aperçu brouillon, jamais transmis). Additif.
    fichier_ubl = models.CharField(
        max_length=500, blank=True, null=True
    )
    # ── FG52 — Devise (multi-currency) — additif, tout optionnel ──
    # Même sémantique que sur le Devis : code ISO 4217, défaut MAD, taux = 1.0.
    # Le UBL 2.1 lit ce champ pour renseigner DocumentCurrencyCode au lieu du
    # « MAD » codé en dur de la version précédente.
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

    # ── XFAC29 — Transmission DGI SORTANTE (key-gated, additif) ──
    # Distincte de `fichier_ubl` (export local N105, jamais transmis) : ces
    # champs suivent le cycle de vie d'une VRAIE transmission signée à une
    # plateforme agréée, une fois sa spec publiée. Défaut = jamais transmise
    # (comportement actuel byte-identique tant qu'aucune transmission n'est
    # déclenchée).
    class DgiStatut(models.TextChoices):
        A_TRANSMETTRE = 'a_transmettre', 'À transmettre'
        TRANSMISE = 'transmise', 'Transmise'
        ACCEPTEE = 'acceptee', 'Acceptée'
        REJETEE = 'rejetee', 'Rejetée'

    dgi_statut = models.CharField(
        max_length=15, choices=DgiStatut.choices,
        default=DgiStatut.A_TRANSMETTRE,
        verbose_name='Statut transmission DGI',
    )
    dgi_reference = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='Référence DGI',
    )
    dgi_motif_rejet = models.TextField(
        blank=True, default='',
        verbose_name='Motif de rejet DGI',
    )

    # ── YSUBS9 — Période de service (du/au) des factures récurrentes ──
    # NULL = comportement actuel (facture non récurrente ou pré-existante).
    # Renseignés par `creer_facture_contrat` (ventes) et
    # `facturer_ligne_echeance` (contrats) à partir de la période facturée —
    # permet le calcul du revenu différé au prorata et prouve l'unicité
    # (une facture par ligne par période).
    periode_service_debut = models.DateField(
        null=True, blank=True, verbose_name='Période de service — début')
    periode_service_fin = models.DateField(
        null=True, blank=True, verbose_name='Période de service — fin')

    class Meta:
        verbose_name = 'Facture'
        verbose_name_plural = 'Factures'
        ordering = ['-date_emission']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        """U12 — snapshote le lead d'origine depuis le devis source à la création.

        Couvre les deux voies : la facture d'échéancier (porte `devis`) et la
        chaîne BC → facture (porte `bon_commande`, dont le devis porte le lead).
        On ne pose le lead que s'il n'est pas déjà fixé (jamais d'écrasement) et
        qu'un devis source le porte — comportement historique strictement
        inchangé pour une facture sans devis/BC ou sans lead (ex. facture de
        contrat de maintenance)."""
        if self.lead_id is None:
            # Résolution INLINE (aucun import de services → préserve le contrat
            # import-linter). Facture d'échéancier → self.devis ; chaîne
            # BC → facture → self.bon_commande.devis.
            devis = getattr(self, 'devis', None)
            if devis is None:
                bc = getattr(self, 'bon_commande', None)
                devis = getattr(bc, 'devis', None) if bc is not None else None
            lead = getattr(devis, 'lead', None) if devis is not None else None
            if lead is not None:
                self.lead = lead
        super().save(*args, **kwargs)

    @property
    def total_ht(self):
        # Tranche d'échéancier : montant figé. Sinon : somme des lignes.
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
        """Ventilation de la TVA par taux (10 % / 20 %), réconciliée au centime.

        Miroir exact de la logique devis : on regroupe les lignes par taux
        effectif. Mono-taux (toutes les factures historiques ou de tranche) →
        un seul panier, calculé par la formule d'origine, rendu strictement
        inchangé. Taux mixtes (10/20) → un panier par taux, chaque TVA
        arrondie au centime, dont la somme est le total TVA.

        DC23 — délègue au selector unique ``tva_buckets``. Facture de tranche
        (montant figé) : panier figé passé via ``frozen``.
        """
        from .selectors import tva_buckets
        frozen = None
        if self.montant_tva is not None:
            # Facture de tranche (acompte) : montant figé, un seul panier.
            frozen = (self.taux_tva, self.total_ht, self.montant_tva)
        return tva_buckets(
            self.lignes.all(), fallback_taux=self.taux_tva, frozen=frozen)

    @property
    def total_ttc(self):
        if self.montant_ttc is not None:
            return self.montant_ttc
        return self.total_ht + self.total_tva

    @property
    def montant_paye(self):
        """Somme des paiements enregistrés sur cette facture.

        XFAC1 — inclut aussi les ventilations d'avances (``AffectationPaiement``)
        reçues par cette facture : une avance non affectée (``facture`` vide)
        n'entre dans ``montant_paye`` d'aucune facture tant qu'elle n'est pas
        ventilée. Comportement historique inchangé pour un paiement classique
        (posé directement sur ``facture``, jamais ventilé).

        XFAC12 — inclut aussi les escomptes automatiquement appliqués
        (``Paiement.escompte_montant``) : le règlement net + l'escompte
        SOLDENT ensemble la facture, exactement comme montant + retenue
        (XFAC4). Sans escompte (0/NULL) → comportement inchangé.

        YLEDG5 — un paiement ``rejete`` (chèque impayé/virement rejeté) sort
        de ce total : la facture redevient ouverte/en retard exactement
        comme si le règlement n'avait jamais eu lieu (jamais supprimé —
        piste d'audit conservée)."""
        from decimal import Decimal
        actifs = [p for p in self.paiements.all()
                  if p.statut != Paiement.Statut.REJETE]
        direct = sum((p.montant for p in actifs), Decimal('0'))
        escomptes = sum(
            (p.escompte_montant or Decimal('0') for p in actifs),
            Decimal('0'))
        via_affectation = sum(
            (a.montant for a in self.affectations_paiement.all()), Decimal('0'))
        return direct + escomptes + via_affectation

    @property
    def avoirs_total(self):
        """Total TTC des avoirs (notes de crédit) actifs sur cette facture.

        Un avoir réduit ce que le client doit. Aucun avoir → 0 → comportement
        historique strictement inchangé."""
        from decimal import Decimal
        return sum(
            (a.total_ttc for a in self.avoirs.all()
             if a.statut != 'annulee'),
            Decimal('0'))

    @property
    def notes_debit_total(self):
        """ZFAC4 — total TTC des notes de débit actives sur cette facture.

        Une note de débit AUGMENTE ce que le client doit — symétrique
        d'``avoirs_total``. Aucune note de débit → 0 → comportement
        historique strictement inchangé."""
        from decimal import Decimal
        return sum(
            (n.total_ttc for n in self.notes_debit.all()
             if n.statut == 'emise'),
            Decimal('0'))

    @property
    def retenues_subies_total(self):
        """XFAC4 — total des retenues à la source SUBIES (RAS TVA/IS) que le
        client a retenues sur cette facture. Une retenue solde la facture au
        même titre qu'un paiement — trace la créance d'attestation, pas une
        perte. Aucune retenue → 0 → comportement historique inchangé."""
        from decimal import Decimal
        return sum(
            (r.montant for r in self.retenues_subies.all()), Decimal('0'))

    @property
    def montant_paye_avec_retenues(self):
        """XFAC4 — payé + retenues subies (ce qui solde réellement la facture)."""
        return self.montant_paye + self.retenues_subies_total

    @property
    def montant_du(self):
        """Reste à payer (TTC + notes de débit − payé − retenues subies −
        avoirs), jamais négatif. ZFAC4 — les notes de débit actives
        AUGMENTENT le reste à payer (symétrique des avoirs) ; aucune note de
        débit → comportement historique strictement inchangé."""
        from decimal import Decimal
        reste = (self.total_ttc + self.notes_debit_total
                 - self.montant_paye_avec_retenues
                 - self.avoirs_total)
        return reste if reste > 0 else Decimal('0')

    @property
    def jours_retard(self):
        """Jours de retard (échéance dépassée) si la facture reste due."""
        from django.utils import timezone
        if not self.date_echeance or self.statut in ('payee', 'annulee'):
            return 0
        if self.montant_du <= 0:
            return 0
        delta = (timezone.now().date() - self.date_echeance).days
        return delta if delta > 0 else 0

    @staticmethod
    def _client_est_pro(client):
        """B2B : client « professionnel » s'il est de type Entreprise ou porte
        un marqueur entreprise (ICE, IF ou RC renseigné)."""
        if client is None:
            return False
        type_client = (getattr(client, 'type_client', '') or '').lower()
        if type_client == 'entreprise':
            return True
        for attr in ('ice', 'if_fiscal', 'rc'):
            if (getattr(client, attr, '') or '').strip():
                return True
        return False

    @property
    def mentions_manquantes(self):
        """Mentions obligatoires manquantes (Article 145 CGI marocain).

        AVERTISSEMENT seulement : renvoie la liste des mentions absentes — ne
        bloque JAMAIS l'émission. Couvre l'identité + IF/ICE/RC du vendeur,
        l'identité du client (+ ICE en B2B), le numéro séquentiel, les dates
        d'émission et de livraison, le détail des lignes, et les conditions de
        paiement.
        """
        manquantes = []
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.get(company=self.company)

        # Identité + identifiants légaux du vendeur.
        if not (profile.nom or '').strip():
            manquantes.append("Identité du vendeur (raison sociale)")
        if not (getattr(profile, 'identifiant_fiscal', '') or '').strip():
            manquantes.append("Identifiant fiscal (IF) du vendeur")
        if not (getattr(profile, 'ice', '') or '').strip():
            manquantes.append("ICE du vendeur")
        if not (getattr(profile, 'rc', '') or '').strip():
            manquantes.append("Registre de commerce (RC) du vendeur")

        # Identité du client (+ ICE pour un client professionnel/B2B).
        client = self.client
        if client is None or not (client.nom or '').strip():
            manquantes.append("Identité du client")
        elif self._client_est_pro(client) and \
                not (getattr(client, 'ice', '') or '').strip():
            manquantes.append("ICE du client (client professionnel)")

        # Numéro séquentiel + date d'émission.
        if not (self.reference or '').strip():
            manquantes.append("Numéro de facture séquentiel")
        if self.date_emission is None:
            manquantes.append("Date d'émission")

        # Date de livraison / prestation.
        if self.date_livraison is None:
            manquantes.append("Date de livraison / prestation")

        # Détail des lignes (désignation, qté, PU HT, taux TVA, total HT).
        lignes = list(self.lignes.all())
        if not lignes and not (self.libelle or '').strip():
            manquantes.append("Détail des lignes (désignation, quantité, "
                              "prix unitaire HT, taux TVA, total HT)")
        else:
            for ligne in lignes:
                if not (ligne.designation or '').strip() \
                        or ligne.quantite is None \
                        or ligne.prix_unitaire is None \
                        or ligne.taux_tva_effectif is None:
                    manquantes.append("Détail des lignes (désignation, "
                                      "quantité, prix unitaire HT, taux TVA, "
                                      "total HT)")
                    break

        # Conditions + mode de paiement.
        if not (self.conditions_paiement or '').strip():
            manquantes.append("Conditions et mode de paiement")

        return manquantes

    @property
    def escompte_mention(self):
        """XFAC12 — mention imprimable de l'escompte (« Escompte X % si
        règlement sous N jours, soit Y MAD »), ou ``None`` si non configuré."""
        if not self.escompte_pct or not self.escompte_jours:
            return None
        from decimal import Decimal
        montant = (
            self.total_ttc * Decimal(self.escompte_pct) / Decimal('100')
        ).quantize(Decimal('0.01'))
        return {
            'pct': self.escompte_pct, 'jours': self.escompte_jours,
            'montant': montant,
        }

    def escompte_applicable(self, date_paiement):
        """XFAC12 — True si ``date_paiement`` tombe dans la fenêtre d'escompte
        (émission + escompte_jours inclus). Sans escompte configuré ou sans
        date d'émission/paiement → False (comportement actuel inchangé)."""
        if not self.escompte_pct or not self.escompte_jours:
            return False
        if not self.date_emission or not date_paiement:
            return False
        from datetime import timedelta
        limite = self.date_emission + timedelta(days=self.escompte_jours)
        return date_paiement <= limite

    def calcul_escompte(self, montant, date_paiement):
        """XFAC12 — montant de l'escompte applicable à un règlement de
        ``montant`` fait le ``date_paiement``, dans la fenêtre. Hors fenêtre
        (ou non configuré) → 0 (comportement actuel inchangé)."""
        from decimal import Decimal
        if not self.escompte_applicable(date_paiement):
            return Decimal('0.00')
        return (
            Decimal(montant) * Decimal(self.escompte_pct) / Decimal('100')
        ).quantize(Decimal('0.01'))


class LigneFacture(models.Model):
    facture = models.ForeignKey(
        Facture, on_delete=models.CASCADE, related_name='lignes'
    )
    produit = models.ForeignKey(
        'stock.Produit',
        on_delete=models.PROTECT,
        related_name='lignes_facture',
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
    # le reste) — exactement comme LigneDevis. NULL = ligne historique → le
    # taux global de la facture s'applique, rendu strictement inchangé pour
    # les factures déjà émises.
    taux_tva = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Taux TVA de la ligne (%). Vide = taux global de la facture.')
    # XFAC11 — facture CONSOLIDÉE : document source de cette ligne (pour le
    # sous-titre « Devis DV-… » groupant les lignes par document d'origine).
    # NULL = ligne classique (facture simple, comportement inchangé).
    source_devis = models.ForeignKey(
        Devis, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lignes_facture_consolidee')

    class Meta:
        verbose_name = 'Ligne de Facture'
        verbose_name_plural = 'Lignes de Facture'

    @property
    def total_ht(self):
        return (
            self.quantite * self.prix_unitaire * (1 - self.remise / 100)
        )

    @property
    def taux_tva_effectif(self):
        """Taux réellement appliqué : celui de la ligne, sinon celui de la facture."""
        return self.taux_tva if self.taux_tva is not None else self.facture.taux_tva


class Paiement(models.Model):
    """Paiement encaissé sur une facture (enregistrement MANUEL) — ou une AVANCE
    client non affectée (XFAC1) tant qu'aucune facture ne la reçoit.

    Une facture peut recevoir plusieurs paiements (acompte partiel, solde…).
    Le reste à payer d'une facture et le solde d'un devis se déduisent de ces
    lignes — source unique du « payé ».

    XFAC1 — ``facture`` devient nullable : un règlement reçu SANS facture
    (avance, acompte à la commande, trop-perçu) se rattache directement au
    ``client`` et reste ``statut=non_affecte`` jusqu'à ventilation (voir
    ``AffectationPaiement``) sur une ou plusieurs factures ouvertes. Un
    paiement classique (facture posée à la création) reste ``affecte`` —
    comportement historique strictement inchangé pour tout paiement déjà
    rattaché à une facture.
    """
    class Mode(models.TextChoices):
        ESPECES = 'especes', 'Espèces'
        VIREMENT = 'virement', 'Virement'
        CHEQUE = 'cheque', 'Chèque'
        CARTE = 'carte', 'Carte bancaire'
        PRELEVEMENT = 'prelevement', 'Prélèvement'
        AUTRE = 'autre', 'Autre'

    class StatutAffectation(models.TextChoices):
        AFFECTE = 'affecte', 'Affecté'
        PARTIELLEMENT_AFFECTE = 'partiellement_affecte', 'Partiellement affecté'
        NON_AFFECTE = 'non_affecte', 'Non affecté'

    # ── YLEDG5 — chemin d'exception « paiement rejeté » (additif) ──
    # Un paiement rejeté (chèque impayé / virement rejeté) N'EST JAMAIS
    # supprimé (piste d'audit) : il sort du calcul montant_paye/Facture.statut
    # via ce statut plutôt que par suppression.
    class Statut(models.TextChoices):
        ENCAISSE = 'encaisse', 'Encaissé'
        REJETE = 'rejete', 'Rejeté'

    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.ENCAISSE)
    motif_rejet = models.CharField(max_length=255, blank=True, default='')
    frais_rejet = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Frais bancaires optionnels liés au rejet (ex. frais de '
                  'chèque impayé), informatif.')
    date_rejet = models.DateField(null=True, blank=True)

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='paiements',
    )
    facture = models.ForeignKey(
        Facture,
        on_delete=models.CASCADE,
        related_name='paiements',
        null=True,
        blank=True,
    )
    # XFAC1 — client titulaire d'une AVANCE non (encore) affectée à une
    # facture. Requis quand ``facture`` est vide ; sinon dérivable de la
    # facture (mais toujours dispo pour retrouver les avances d'un client).
    client = models.ForeignKey(
        'crm.Client',
        on_delete=models.PROTECT,
        related_name='avances',
        null=True,
        blank=True,
    )
    statut_affectation = models.CharField(
        max_length=25, choices=StatutAffectation.choices,
        default=StatutAffectation.AFFECTE,
    )
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    date_paiement = models.DateField()
    mode = models.CharField(
        max_length=20, choices=Mode.choices, default=Mode.VIREMENT,
    )
    reference = models.CharField(max_length=120, blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    # ZFAC7 — suivi métier des chèques (remise en banque, chèque impayé).
    # Uniquement pertinent quand mode == CHEQUE ; laissés vides pour tout
    # autre mode (comportement historique inchangé).
    numero_cheque = models.CharField(max_length=50, blank=True, default='')
    banque_tiree = models.CharField(max_length=120, blank=True, default='')
    # XFAC12 — escompte AUTOMATIQUEMENT appliqué à ce règlement (fenêtre
    # atteinte). 0/NULL = comportement actuel inchangé (aucun escompte, ou
    # règlement hors fenêtre).
    escompte_montant = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='paiements_enregistres',
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Paiement'
        verbose_name_plural = 'Paiements'
        ordering = ['-date_paiement', '-date_creation']

    def __str__(self):
        cible = self.facture.reference if self.facture_id else (
            f'avance client #{self.client_id}')
        return f'{self.montant} MAD — {cible}'

    @property
    def montant_affecte(self):
        """XFAC1 — somme déjà ventilée sur des factures (via AffectationPaiement).

        Pour un paiement classique (facture posée directement, jamais ventilé),
        renvoie son montant plein — comportement historique inchangé."""
        from decimal import Decimal
        total = sum(
            (a.montant for a in self.affectations.all()), Decimal('0'))
        if total:
            return total
        return self.montant if self.facture_id else Decimal('0')

    @property
    def montant_disponible(self):
        """Solde de l'avance encore disponible pour ventilation."""
        from decimal import Decimal
        if self.facture_id and not self.affectations.exists():
            return Decimal('0')
        montant = self.montant if isinstance(self.montant, Decimal) \
            else Decimal(str(self.montant))
        reste = montant - self.montant_affecte
        return reste if reste > 0 else Decimal('0')


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
        Paiement, on_delete=models.CASCADE, related_name='affectations')
    facture = models.ForeignKey(
        Facture, on_delete=models.CASCADE, related_name='affectations_paiement')
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


class Avoir(models.Model):
    """Note de crédit (Avoir) liée à une facture émise — style Odoo : on garde
    le lien vers la facture d'origine, jamais une facture négative isolée.

    Totaux et ventilation TVA calculés EXACTEMENT comme la facture (10 %/20 %,
    réconciliés au centime). Pour une facture de tranche sans lignes, les
    montants sont figés à la création (comme les tranches de facture)."""
    class Statut(models.TextChoices):
        EMISE = 'emise', 'Émis'
        ANNULEE = 'annulee', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='avoirs')
    reference = models.CharField(max_length=50)
    facture = models.ForeignKey(
        Facture, on_delete=models.PROTECT, related_name='avoirs')
    client = models.ForeignKey(
        'crm.Client', on_delete=models.PROTECT, related_name='avoirs')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.EMISE)
    motif = models.TextField(blank=True, default='')
    date_emission = models.DateField(auto_now_add=True)
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2, default=20.00)
    remise_globale = models.DecimalField(
        max_digits=5, decimal_places=2, default=0)
    # Montants figés pour un avoir sur facture sans lignes (tranche).
    montant_ht = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    montant_tva = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    montant_ttc = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='avoirs_crees')
    fichier_pdf = models.CharField(max_length=500, blank=True, null=True)
    # ── XPOS7 — Retour client avec re-stockage (additif) ──
    # Un avoir « normal » (correction de facturation) laisse ces deux champs
    # à leur valeur par défaut (False/'') — comportement historique intact.
    # Un avoir créé depuis l'action `retour-client` pose `restocke=True` quand
    # la marchandise a été remise en stock (option — un retour peut choisir de
    # NE PAS re-stocker, ex. produit défectueux détruit) et exige un motif.
    restocke = models.BooleanField(default=False)
    motif_retour = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        verbose_name = 'Avoir'
        verbose_name_plural = 'Avoirs'
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
        """Ventilation TVA par taux — même logique exacte que Facture.

        DC23 — délègue au selector unique ``tva_buckets``."""
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


class LigneAvoir(models.Model):
    avoir = models.ForeignKey(
        Avoir, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lignes_avoir')
    designation = models.CharField(max_length=255)
    quantite = models.DecimalField(max_digits=10, decimal_places=2)
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    remise = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    taux_tva = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = 'Ligne d\'avoir'
        verbose_name_plural = 'Lignes d\'avoir'

    def clean(self):
        # DC10 — lien produit RENFORCÉ : une NOUVELLE ligne d'avoir doit porter
        # son produit (snapshot fort du lien). Le FK reste nullable au niveau
        # base (SET_NULL) pour ne pas invalider les lignes historiques dont le
        # produit a pu être supprimé ; la contrainte est appliquée au niveau
        # APPLICATIF, uniquement à la création (self._state.adding).
        super().clean()
        from django.core.exceptions import ValidationError
        if getattr(self, '_state', None) and self._state.adding \
                and self.produit_id is None:
            raise ValidationError(
                {'produit': "Le produit est requis sur une nouvelle ligne "
                            "d'avoir (note de crédit)."})

    @property
    def total_ht(self):
        return self.quantite * self.prix_unitaire * (1 - self.remise / 100)

    @property
    def taux_tva_effectif(self):
        return self.taux_tva if self.taux_tva is not None else self.avoir.taux_tva


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
        Facture, on_delete=models.PROTECT, related_name='notes_debit')
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
        Facture, on_delete=models.CASCADE, related_name='retenues_subies')
    # Paiement qui a déclenché la constatation de la retenue (le paiement
    # partiel + la retenue soldent ensemble la facture). Optionnel : la
    # retenue peut être saisie avant ou après le paiement lui-même.
    paiement = models.ForeignKey(
        Paiement, on_delete=models.SET_NULL, null=True, blank=True,
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
        Facture, on_delete=models.CASCADE, related_name='promesses_paiement')
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


class FollowupLevel(models.Model):
    """Niveau de relance configurable (J+7 rappel, J+15 relance, J+30 ferme…).

    `delai_jours` = nombre de jours de retard à partir duquel ce niveau
    s'applique. Le niveau courant d'une facture est le plus élevé dont le
    seuil est atteint. Modifiable par l'admin dans Paramètres."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='followup_levels')
    ordre = models.PositiveIntegerField(default=0)
    nom = models.CharField(max_length=120)
    delai_jours = models.PositiveIntegerField(default=7)
    message = models.TextField(blank=True, default='')
    # XFAC6 — pénalités/intérêts de retard (loi 69-21, intérêts moratoires
    # B2B) : taux annuel (%) + frais fixes (MAD), tous deux nullable/défaut 0
    # → comportement historique BYTE-IDENTIQUE (aucune pénalité) tant qu'ils
    # ne sont pas paramétrés. Purement INDICATIF sur la lettre de relance tant
    # que la facturation optionnelle n'est pas déclenchée.
    taux_interet_annuel = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, default=0)
    frais_fixes = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, default=0)

    # XFAC8 — canal par niveau de relance (Odoo 19/D365 : courtoisie email →
    # ferme WhatsApp → mise en demeure courrier → niveau « appel » qui crée
    # une tâche téléphonique). Défaut EMAIL → comportement historique inchangé.
    class Canal(models.TextChoices):
        EMAIL = 'email', 'Email'
        WHATSAPP = 'whatsapp', 'WhatsApp'
        COURRIER = 'courrier', 'Courrier'
        APPEL = 'appel', 'Appel (tâche téléphonique)'

    canal = models.CharField(
        max_length=10, choices=Canal.choices, default=Canal.EMAIL)

    class Meta:
        ordering = ['delai_jours', 'ordre']
        verbose_name = 'Niveau de relance'

    def __str__(self):
        return f'{self.nom} (J+{self.delai_jours})'

    def calcul_penalite(self, montant_du, jours_retard):
        """XFAC6 — pénalité de retard = montant dû × taux annuel × jours/365 +
        frais fixes. Taux/frais à 0 (ou NULL) → renvoie 0 (comportement
        actuel byte-identique). N'affecte JAMAIS ``montant_du`` — purement
        indicatif tant que non facturé."""
        from decimal import Decimal, ROUND_HALF_UP
        taux = self.taux_interet_annuel or Decimal('0')
        frais = self.frais_fixes or Decimal('0')
        if taux <= 0 and frais <= 0:
            return Decimal('0.00')
        montant_du = Decimal(montant_du or 0)
        jours = max(int(jours_retard or 0), 0)
        interet = montant_du * Decimal(taux) / Decimal('100') * \
            Decimal(jours) / Decimal('365')
        return (interet + Decimal(frais)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP)


class RelanceLog(models.Model):
    """Trace d'une relance effectuée sur une facture (consigne, jamais envoi)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='relance_logs')
    facture = models.ForeignKey(
        Facture, on_delete=models.CASCADE, related_name='relances')
    niveau = models.PositiveIntegerField(null=True, blank=True)
    niveau_nom = models.CharField(max_length=120, blank=True, default='')
    note = models.TextField(blank=True, default='')
    # XFAC8 — canal réellement utilisé pour CETTE relance (trace, pas config).
    # Vide = comportement historique (email implicite avant XFAC8).
    canal = models.CharField(max_length=10, blank=True, default='')
    # Canal courrier : clé MinIO de la lettre PDF générée en file d'attente
    # d'impression (jamais d'envoi postal automatisé — impression manuelle).
    courrier_pdf_key = models.CharField(max_length=500, blank=True, default='')
    date = models.DateField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='relances_effectuees')

    class Meta:
        ordering = ['-date', '-id']
        verbose_name = 'Relance'

    def __str__(self):
        return f'Relance {self.facture.reference} — {self.date}'


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
        Facture, on_delete=models.CASCADE, null=True, blank=True,
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
        Facture, on_delete=models.CASCADE, null=True, blank=True,
        related_name='share_links')
    # QS3 — lien tokenisé vers le PDF d'un Bon de Commande FOURNISSEUR (stock).
    # String-FK (ventes → stock) : ventes n'importe pas les modèles de stock.
    # Additif/nullable : les liens existants (devis/facture) sont inchangés. Ce
    # PDF montre légitimement les PRIX D'ACHAT au FOURNISSEUR — le jeton reste
    # imprévisible + expirant, et le lien n'est JAMAIS exposé dans l'UI client.
    bon_commande_fournisseur = models.ForeignKey(
        'stock.BonCommandeFournisseur', on_delete=models.CASCADE,
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
        Facture, on_delete=models.CASCADE, related_name='payment_links')
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
        Paiement, on_delete=models.SET_NULL, null=True, blank=True,
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
        Paiement, on_delete=models.PROTECT,
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
        Paiement, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tentatives_debit_mandat')
    date_tentative = models.DateTimeField(auto_now_add=True)
    prochaine_retentative = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'Tentative de débit (mandat)'
        verbose_name_plural = 'Tentatives de débit (mandat)'
        ordering = ['-date_tentative']

    def __str__(self):
        return f'{self.mandat_id} / {self.periode} — {self.statut}'
