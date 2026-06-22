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
        """
        from decimal import Decimal, ROUND_HALF_UP
        lignes = list(self.lignes.all())
        buckets = {}
        for ligne in lignes:
            # Coercition Decimal du taux : un taux non encore relu de la base
            # (défaut modèle) peut être un float — on garde des Decimals partout
            # pour ne jamais mélanger Decimal et float dans le calcul.
            rate = Decimal(str(ligne.taux_tva_effectif))
            buckets[rate] = buckets.get(rate, Decimal('0')) + Decimal(ligne.total_ht)
        if len(buckets) <= 1:
            rate = next(iter(buckets), Decimal(str(self.taux_tva)))
            base = sum((Decimal(li.total_ht) for li in lignes), Decimal('0'))
            return [{'taux': rate, 'base_ht': base,
                     'montant': base * rate / Decimal('100')}]

        def q(x):
            return x.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return [
            {'taux': rate, 'base_ht': q(buckets[rate]),
             'montant': q(buckets[rate] * rate / Decimal('100'))}
            for rate in sorted(buckets)
        ]

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

    class Meta:
        verbose_name = 'Facture'
        verbose_name_plural = 'Factures'
        ordering = ['-date_emission']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference

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
        """
        from decimal import Decimal, ROUND_HALF_UP
        # Facture de tranche (acompte) : montant figé, un seul panier.
        if self.montant_tva is not None:
            return [{'taux': self.taux_tva, 'base_ht': self.total_ht,
                     'montant': self.montant_tva}]
        lignes = list(self.lignes.all())
        buckets = {}
        for ligne in lignes:
            rate = ligne.taux_tva_effectif
            buckets[rate] = buckets.get(rate, Decimal('0')) + Decimal(ligne.total_ht)
        if len(buckets) <= 1:
            # Mono-taux : formule d'origine (HT × taux), aucun arrondi par
            # panier → figures historiques strictement identiques.
            rate = next(iter(buckets), self.taux_tva)
            base = sum((Decimal(li.total_ht) for li in lignes), Decimal('0'))
            return [{'taux': rate, 'base_ht': base,
                     'montant': base * rate / Decimal('100')}]

        def q(x):
            return x.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return [
            {'taux': rate, 'base_ht': q(buckets[rate]),
             'montant': q(buckets[rate] * rate / Decimal('100'))}
            for rate in sorted(buckets)
        ]

    @property
    def total_ttc(self):
        if self.montant_ttc is not None:
            return self.montant_ttc
        return self.total_ht + self.total_tva

    @property
    def montant_paye(self):
        """Somme des paiements enregistrés sur cette facture."""
        from decimal import Decimal
        return sum((p.montant for p in self.paiements.all()), Decimal('0'))

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
    def montant_du(self):
        """Reste à payer (TTC − payé − avoirs), jamais négatif."""
        from decimal import Decimal
        reste = self.total_ttc - self.montant_paye - self.avoirs_total
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
    """Paiement encaissé sur une facture (enregistrement MANUEL).

    Une facture peut recevoir plusieurs paiements (acompte partiel, solde…).
    Le reste à payer d'une facture et le solde d'un devis se déduisent de ces
    lignes — source unique du « payé ».
    """
    class Mode(models.TextChoices):
        ESPECES = 'especes', 'Espèces'
        VIREMENT = 'virement', 'Virement'
        CHEQUE = 'cheque', 'Chèque'
        CARTE = 'carte', 'Carte bancaire'
        PRELEVEMENT = 'prelevement', 'Prélèvement'
        AUTRE = 'autre', 'Autre'

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
    )
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    date_paiement = models.DateField()
    mode = models.CharField(
        max_length=20, choices=Mode.choices, default=Mode.VIREMENT,
    )
    reference = models.CharField(max_length=120, blank=True, null=True)
    note = models.TextField(blank=True, null=True)
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
        return f'{self.montant} MAD — {self.facture.reference}'


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
        """Ventilation TVA par taux — même logique exacte que Facture."""
        from decimal import Decimal, ROUND_HALF_UP
        if self.montant_tva is not None:
            return [{'taux': self.taux_tva, 'base_ht': self.total_ht,
                     'montant': self.montant_tva}]
        lignes = list(self.lignes.all())
        buckets = {}
        for ligne in lignes:
            rate = ligne.taux_tva_effectif
            buckets[rate] = buckets.get(rate, Decimal('0')) + Decimal(ligne.total_ht)
        if len(buckets) <= 1:
            rate = next(iter(buckets), self.taux_tva)
            base = sum((Decimal(li.total_ht) for li in lignes), Decimal('0'))
            return [{'taux': rate, 'base_ht': base,
                     'montant': base * rate / Decimal('100')}]

        def q(x):
            return x.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return [
            {'taux': rate, 'base_ht': q(buckets[rate]),
             'montant': q(buckets[rate] * rate / Decimal('100'))}
            for rate in sorted(buckets)
        ]

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

    @property
    def total_ht(self):
        return self.quantite * self.prix_unitaire * (1 - self.remise / 100)

    @property
    def taux_tva_effectif(self):
        return self.taux_tva if self.taux_tva is not None else self.avoir.taux_tva


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

    class Meta:
        ordering = ['delai_jours', 'ordre']
        verbose_name = 'Niveau de relance'

    def __str__(self):
        return f'{self.nom} (J+{self.delai_jours})'


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
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_default_share_expiry)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['token'])]

    def __str__(self):
        cible = self.devis_id and 'devis' or 'facture'
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
