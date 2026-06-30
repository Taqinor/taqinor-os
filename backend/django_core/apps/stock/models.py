from decimal import Decimal

from django.db import models
from django.conf import settings


class Categorie(models.Model):
    # Tag de TYPE d'équipement optionnel et additif (L579) : permet de filtrer
    # un emplacement (slot) d'équipement de chantier par TYPE indépendamment du
    # libellé free-text de la catégorie (qu'une société peut renommer). Les
    # catégories existantes restent NON typées (None) → comportement inchangé.
    class TypeEquipement(models.TextChoices):
        PANNEAU = 'panneau', 'Panneau'
        ONDULEUR = 'onduleur', 'Onduleur'
        BATTERIE = 'batterie', 'Batterie'
        STRUCTURE = 'structure', 'Structure'
        CABLE = 'cable', 'Câble'
        PROTECTION = 'protection', 'Protection'
        POMPE = 'pompe', 'Pompe'
        VARIATEUR = 'variateur', 'Variateur'
        COMPTEUR = 'compteur', 'Compteur'
        ACCESSOIRE = 'accessoire', 'Accessoire'

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
    type_equipement = models.CharField(
        max_length=20,
        choices=TypeEquipement.choices,
        null=True,
        blank=True,
        help_text="Type d'équipement (optionnel) pour filtrer les slots de "
                  "chantier par TYPE, quel que soit le libellé de la "
                  "catégorie. Vide = non typée (comportement historique).")

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

    # ── DC15 — Identité légale du fournisseur (saisie une seule fois) ─────────
    # ICE / IF / RC / RIB sont les identifiants légaux marocains du fournisseur.
    # Saisis ici une fois, ils sont CONSOMMÉS par les comptes auxiliaires de la
    # comptabilité (DC30), les parties au contrat (DC31), les PDF de facture
    # fournisseur (AP) et les profils sous-traitant — sans jamais re-saisir
    # l'identité ailleurs. Tous optionnels (compat ascendante : aucun
    # fournisseur existant n'est impacté). Aucun montant / prix d'achat ici.
    ice = models.CharField(
        max_length=20, blank=True, null=True,
        help_text="Identifiant Commun de l'Entreprise (ICE).")
    identifiant_fiscal = models.CharField(
        max_length=20, blank=True, null=True,
        help_text='Identifiant Fiscal (IF).')
    rc = models.CharField(
        max_length=40, blank=True, null=True,
        help_text='Numéro du Registre du Commerce (RC).')
    rib = models.CharField(
        max_length=50, blank=True, null=True,
        help_text='RIB / IBAN du fournisseur (règlements AP).')

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

    # ── FG54 — Réapprovisionnement auto ──────────────────────────────────────
    # Quantité cible à recomander quand le stock passe sous seuil_alerte.
    # Si non renseignée, la suggestion de réappro propose seuil_alerte × 2
    # (comportement conservateur par défaut). INTERNE — jamais client-facing.
    quantite_reappro_cible = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Quantité cible à commander lors d\'un réapprovisionnement '
                  '(facultatif ; défaut = seuil_alerte × 2).')

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

    # ── FG62 — Seuils min/max par emplacement ────────────────────────────
    # Permettent de signaler qu'un emplacement non-principal (ex: camionnette)
    # est sous son seuil propre, indépendamment du seuil global du produit.
    # Optionnels : null = pas de seuil défini sur cet emplacement.
    seuil_min = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Seuil minimum de stock pour cet emplacement (optionnel).')
    seuil_max = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Seuil maximum de stock pour cet emplacement (optionnel).')

    class Meta:
        verbose_name = "Stock par emplacement"
        verbose_name_plural = "Stocks par emplacement"
        # ERR93 — `company` ajouté à la contrainte d'unicité (convention
        # company-in-constraint) ; la quantité ventilée ne peut jamais être
        # négative (CheckConstraint additive, sûre sur les données existantes
        # car les gardes de transfert plafonnent déjà au stock disponible).
        unique_together = [('company', 'produit', 'emplacement')]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantite__gte=0),
                name='stockemplacement_quantite_non_negative'),
        ]

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


