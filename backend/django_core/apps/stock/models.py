from django.db import models
from django.conf import settings


class Categorie(models.Model):
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='categories',
    )
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    ordre = models.PositiveSmallIntegerField(
        default=100,
        help_text="Ordre d'affichage délibéré (plus petit = plus haut).")

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        unique_together = [('company', 'nom')]
        ordering = ['ordre', 'nom']

    def __str__(self):
        return self.nom


class Fournisseur(models.Model):
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='fournisseurs',
    )
    nom = models.CharField(max_length=255)
    contact_personne = models.CharField(
        max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    adresse = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Fournisseur"
        verbose_name_plural = "Fournisseurs"

    def __str__(self):
        return self.nom


class Marque(models.Model):
    """Marque produit gérée (Paramètres → Stock). `Produit.marque` reste un
    texte libre (compat ascendante) ; cette liste sert de référentiel + ajout
    libre dans le formulaire produit. Additif — aucune migration destructive."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='marques')
    nom = models.CharField(max_length=100)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['nom']
        unique_together = [('company', 'nom')]
        verbose_name = 'Marque'

    def __str__(self):
        return self.nom


class Produit(models.Model):
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='produits',
    )
    nom = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    sku = models.CharField(max_length=50, blank=True, null=True)
    prix_achat = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    prix_vente = models.DecimalField(max_digits=10, decimal_places=2)
    quantite_stock = models.IntegerField(default=0)
    seuil_alerte = models.IntegerField(default=0)
    categorie = models.ForeignKey(
        Categorie,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='produits'
    )
    fournisseur = models.ForeignKey(
        Fournisseur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='produits'
    )
    tva = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_archived = models.BooleanField(default=False)

    # ── Fiche commerciale (devis PDF riches, 2026-06) — tout optionnel ──
    marque = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(
        blank=True, null=True,
        help_text='Lignes descriptives affichées sous la désignation dans les PDF (une par ligne).')
    garantie = models.CharField(
        max_length=255, blank=True, null=True,
        help_text='Texte garantie constructeur / performance.')

    # ── Durée de garantie structurée (alimente les horloges de garantie du
    #    parc d'équipements). Numérique, en MOIS, optionnelle : un produit sans
    #    durée renseignée donne « garantie non renseignée » sur son équipement
    #    (même logique que les pompes sans prix). Le texte `garantie` ci-dessus
    #    reste en place et inchangé. Aucune durée n'est inventée par le code. ──
    garantie_mois = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Garantie équipement en mois (laisser vide si non renseignée).')
    garantie_production_mois = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Garantie production (panneaux) en mois — souvent 300 à 360.')

    # ── Spécifications pompage solaire (mode Agricole) ──
    pompe_cv = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text='Puissance pompe en chevaux (CV).')
    hmt_m = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Hauteur manométrique totale max (m).')
    debit_m3j = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Débit max indicatif (m³/jour).')
    pompe_kw = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text='Puissance nominale (kW) — pompes ET variateurs.')
    tension_v = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Tension nominale (V) : 220 ou 380.')
    courbe_pompe = models.JSONField(
        null=True, blank=True,
        help_text="Courbe de performance constructeur : "
                  '{"debits_m3h": [0, 12, ...], "hmt_m": [91, 85, ...]} '
                  '(HMT délivrée à chaque débit).')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    # Champs personnalisés (T11) — valeurs indexées par CustomFieldDef.code.
    custom_data = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name = "Produit"
        verbose_name_plural = "Produits"
        unique_together = [('company', 'sku')]

    def __str__(self):
        return self.nom


class MouvementStock(models.Model):
    """Entrées / Sorties / Transferts de stock avec traçabilité complète."""

    class TypeMouvement(models.TextChoices):
        ENTREE = 'entree', 'Entrée'
        SORTIE = 'sortie', 'Sortie'
        TRANSFERT = 'transfert', 'Transfert'
        AJUSTEMENT = 'ajustement', 'Ajustement'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='mouvements_stock',
    )
    produit = models.ForeignKey(
        Produit,
        on_delete=models.PROTECT,
        related_name='mouvements'
    )
    type_mouvement = models.CharField(
        max_length=20,
        choices=TypeMouvement.choices,
    )
    quantite = models.IntegerField()
    quantite_avant = models.IntegerField()
    quantite_apres = models.IntegerField()
    reference = models.CharField(max_length=100, blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mouvements_stock'
    )
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mouvement de Stock"
        verbose_name_plural = "Mouvements de Stock"
        ordering = ['-date']

    def __str__(self):
        return f"{self.type_mouvement} | {self.produit.nom} | {self.quantite}"


class EmplacementStock(models.Model):
    """N15 — Emplacement de stock (dépôt principal, camionnette, dépôt secondaire…).

    Le stock TOTAL d'un produit reste `Produit.quantite_stock` (canonique,
    inchangé : réceptions, ventes, inventaire continuent de l'alimenter). Cette
    couche se contente de VENTILER ce total entre emplacements. L'emplacement
    PRINCIPAL détient le reste (total − somme des autres emplacements), si bien
    que tout le stock existant est par défaut au dépôt principal et que le
    comportement actuel est strictement inchangé. Entièrement additif.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='emplacements_stock')
    nom = models.CharField(max_length=100)
    is_principal = models.BooleanField(
        default=False,
        help_text='Le dépôt principal détient le stock non ventilé (un seul '
                  'par société).')
    ordre = models.PositiveSmallIntegerField(default=100)
    archived = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Emplacement de stock'
        verbose_name_plural = 'Emplacements de stock'
        unique_together = [('company', 'nom')]
        ordering = ['-is_principal', 'ordre', 'nom']

    def __str__(self):
        return self.nom


