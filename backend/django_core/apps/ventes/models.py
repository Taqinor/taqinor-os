from django.db import models
from django.conf import settings
from apps.crm.models import Client
from apps.stock.models import Produit


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
        Client,
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
    prix_cible_kwc = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)

    # ── Révisions / versionnage (T10) — additif, tout optionnel ──
    # Une révision pointe vers le devis source via `revision_de` ; le source
    # expose ses révisions via `revisions` (reverse). `version` part à 1.
    # SET_NULL : supprimer un source ne casse jamais la révision.
    revision_de = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='revisions',
    )
    version = models.PositiveIntegerField(default=1)

    # ── Garde d'approbation de remise (T17) — additif, tout optionnel ──
    # Renseignés quand un responsable/admin approuve une remise au-dessus du
    # seuil société. NULL = jamais approuvé (cas par défaut).
    remise_approuvee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='remises_devis_approuvees',
    )
    remise_approuvee_le = models.DateTimeField(null=True, blank=True)

    # ── Acceptation client « Bon pour accord » (N9) — additif, tout optionnel ──
    # Capture explicite de l'acceptation : c'est CE geste qui déclenche la
    # possibilité de créer le chantier (le flux chantier-depuis-devis exige
    # déjà statut == 'accepte'). `accepte_par_nom` = nom CLIENT saisi à la main ;
    # `accepte_par_user` = membre du staff qui a consigné l'acceptation.
    date_acceptation = models.DateField(null=True, blank=True)
    accepte_par_nom = models.CharField(max_length=255, blank=True, default='')
    accepte_par_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='devis_acceptes',
    )
    bon_pour_accord = models.BooleanField(default=False)

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
        # TVA par ligne quand un taux de ligne existe, sinon taux du devis
        # (anciens devis : toutes lignes NULL → strictement l'ancien calcul).
        return sum(
            ligne.total_ht * (ligne.taux_tva_effectif / 100)
            for ligne in self.lignes.all()
        )

    @property
    def total_ttc(self):
        return self.total_ht + self.total_tva

    # ── Expiration calculée À LA VOLÉE (T7a) ──
    # Jamais stockée, jamais persistée : le statut du devis et le funnel CRM
    # ne bougent pas. La validité = date de création + N jours (réglage société
    # `quote_validity_days`, défaut 30). On privilégie `date_validite` si elle a
    # été saisie explicitement sur le devis, sinon on la calcule.
    @property
    def date_expiration(self):
        from datetime import timedelta
        if self.date_validite is not None:
            return self.date_validite
        if self.date_creation is None:
            return None
        from .utils.company_settings import quote_validity_days
        days = quote_validity_days(self.company)
        return (self.date_creation + timedelta(days=days)).date()

    @property
    def est_expire(self):
        exp = self.date_expiration
        if exp is None:
            return False
        return timezone.now().date() > exp


class LigneDevis(models.Model):
    devis = models.ForeignKey(
        Devis, on_delete=models.CASCADE, related_name='lignes'
    )
    produit = models.ForeignKey(
        Produit,
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
        Client,
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
        Client,
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
    # ── Conformité Article 145 CGI (N30/N11) — additif, tout optionnel ──
    # date_livraison = date de la livraison/prestation (mention obligatoire) ;
    # par défaut, reprise de la mise en service du chantier lié à la création.
    # conditions_paiement = conditions et mode de règlement (mention obligatoire)
    # — défaut vide pour ne RIEN changer au comportement existant.
    date_livraison = models.DateField(null=True, blank=True)
    conditions_paiement = models.TextField(blank=True, default='')
    taux_tva = models.DecimalField(
        max_digits=5, decimal_places=2, default=20.00
    )
    remise_globale = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    note = models.TextField(blank=True, null=True)
    # ── Relances / recouvrement (workstream E) — additif ──
    # Date de la prochaine relance prévue (posée à l'enregistrement d'une
    # relance) ; exclu_relances retire la facture des listes d'impayés.
    prochaine_relance = models.DateField(null=True, blank=True)
    exclu_relances = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='factures_creees',
    )
    fichier_pdf = models.CharField(
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

    @property
    def mentions_manquantes(self):
        """Mentions obligatoires manquantes (Article 145 CGI marocain).

        AVERTISSEMENT seulement : renvoie la liste des mentions absentes — ne
        bloque JAMAIS l'émission. Couvre l'identité + IF/ICE/RC du vendeur,
        l'identité du client (+ ICE en B2B), le numéro séquentiel, la date
        d'émission, la date de livraison/prestation, le détail des lignes
        (désignation/qté/PU HT/taux TVA/total HT), les totaux HT/TVA/TTC, et
        les conditions + mode de paiement.
        """
        manquantes = []
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.get(company=self.company)

        # Identité + identifiants légaux du vendeur
        if not (profile.nom or '').strip():
            manquantes.append("Identité du vendeur (raison sociale)")
        if not (getattr(profile, 'identifiant_fiscal', '') or '').strip():
            manquantes.append("Identifiant fiscal (IF) du vendeur")
        if not (getattr(profile, 'ice', '') or '').strip():
            manquantes.append("ICE du vendeur")
        if not (getattr(profile, 'rc', '') or '').strip():
            manquantes.append("Registre de commerce (RC) du vendeur")

        # Identité du client (+ ICE pour un client professionnel/B2B)
        client = self.client
        if client is None or not (client.nom or '').strip():
            manquantes.append("Identité du client")
        elif self._client_est_pro(client) and \
                not (getattr(client, 'ice', '') or '').strip():
            manquantes.append("ICE du client (client professionnel)")

        # Numéro séquentiel + date d'émission
        if not (self.reference or '').strip():
            manquantes.append("Numéro de facture séquentiel")
        if self.date_emission is None:
            manquantes.append("Date d'émission")

        # Date de livraison / prestation
        if self.date_livraison is None:
            manquantes.append("Date de livraison / prestation")

        # Détail des lignes (désignation, qté, PU HT, taux TVA, total HT)
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

        # Conditions + mode de paiement
        if not (self.conditions_paiement or '').strip():
            manquantes.append("Conditions et mode de paiement")

        return manquantes

    @staticmethod
    def _client_est_pro(client):
        """B2B : un client est « professionnel » s'il est de type Entreprise ou
        s'il porte un marqueur entreprise (ICE, IF ou RC renseigné)."""
        type_client = (getattr(client, 'type_client', '') or '').lower()
        if type_client == 'entreprise':
            return True
        for attr in ('ice', 'if_fiscal', 'rc'):
            if (getattr(client, attr, '') or '').strip():
                return True
        return False


class LigneFacture(models.Model):
    facture = models.ForeignKey(
        Facture, on_delete=models.CASCADE, related_name='lignes'
    )
    produit = models.ForeignKey(
        Produit,
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
        Client, on_delete=models.PROTECT, related_name='avoirs')
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
        Produit, on_delete=models.SET_NULL, null=True, blank=True,
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
