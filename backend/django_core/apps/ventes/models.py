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
        return self.total_ht * (self.taux_tva / 100)

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
    def montant_du(self):
        """Reste à payer sur cette facture (TTC − payé), jamais négatif."""
        from decimal import Decimal
        reste = self.total_ttc - self.montant_paye
        return reste if reste > 0 else Decimal('0')


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

    class Meta:
        verbose_name = 'Ligne de Facture'
        verbose_name_plural = 'Lignes de Facture'

    @property
    def total_ht(self):
        return (
            self.quantite * self.prix_unitaire * (1 - self.remise / 100)
        )


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