class ReceptionFournisseur(models.Model):
    """G5 — Réception fournisseur (goods-in / entrée de marchandises).

    Trace une réception (totale ou partielle) des articles d'un bon de commande
    fournisseur. À la CONFIRMATION (statut « confirmé »), chaque ligne reçue
    crée un `MouvementStock` ENTREE — exactement comme l'action `recevoir` du
    BCF, jamais un mécanisme parallèle — et avance le statut du BCF selon ses
    quantités reçues existantes (`quantite_recue`/`est_entierement_recu`). La
    confirmation est IDEMPOTENTE : une réception déjà confirmée ne re-crée
    jamais de mouvement. Numérotation sans trou (préfixe REC). Usage INTERNE.
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        CONFIRME = 'confirme', 'Confirmé'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='receptions_fournisseur')
    reference = models.CharField(max_length=50)
    bon_commande = models.ForeignKey(
        BonCommandeFournisseur, on_delete=models.PROTECT,
        related_name='receptions')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    date_reception = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True, null=True)
    # Qui a réceptionné la marchandise.
    recu_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='receptions_fournisseur')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='receptions_fournisseur_creees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Réception fournisseur'
        verbose_name_plural = 'Réceptions fournisseur'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference

    @property
    def total_recu(self):
        """Nombre total d'articles reçus sur cette réception."""
        return sum((ligne.quantite for ligne in self.lignes.all()), 0)


class LigneReceptionFournisseur(models.Model):
    """Ligne d'une réception fournisseur : la ligne de BCF concernée, le produit
    et la quantité effectivement reçue lors de cette réception."""

    reception = models.ForeignKey(
        ReceptionFournisseur, on_delete=models.CASCADE, related_name='lignes')
    ligne_commande = models.ForeignKey(
        LigneBonCommandeFournisseur, on_delete=models.PROTECT,
        related_name='lignes_reception')
    produit = models.ForeignKey(
        Produit, on_delete=models.PROTECT,
        related_name='lignes_reception_fournisseur')
    quantite = models.IntegerField()

    # ── FG61 — Numéros de série à la réception ────────────────────────────
    # Sériaux capturés à l'entrée en stock (pour réconciliation avec
    # sav.Equipement lors de l'installation). Optionnel ; liste de chaînes.
    numeros_serie = models.JSONField(
        null=True, blank=True,
        help_text='Numéros de série reçus lors de cette ligne (liste de '
                  'chaînes). Optionnel ; aucune série = null.')

    # ── FG64 — Traçabilité lot / date de péremption ───────────────────────
    # Batteries, produits d'étanchéité, etc. Optionnel : un produit sans
    # date de péremption n'apparaît jamais dans le rapport d'expiry.
    numero_lot = models.CharField(
        max_length=100, blank=True, null=True,
        help_text='Numéro de lot ou batch (optionnel).')
    date_peremption = models.DateField(
        null=True, blank=True,
        help_text='Date de péremption / fin de vie (optionnel).')

    class Meta:
        verbose_name = 'Ligne de réception fournisseur'
        verbose_name_plural = 'Lignes de réception fournisseur'

    def __str__(self):
        return f'{self.produit_id} × {self.quantite}'


class FactureFournisseur(models.Model):
    """G5 — Facture fournisseur / comptabilité fournisseur (AP).

    Document d'ACHAT reçu d'un fournisseur, éventuellement rattaché à un bon de
    commande fournisseur. Porte les montants HT/TVA/TTC et un statut de
    règlement. Le solde dû = TTC − Σ paiements. Usage INTERNE (les montants
    d'achat ne sont jamais client-facing).
    """

    class Statut(models.TextChoices):
        A_PAYER = 'a_payer', 'À payer'
        PARTIELLEMENT_PAYEE = 'partiellement_payee', 'Partiellement payée'
        PAYEE = 'payee', 'Payée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='factures_fournisseur')
    reference = models.CharField(max_length=50)
    fournisseur = models.ForeignKey(
        Fournisseur, on_delete=models.PROTECT,
        related_name='factures_fournisseur')
    bon_commande = models.ForeignKey(
        BonCommandeFournisseur, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='factures_fournisseur')
    # Référence du document chez le fournisseur (numéro de sa facture).
    ref_fournisseur = models.CharField(max_length=100, blank=True, null=True)
    date_facture = models.DateField(null=True, blank=True)
    date_echeance = models.DateField(null=True, blank=True)
    montant_ht = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    montant_tva = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    montant_ttc = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    statut = models.CharField(
        max_length=24, choices=Statut.choices, default=Statut.A_PAYER)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='factures_fournisseur')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Facture fournisseur'
        verbose_name_plural = 'Factures fournisseur'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference

    @property
    def total_paye(self):
        """Somme des paiements enregistrés sur cette facture."""
        return sum((p.montant for p in self.paiements.all()), Decimal('0'))

    @property
    def solde_du(self):
        """Solde dû = TTC − Σ paiements (jamais négatif affiché)."""
        return (self.montant_ttc or Decimal('0')) - self.total_paye