class StockEmplacement(models.Model):
    """Quantité d'un produit dans un emplacement NON principal.

    La quantité de l'emplacement principal n'est jamais stockée : elle est
    DÉRIVÉE (total − somme des emplacements non principaux) pour que le total
    canonique et la ventilation ne puissent pas diverger.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='stocks_emplacement')
    produit = models.ForeignKey(
        Produit, on_delete=models.CASCADE, related_name='stocks_emplacement')
    emplacement = models.ForeignKey(
        EmplacementStock, on_delete=models.CASCADE, related_name='stocks')
    quantite = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Stock par emplacement"
        verbose_name_plural = "Stocks par emplacement"
        unique_together = [('produit', 'emplacement')]

    def __str__(self):
        return f'{self.produit_id} @ {self.emplacement_id} = {self.quantite}'


class TransfertStock(models.Model):
    """Le « transfer record » de N15 : déplace une quantité d'un produit d'un
    emplacement source vers un emplacement destination.

    Ne modifie JAMAIS le total `Produit.quantite_stock` — seule la ventilation
    par emplacement change. Tracé complet (qui / quand)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='transferts_stock')
    produit = models.ForeignKey(
        Produit, on_delete=models.PROTECT, related_name='transferts')
    source = models.ForeignKey(
        EmplacementStock, on_delete=models.PROTECT,
        related_name='transferts_sortants')
    destination = models.ForeignKey(
        EmplacementStock, on_delete=models.PROTECT,
        related_name='transferts_entrants')
    quantite = models.PositiveIntegerField()
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transferts_stock')
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Transfert de stock'
        verbose_name_plural = 'Transferts de stock'
        ordering = ['-date']

    def __str__(self):
        return (f'{self.produit_id}: {self.quantite} '
                f'{self.source_id}→{self.destination_id}')


class RetourFournisseur(models.Model):
    """N19 — retour fournisseur (articles défectueux / erronés).

    À la validation, le stock est DÉCRÉMENTÉ via MouvementStock (type SORTIE),
    exactement comme partout ailleurs. Peut être lié au bon de commande
    fournisseur d'origine. Usage INTERNE (prix d'achat jamais client-facing).
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        VALIDE = 'valide', 'Validé'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='retours_fournisseur')
    reference = models.CharField(max_length=50)
    fournisseur = models.ForeignKey(
        Fournisseur, on_delete=models.PROTECT, related_name='retours')
    bon_commande = models.ForeignKey(
        'BonCommandeFournisseur', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='retours')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    motif = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='retours_fournisseur')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Retour fournisseur'
        verbose_name_plural = 'Retours fournisseur'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference


class LigneRetourFournisseur(models.Model):
    """Ligne d'un retour fournisseur : SKU, quantité retournée, motif."""
    retour = models.ForeignKey(
        RetourFournisseur, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        Produit, on_delete=models.PROTECT,
        related_name='lignes_retour_fournisseur')
    quantite = models.IntegerField()
    motif = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = 'Ligne de retour fournisseur'
        verbose_name_plural = 'Lignes de retour fournisseur'

    def __str__(self):
        return f'{self.produit_id} × {self.quantite}'


