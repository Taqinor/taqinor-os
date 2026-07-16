from django.db import models
from django.conf import settings

# ODX17 — App Facturation, étape 1 (modèles, state-only).
#
# Ces modèles vivaient dans ``apps.ventes.models`` (Facture, LigneFacture,
# Paiement, Avoir, LigneAvoir, FollowupLevel, RelanceLog). Ils sont déplacés
# ICI en préservant à l'IDENTIQUE leurs tables physiques
# (``db_table = 'ventes_<model>'``) via des migrations
# ``SeparateDatabaseAndState`` (state-only, zéro SQL) — même recette que
# ODX9/ODX11/ODX12/ODX13. ``apps.ventes.models`` garde un shim de ré-export
# (``from apps.facturation.models import Facture, ...``) pour tout le code
# existant (générer-facture, échéanciers, reporting, compta, publicapi…).
#
# M1 — cross-app FKs use Django's lazy "app.Model" string form so this module
# imports no sibling app's models at load time. Facture/LigneFacture
# référencent Devis/BonCommande (restés dans ``apps.ventes``) en string-FK
# ('ventes.Devis', 'ventes.BonCommande') ; les FKs vers Client/Lead restent
# telles quelles ('crm.Client', 'crm.Lead').


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
        'ventes.BonCommande',
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
        'ventes.Devis',
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
    # ── ARC24 — référentiel des conditions de paiement (additif, optionnel) ──
    # FK nullable (string-FK — jamais d'import de apps.parametres.models ici)
    # vers parametres.ConditionPaiement : SOURCE du libellé par défaut. Le
    # TextField ``conditions_paiement`` ci-dessus reste MAÎTRE (surchargeable) ;
    # cette FK ne fait que tracer la condition référentielle choisie. Vide =
    # comportement historique inchangé (texte libre seul).
    condition_paiement_ref = models.ForeignKey(
        'parametres.ConditionPaiement',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='factures',
        verbose_name='Condition de paiement (référentiel)',
        help_text="Condition du référentiel Paramètres — source du libellé par "
                  "défaut. Le texte libre reste surchargeable.")
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
        # ZFAC11 — écart d'arrondi de caisse (règlement espèces arrondi au pas
        # configuré par la société) ; tracé comme un abandon de résiduel, jamais
        # silencieux. Le PDF facture legacy affiche alors « Arrondi espèces ».
        ARRONDI_CAISSE = 'arrondi_caisse', 'Arrondi espèces'

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

    # VX98 — fraîcheur : horodatage (auto_now) + dernier auteur d'une
    # modification (posé server-side dans perform_update, jamais accepté du
    # corps). Alimente la puce « modifié par X il y a N min » (silencieuse si
    # NULL ou si c'est l'utilisateur courant). updated_by suit le pattern
    # created_by ; NULL sur les factures antérieures à la migration.
    updated_at = models.DateTimeField(auto_now=True, null=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='factures_modifiees',
    )

    class Meta:
        verbose_name = 'Facture'
        verbose_name_plural = 'Factures'
        db_table = 'ventes_facture'
        ordering = ['-date_emission']
        unique_together = [('company', 'reference')]
        # SCA39 — index chemin-de-l'argent (sous-ensemble Facture de NTPLT20).
        # (company, statut) couvre les listes filtrées par statut (impayés,
        # en_retard…) ; (company, date_emission) couvre la liste par défaut
        # (scopée société, triée -date_emission). Posés SANS verrou d'écriture
        # bloquant via AddIndexConcurrently + lock_timeout (YOPSB6).
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='ventes_fact_co_statut_idx'),
            models.Index(
                fields=['company', 'date_emission'],
                name='ventes_fact_co_dateemis_idx'),
        ]

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
        # ── ARC24 — défaut du libellé de conditions de paiement à la CRÉATION ──
        # Quand une condition référentielle est reliée mais que le texte libre
        # (mention N11) est vide, on l'initialise depuis le libellé du
        # référentiel. UNIQUEMENT à la création (self.pk None) et si le texte est
        # vide : le texte libre reste MAÎTRE et surchargeable, et un document
        # existant n'est JAMAIS réécrit (immutabilité — règle #4).
        if self.pk is None and self.condition_paiement_ref_id is not None \
                and not (self.conditions_paiement or '').strip():
            libelle = getattr(self.condition_paiement_ref, 'libelle', '')
            if libelle:
                self.conditions_paiement = libelle
        super().save(*args, **kwargs)

    @property
    def _remise_globale_active(self):
        """QX1 — vrai si une remise globale doit être appliquée aux totaux.

        Ne s'applique JAMAIS à une facture de tranche (montants figés) et
        seulement si ``remise_globale`` > 0. Une facture sans remise (défaut 0)
        garde donc la sémantique historique « total = somme des lignes »,
        byte-identique."""
        from decimal import Decimal
        if self.montant_ht is not None:
            return False
        return (self.remise_globale or Decimal('0')) > 0

    @property
    def total_ht(self):
        # Tranche d'échéancier : montant figé. Sinon : somme des lignes.
        if self.montant_ht is not None:
            return self.montant_ht
        if self._remise_globale_active:
            # QX1 — HT NET (remise globale appliquée) via la chaîne canonique
            # partagée avec le devis/l'échéancier (centime-exact).
            from apps.ventes.selectors import _canonical_totaux
            return _canonical_totaux(
                self.lignes.all(),
                remise_globale_pct=self.remise_globale,
                fallback_taux=self.taux_tva)['ht_net']
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

        QX1 — quand une remise globale est active, la TVA est calculée sur le HT
        NET via la même chaîne canonique que le devis (``_canonical_totaux``),
        pour que devis/BC/facture s'accordent au centime.
        """
        if self._remise_globale_active:
            from apps.ventes.selectors import _canonical_totaux
            return _canonical_totaux(
                self.lignes.all(),
                remise_globale_pct=self.remise_globale,
                fallback_taux=self.taux_tva)['tva_par_taux']
        from apps.ventes.selectors import tva_buckets
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
        if self._remise_globale_active:
            from apps.ventes.selectors import _canonical_totaux
            return _canonical_totaux(
                self.lignes.all(),
                remise_globale_pct=self.remise_globale,
                fallback_taux=self.taux_tva)['ttc']
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
        avoirs − abandon de créance), jamais négatif. ZFAC4 — les notes de
        débit actives AUGMENTENT le reste à payer (symétrique des avoirs) ;
        aucune note de débit → comportement historique strictement inchangé.
        XFAC13 — un abandon de créance (write-off, manuel ou automatique sous
        tolérance) solde le résiduel abandonné ; aucun abandon → comportement
        historique inchangé (abandon_montant vaut 0 par défaut)."""
        from decimal import Decimal
        reste = (self.total_ttc + self.notes_debit_total
                 - self.montant_paye_avec_retenues
                 - self.avoirs_total
                 - (self.abandon_montant or Decimal('0')))
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
        'ventes.Devis', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lignes_facture_consolidee')

    class Meta:
        verbose_name = 'Ligne de Facture'
        verbose_name_plural = 'Lignes de Facture'
        db_table = 'ventes_lignefacture'

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

    # ── SCA45 — champs PROVIDER-AGNOSTIQUES (le « sol » de QJ24/NTSUB) ──
    # Leçon ServiceTitan/Toast : un paiement doit être un objet de registre de
    # première classe DANS le schéma, pas la boîte noire d'un PSP futur. Ces
    # deux champs accueillent une future intégration (CMI/PayZone — QJ24, gated
    # fondateur ; NTSUB1-4 comme moteur d'abonnement) SANS nouveau schéma le
    # jour venu. AUCUNE intégration PSP ici : purement additif.
    #
    # ARCHITECTURE (garde-fou permanent) : un futur webhook PSP ne touchera
    # JAMAIS Facture.statut EN DIRECT — il route par apps.ventes.services
    # (règle #4 + frontières inter-app). Ces colonnes ne font que STOCKER la
    # référence prestataire + la clé d'idempotence, jamais piloter un statut.
    provider_ref = models.CharField(
        max_length=200, null=True, blank=True,
        help_text='Référence du prestataire de paiement (PSP) — vide tant '
                  'qu\'aucune intégration ne renseigne ce paiement.')
    idempotency_key = models.CharField(
        max_length=200, null=True, blank=True,
        help_text='Clé d\'idempotence (déduplication webhook PSP) — unique par '
                  'société quand renseignée.')

    class Meta:
        verbose_name = 'Paiement'
        verbose_name_plural = 'Paiements'
        db_table = 'ventes_paiement'
        ordering = ['-date_paiement', '-date_creation']
        constraints = [
            # SCA45 — la clé d'idempotence est unique PAR SOCIÉTÉ quand elle est
            # renseignée (empêche le double-encaissement d'un même événement PSP
            # rejoué). Les paiements sans clé (saisie manuelle actuelle) sont
            # exclus de la contrainte — comportement historique inchangé.
            models.UniqueConstraint(
                fields=['company', 'idempotency_key'],
                condition=models.Q(idempotency_key__isnull=False)
                & ~models.Q(idempotency_key=''),
                name='uniq_paiement_idempotency_par_societe',
            ),
        ]

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
        db_table = 'ventes_avoir'
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
        from apps.ventes.selectors import tva_buckets
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
        db_table = 'ventes_ligneavoir'

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
        db_table = 'ventes_followuplevel'

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
        db_table = 'ventes_relancelog'

    def __str__(self):
        return f'Relance {self.facture.reference} — {self.date}'