class LigneFactureFournisseur(models.Model):
    """Ligne (optionnelle) d'une facture fournisseur : désignation libre,
    quantité et prix d'achat unitaire HT. Permet de ventiler une facture par
    article. INTERNE."""

    facture = models.ForeignKey(
        FactureFournisseur, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        Produit, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lignes_facture_fournisseur')
    designation = models.CharField(max_length=255)
    quantite = models.DecimalField(
        max_digits=12, decimal_places=2, default=1)
    prix_unitaire_ht = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Ligne de facture fournisseur'
        verbose_name_plural = 'Lignes de facture fournisseur'

    def __str__(self):
        return f'{self.designation} × {self.quantite}'

    @property
    def total_ht(self):
        return (self.quantite or Decimal('0')) * (
            self.prix_unitaire_ht or Decimal('0'))


class PaiementFournisseur(models.Model):
    """G5 — Paiement (règlement) d'une facture fournisseur. Chaque paiement
    réduit le solde dû de la facture. INTERNE."""

    class Mode(models.TextChoices):
        VIREMENT = 'virement', 'Virement'
        CHEQUE = 'cheque', 'Chèque'
        ESPECES = 'especes', 'Espèces'
        CARTE = 'carte', 'Carte'
        EFFET = 'effet', 'Effet / traite'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='paiements_fournisseur')
    facture = models.ForeignKey(
        FactureFournisseur, on_delete=models.CASCADE, related_name='paiements')
    montant = models.DecimalField(max_digits=14, decimal_places=2)
    date_paiement = models.DateField(null=True, blank=True)
    mode = models.CharField(
        max_length=20, choices=Mode.choices, default=Mode.VIREMENT)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='paiements_fournisseur')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Paiement fournisseur'
        verbose_name_plural = 'Paiements fournisseur'
        ordering = ['-date_paiement', '-date_creation']

    def __str__(self):
        return f'{self.facture_id} — {self.montant}'


# ── FG63 — Session d'inventaire (comptage physique en brouillon) ──────────────

class InventaireSession(models.Model):
    """FG63 — Session de comptage physique du stock.

    Remplace l'action `inventaire` "one-shot" par un workflow draft / valider :
    le comptage est enregistré en mode brouillon (pouvant être corrigé) puis
    validé en une seule passe qui émet les ajustements (AJUSTEMENT) uniquement
    pour les lignes dont la quantité comptée diffère de la quantité théorique.
    La validation est IDEMPOTENTE : une session déjà validée ne peut pas être
    re-validée. INTERNE — admin uniquement.
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        VALIDE = 'valide', 'Validé'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='inventaire_sessions')
    reference = models.CharField(max_length=50)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    motif = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='inventaire_sessions')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Session d\'inventaire'
        verbose_name_plural = 'Sessions d\'inventaire'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference


class LigneInventaire(models.Model):
    """Ligne d'une session d'inventaire : produit, quantité théorique
    (tirée du stock au moment de la création) et quantité comptée physiquement.
    L'écart est calculé lors de la validation de la session."""
    session = models.ForeignKey(
        InventaireSession, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        Produit, on_delete=models.PROTECT,
        related_name='lignes_inventaire')
    quantite_theorique = models.IntegerField(
        help_text='Stock théorique au moment du comptage (snapshot).')
    quantite_comptee = models.IntegerField(
        help_text='Quantité réellement comptée physiquement.')

    class Meta:
        verbose_name = 'Ligne d\'inventaire'
        verbose_name_plural = 'Lignes d\'inventaire'

    def __str__(self):
        return f'{self.produit_id}: théo={self.quantite_theorique} compté={self.quantite_comptee}'

    @property
    def ecart(self):
        return self.quantite_comptee - self.quantite_theorique