class PrixFournisseur(models.Model):
    """N17 — prix d'achat d'un produit chez un fournisseur donné.

    Un produit peut avoir plusieurs fournisseurs avec des prix différents ;
    on garde le prix d'achat (INTERNE — jamais client-facing) et la date du
    dernier achat. Sert à proposer le fournisseur le moins cher au moment de
    rédiger un bon de commande. La date du dernier achat est mise à jour
    automatiquement à la réception d'un BCF. Additif."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='prix_fournisseurs')
    produit = models.ForeignKey(
        Produit, on_delete=models.CASCADE, related_name='prix_fournisseurs')
    fournisseur = models.ForeignKey(
        Fournisseur, on_delete=models.CASCADE, related_name='prix_produits')
    # Prix d'ACHAT — donnée INTERNE, jamais sur un document client.
    prix_achat = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date_dernier_achat = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Prix fournisseur"
        verbose_name_plural = "Prix fournisseurs"
        unique_together = [('produit', 'fournisseur')]
        ordering = ['prix_achat']

    def __str__(self):
        return f'{self.produit_id} @ {self.fournisseur_id} = {self.prix_achat}'


class BonCommandeFournisseur(models.Model):
    """Bon de commande FOURNISSEUR (achat / approvisionnement) — N12.

    À NE PAS confondre avec `ventes.BonCommande`, qui est un bon de commande
    CLIENT lié à un devis. Celui-ci est un document d'ACHAT : il liste les
    références (SKU) commandées à un fournisseur, avec leurs PRIX D'ACHAT
    (INTERNES — jamais exposés sur un document client).

    À la réception (totale ou partielle), le stock est INCRÉMENTÉ exactement
    comme partout ailleurs : via `MouvementStock` (type ENTREE). Aucun
    mécanisme parallèle.
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        ENVOYE = 'envoye', 'Envoyé'
        RECU = 'recu', 'Reçu'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='bons_commande_fournisseur',
    )
    reference = models.CharField(max_length=50)
    fournisseur = models.ForeignKey(
        Fournisseur,
        on_delete=models.PROTECT,
        related_name='bons_commande',
    )
    statut = models.CharField(
        max_length=20,
        choices=Statut.choices,
        default=Statut.BROUILLON,
    )
    date_commande = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bons_commande_fournisseur',
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Bon de commande fournisseur'
        verbose_name_plural = 'Bons de commande fournisseur'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference

    @property
    def total_achat(self):
        """Total HT d'achat (INTERNE — jamais sur un document client)."""
        return sum((ligne.total_achat for ligne in self.lignes.all()), 0)

    @property
    def est_entierement_recu(self):
        lignes = list(self.lignes.all())
        return bool(lignes) and all(
            ligne.quantite_recue >= ligne.quantite for ligne in lignes
        )


class LigneBonCommandeFournisseur(models.Model):
    """Ligne d'un bon de commande fournisseur : SKU, quantité, prix d'achat
    unitaire (INTERNE) et quantité déjà reçue (réceptions partielles)."""

    bon_commande = models.ForeignKey(
        BonCommandeFournisseur,
        on_delete=models.CASCADE,
        related_name='lignes',
    )
    produit = models.ForeignKey(
        Produit,
        on_delete=models.PROTECT,
        related_name='lignes_bon_commande_fournisseur',
    )
    quantite = models.IntegerField()
    # Prix d'ACHAT unitaire — donnée INTERNE. N'apparaît JAMAIS sur un document
    # destiné au client (devis, facture, BC client).
    prix_achat_unitaire = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
    )
    quantite_recue = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Ligne de bon de commande fournisseur'
        verbose_name_plural = 'Lignes de bon de commande fournisseur'

    def __str__(self):
        return f'{self.produit_id} × {self.quantite}'

    @property
    def quantite_restante(self):
        return max(self.quantite - self.quantite_recue, 0)

    @property
    def total_achat(self):
        return self.quantite * self.prix_achat_unitaire
