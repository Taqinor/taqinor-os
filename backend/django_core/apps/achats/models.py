"""apps.achats — App Achats (équivalent Odoo Purchase), étape 1 (ODX19).

Ces modèles vivaient dans ``apps.stock`` (bons de commande fournisseur,
réceptions, factures/paiements fournisseur, retours fournisseur). ODX19 les
sort de stock en préservant à l'IDENTIQUE leurs tables physiques
(``db_table = 'stock_<model>'``) via des migrations
``SeparateDatabaseAndState`` (state-only, zéro SQL). ``apps.stock`` garde un
shim de ré-export (``apps/stock/models.py``) pour tout le code existant.

Fournisseur, Produit, MouvementStock, EmplacementStock RESTENT dans stock
(master data façon res.partner/product) : ces modèles les référencent par
STRING-FK uniquement (jamais d'import de ``apps.stock.models``) — le
contrat import-linter ``achats-models-decoupled`` verrouille cette règle.
``prix_achat``/``PrixFournisseur`` restent des données INTERNES, jamais
client-facing (cf. règle CLAUDE.md — pas d'exposition dans un document
client).
"""

from decimal import Decimal

from django.conf import settings
from django.db import models


# XPUR3 — devises d'achat courantes (imports panneaux/onduleurs). MAD reste le
# défaut partout : un document sans devise saisie garde le comportement
# historique (contre-valeur = montant, taux = 1) puisque tout est déjà en MAD.
class DeviseAchat(models.TextChoices):
    MAD = 'MAD', 'Dirham marocain (MAD)'
    EUR = 'EUR', 'Euro (EUR)'
    USD = 'USD', 'Dollar américain (USD)'
    CNY = 'CNY', 'Yuan chinois (CNY)'


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
        'stock.Produit', on_delete=models.CASCADE,
        related_name='prix_fournisseurs')
    fournisseur = models.ForeignKey(
        'stock.Fournisseur', on_delete=models.CASCADE,
        related_name='prix_produits')
    # Prix d'ACHAT — donnée INTERNE, jamais sur un document client.
    prix_achat = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date_dernier_achat = models.DateField(null=True, blank=True)
    # XPUR7 — délai de livraison (jours) constaté/annoncé pour ce couple
    # produit×fournisseur. Alimente la suggestion `date_livraison_prevue`
    # d'un BCF. Null = pas de délai connu (comportement historique).
    delai_livraison_jours = models.PositiveIntegerField(null=True, blank=True)
    # ── XPUR14 — code article fournisseur, paliers de quantité, validité ────
    # Code article CHEZ LE FOURNISSEUR (imprimé sur le PDF BCF pour éviter les
    # erreurs de préparation côté fournisseur). Vide = comportement historique
    # (colonne omise du PDF).
    ref_produit_fournisseur = models.CharField(
        max_length=100, blank=True, default='',
        help_text="Code article chez le fournisseur (imprimé sur le PDF "
                  'BCF).')
    # Fenêtre de validité du tarif. Vide des deux côtés = comportement
    # historique (toujours proposé, aucune expiration). Un tarif expiré
    # (date_fin dépassée) n'est plus proposé par l'auto-fill BCF.
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Prix fournisseur"
        verbose_name_plural = "Prix fournisseurs"
        db_table = 'stock_prixfournisseur'
        unique_together = [('produit', 'fournisseur')]
        ordering = ['prix_achat']

    def __str__(self):
        return f'{self.produit_id} @ {self.fournisseur_id} = {self.prix_achat}'

    def est_en_vigueur(self, a_la_date=None):
        """XPUR14 — vrai si le tarif est valide à la date donnée (aujourd'hui
        par défaut). Une borne absente est ouverte de ce côté (comportement
        historique : sans dates saisies, toujours en vigueur)."""
        from django.utils import timezone
        ref = a_la_date or timezone.now().date()
        if self.date_debut and ref < self.date_debut:
            return False
        if self.date_fin and ref > self.date_fin:
            return False
        return True


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
        'stock.Fournisseur',
        on_delete=models.PROTECT,
        related_name='bons_commande',
    )
    statut = models.CharField(
        max_length=20,
        choices=Statut.choices,
        default=Statut.BROUILLON,
    )
    date_commande = models.DateField(null=True, blank=True)
    # XPUR3 — devise du document (défaut MAD, comportement historique
    # inchangé) + taux de change saisi à la date du document (aucun appel
    # externe). Les LIGNES portent le prix d'achat unitaire EN CETTE DEVISE ;
    # la contre-valeur MAD (utilisée PARTOUT en interne : coût moyen pondéré,
    # balance âgée, payment run, comparatif fournisseurs) est calculée par
    # `LigneBonCommandeFournisseur.prix_achat_unitaire_mad`.
    devise = models.CharField(
        max_length=3, choices=DeviseAchat.choices, default=DeviseAchat.MAD)
    taux_change = models.DecimalField(
        max_digits=12, decimal_places=6, default=1,
        help_text='Taux de change devise → MAD à la date du document '
                  '(saisie manuelle, aucun appel externe).')
    # ── XPUR7 — dates de livraison prévues, accusé fournisseur, OTD réel ────
    # Pré-calculée (date_commande + délai de PrixFournisseur) à la création,
    # reste modifiable ensuite. Null = pas de date prévue (comportement
    # historique, aucun délai connu).
    date_livraison_prevue = models.DateField(null=True, blank=True)
    # Accusé de commande du fournisseur : date qu'IL confirme (distincte de
    # la date demandée ci-dessus, jamais écrasée — préserve l'OTD promis-vs-
    # reçu) + son numéro de confirmation.
    date_confirmee_fournisseur = models.DateField(null=True, blank=True)
    numero_confirmation_fournisseur = models.CharField(
        max_length=100, blank=True, default='')
    # XPUR18 — compteur de révision (0 = jamais révisé, comportement
    # historique). Incrémenté UNIQUEMENT par l'action `reviser` (édition
    # directe des lignes/montants/dates refusée après ENVOYE) ; imprimé sur
    # le PDF (« Rév. N » à partir de 1).
    revision = models.PositiveIntegerField(default=0)
    # ── XPUR23 — destination de réception ───────────────────────────────────
    # Dépôt/emplacement CIBLE (nullable = comportement historique : crédite
    # le dépôt principal, dérivé implicitement) OU chantier de livraison
    # DIRECTE (string-FK installations.Installation, nullable — distinct du
    # `chantier_origine` de YPROC10, qui trace la demande d'ORIGINE plutôt
    # que la LIVRAISON). Au plus l'un des deux est renseigné en usage normal
    # (non contraint en base : un champ vide reste inoffensif).
    emplacement_destination = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.SET_NULL, null=True,
        blank=True,
        related_name='bons_commande_destination',
        help_text='Emplacement crédité à la réception (vide = dépôt '
                  'principal, comportement historique).')
    # String-FK cross-app (jamais d'import de apps.installations.models) —
    # même convention que installations.ContratPrixFournisseur.fournisseur.
    chantier_livraison = models.ForeignKey(
        'installations.Installation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='bons_commande_livraison_directe',
        help_text='Chantier de LIVRAISON DIRECTE (distinct de '
                  "chantier_origine/YPROC10, qui trace la demande "
                  "d'origine) : la réception est suivie d'une affectation "
                  "chantier tracée (n'entre jamais en stock libre). "
                  'Vide = comportement historique.')
    # ── YPROC10 — chantier D'ORIGINE du besoin (distinct de chantier_livraison
    # ci-dessus, qui trace la LIVRAISON). Posé par `draft_bcf_for_shortfall` ;
    # à la confirmation de réception, `installations` (abonné à l'événement
    # `reception_fournisseur_confirmee`) crée/complète les `StockReservation`
    # actives du chantier pour les quantités reçues — la chaîne MTO (« Made
    # To Order ») n'est plus cassée à la réception. Nullable = comportement
    # historique inchangé (la marchandise entre en stock libre).
    chantier_origine = models.ForeignKey(
        'installations.Installation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='bons_commande_besoin_origine',
        help_text="Chantier D'ORIGINE du besoin matériel (distinct de "
                  'chantier_livraison, qui trace la LIVRAISON) : réceptionner '
                  'ce BCF réserve automatiquement les quantités reçues pour '
                  'ce chantier. Vide = comportement historique (stock '
                  'libre).')
    # ZPUR7 — compteur de relances PROPOSÉES au fournisseur pour un BCF en
    # retard (incrémenté par `stock.tasks.relancer_bcf_en_retard`, jamais un
    # envoi automatique — le brouillon est proposé, l'utilisateur clique).
    # 0 = comportement historique (jamais relancé).
    nb_relances = models.PositiveIntegerField(default=0)
    # ── ZPUR8 — onglet « Other Information » Odoo, au niveau du DOCUMENT ────
    # Acheteur (défaut = created_by, alimente l'analyse achats XPUR24 par
    # acheteur + l'OTD par acheteur), référence de commande côté fournisseur
    # (texte libre) et mentions imprimées sur le PDF. Additif — vide/nul =
    # comportement historique inchangé.
    acheteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='bons_commande_fournisseur_acheteur',
        help_text="Acheteur responsable du BCF (défaut = created_by).")
    ref_fournisseur = models.CharField(
        max_length=100, blank=True, null=True,
        help_text='Référence de la commande côté fournisseur (texte libre).')
    note_bas_page = models.TextField(
        blank=True, null=True,
        help_text='Mentions imprimées en bas de page du PDF BCF.')
    # Report éditable des défauts fournisseur (XPUR5 incoterm, XPUR6
    # conditions de paiement) AU NIVEAU DU DOCUMENT — sans redéfinir ces
    # référentiels. Vide = comportement historique (rien reporté).
    incoterm = models.CharField(max_length=10, blank=True, null=True)
    conditions_paiement = models.CharField(
        max_length=200, blank=True, null=True,
        help_text='Conditions de paiement reportées du fournisseur '
                  '(éditables au document), dérivées de delai_paiement_jours.')
    # ZPUR11 — motif OBLIGATOIRE à l'annulation (texte, requis — 400 si vide),
    # horodaté + acteur tracés via `records.Comment` (chatter). Vide = jamais
    # annulé (comportement historique).
    motif_annulation = models.TextField(blank=True, null=True)
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
        db_table = 'stock_boncommandefournisseur'
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
    # XPUR16 — nullable : une ligne LIBRE/SERVICE (transport, prestation,
    # frais) n'a pas de produit catalogue. `sans_stock` (auto quand produit
    # est null) marque ces lignes : elles comptent dans le total/
    # l'approbation/la facturation mais ne génèrent JAMAIS de MouvementStock
    # à la réception. Comportement historique inchangé pour une ligne
    # catalogue normale (produit renseigné, sans_stock=False).
    produit = models.ForeignKey(
        'stock.Produit',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='lignes_bon_commande_fournisseur',
    )
    designation = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Désignation libre (obligatoire quand produit est vide — '
                  'ex. « Transport Casablanca »).')
    sans_stock = models.BooleanField(
        default=False,
        help_text='Ligne libre/service : jamais de mouvement de stock à la '
                  "réception. Toujours vrai quand produit est vide.")
    quantite = models.IntegerField()
    # Prix d'ACHAT unitaire — donnée INTERNE, TOUJOURS en contre-valeur MAD
    # (utilisée PARTOUT en interne : coût moyen pondéré/landed cost, balance
    # âgée, payment run, comparatif fournisseurs — XPUR3). N'apparaît JAMAIS
    # sur un document destiné au client (devis, facture, BC client).
    prix_achat_unitaire = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
    )
    # XPUR3 — prix d'achat unitaire saisi dans la DEVISE du document (BCF.
    # devise/taux_change). Null = document en MAD (comportement historique) :
    # `prix_achat_unitaire` reste alors l'unique source de vérité. Quand
    # renseigné, `prix_achat_unitaire` DOIT être sa contre-valeur MAD
    # (prix_achat_unitaire_devise × bon_commande.taux_change) — recalculée
    # côté service à la saisie, jamais divergente.
    prix_achat_unitaire_devise = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Prix d'achat unitaire dans la devise du document "
                  '(optionnel — null = document en MAD).')
    # ── FG67 / DC38 — Coût débarqué (landed cost) ────────────────────────────
    # Frais annexes TOTAUX de la LIGNE (fret + douane + TVA import + transit),
    # à répartir sur les unités de la ligne. Le coût de revient débarqué
    # unitaire = prix_achat_unitaire + frais_annexes / quantité. Replié dans le
    # coût moyen pondéré (average_cost_with_source). INTERNE, jamais
    # client-facing. Optionnel (0 = comportement historique inchangé).
    frais_annexes = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Frais annexes TOTAUX de la ligne (fret/douane/TVA import/'
                  'transit), répartis sur les unités. INTERNE.')
    quantite_recue = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Ligne de bon de commande fournisseur'
        verbose_name_plural = 'Lignes de bon de commande fournisseur'
        db_table = 'stock_ligneboncommandefournisseur'

    def __str__(self):
        return f'{self.designation or self.produit_id} × {self.quantite}'

    def save(self, *args, **kwargs):
        # XPUR16 — une ligne sans produit catalogue est TOUJOURS sans_stock
        # (auto, jamais l'inverse — une ligne catalogue reste normale).
        if self.produit_id is None:
            self.sans_stock = True
        super().save(*args, **kwargs)

    @property
    def quantite_restante(self):
        return max(self.quantite - self.quantite_recue, 0)

    @property
    def total_achat(self):
        return self.quantite * self.prix_achat_unitaire

    @property
    def cout_unitaire_debarque(self):
        """FG67/DC38 — coût de revient débarqué unitaire = prix d'achat unitaire
        + frais annexes répartis sur la quantité de la ligne. INTERNE."""
        pu = self.prix_achat_unitaire or Decimal('0')
        frais = self.frais_annexes or Decimal('0')
        qte = self.quantite or 0
        if qte and frais:
            return pu + (frais / Decimal(str(qte)))
        return pu


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
        db_table = 'stock_receptionfournisseur'
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
    # XPUR16 — nullable pour une ligne libre/service (dérivé de
    # `ligne_commande.produit`, peut donc être vide).
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True,
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
        db_table = 'stock_lignereceptionfournisseur'

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

    # XPUR2 — nature de l'achat pour la RAS-TVA (LF 2024) : biens & travaux
    # (retenue 100 % de la TVA SI le fournisseur n'a pas d'ARF valide, sinon
    # rien) vs prestations de services (75 % avec ARF valide / 100 % sans).
    # Défaut 'biens' — comportement historique inchangé tant que la RAS-TVA
    # est désactivée (AchatsParametres.ras_tva_actif = False par défaut).
    class TypeAchat(models.TextChoices):
        BIENS = 'biens', 'Biens & travaux'
        SERVICES = 'services', 'Prestations de services'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='factures_fournisseur')
    reference = models.CharField(max_length=50)
    fournisseur = models.ForeignKey(
        'stock.Fournisseur', on_delete=models.PROTECT,
        related_name='factures_fournisseur')
    bon_commande = models.ForeignKey(
        BonCommandeFournisseur, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='factures_fournisseur')
    # Référence du document chez le fournisseur (numéro de sa facture).
    ref_fournisseur = models.CharField(max_length=100, blank=True, null=True)
    type_achat = models.CharField(
        max_length=10, choices=TypeAchat.choices, default=TypeAchat.BIENS,
        help_text="Nature de l'achat (RAS-TVA LF 2024) : biens & travaux ou "
                  'prestations de services.')
    date_facture = models.DateField(null=True, blank=True)
    date_echeance = models.DateField(null=True, blank=True)
    # XPUR3 — devise + taux de change (mêmes règles que le BCF : défaut MAD,
    # taux 1, saisi à la date du document, aucun appel externe). Les montants
    # HT/TVA/TTC ci-dessous restent TOUJOURS la contre-valeur MAD (utilisée
    # partout en interne : balance âgée FG132, payment run FG133) ; les
    # montants en devise natifs sont ajoutés séparément pour l'affichage.
    devise = models.CharField(
        max_length=3, choices=DeviseAchat.choices, default=DeviseAchat.MAD)
    taux_change = models.DecimalField(
        max_digits=12, decimal_places=6, default=1,
        help_text='Taux de change devise → MAD à la date du document '
                  '(saisie manuelle, aucun appel externe).')
    montant_ttc_devise = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text='Montant TTC dans la devise du document (optionnel — '
                  'null = document en MAD).')
    montant_ht = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    montant_tva = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    montant_ttc = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    statut = models.CharField(
        max_length=24, choices=Statut.choices, default=Statut.A_PAYER)

    # ── XPUR10 — file d'exceptions du rapprochement 3 voies (FG131) ────────
    # Une facture HORS tolérance société (XPUR10) passe en `exception` : la
    # CRÉATION d'un PaiementFournisseur est refusée tant qu'elle n'est pas
    # résolue par un responsable/admin. Défaut 'normale' = comportement
    # historique inchangé (jamais bloquée).
    class StatutControle(models.TextChoices):
        NORMALE = 'normale', 'Normale'
        EXCEPTION = 'exception', 'En exception'
        RESOLUE = 'resolue', 'Résolue'

    statut_controle = models.CharField(
        max_length=12, choices=StatutControle.choices,
        default=StatutControle.NORMALE)
    motif_ecart = models.TextField(blank=True, null=True)

    # ── XPUR26 — e-facturation DGI 2026 (ENTRANT, préparation mandat) ───────
    # Un import UBL 2.1 pré-remplit ces champs ; une facture saisie
    # manuellement reste `non_applicable` (comportement historique). AUCUN
    # appel externe ici — la validation plateforme réelle attendra le mandat.
    class StatutConformiteDgi(models.TextChoices):
        NON_APPLICABLE = 'non_applicable', 'Non applicable'
        CLEARED = 'cleared', 'Validée (clearance DGI)'
        NON_CLEARED = 'non_cleared', 'Non validée'

    numero_clearance_dgi = models.CharField(
        max_length=100, blank=True, null=True,
        help_text="Numéro de clearance DGI (e-invoicing entrant, si fourni "
                  'par le document UBL).')
    statut_conformite_dgi = models.CharField(
        max_length=20, choices=StatutConformiteDgi.choices,
        default=StatutConformiteDgi.NON_APPLICABLE)
    resolu_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='factures_fournisseur_resolues')
    resolu_le = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='factures_fournisseur')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Facture fournisseur'
        verbose_name_plural = 'Factures fournisseur'
        db_table = 'stock_facturefournisseur'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference

    @property
    def total_paye(self):
        """Somme des paiements enregistrés sur cette facture."""
        return sum((p.montant for p in self.paiements.all()), Decimal('0'))

    @property
    def total_acomptes_imputes(self):
        """XPUR8 — somme des acomptes fournisseur imputés sur CETTE facture
        (0 si aucun — comportement historique inchangé)."""
        return sum(
            (a.montant for a in self.acomptes_imputes.all()), Decimal('0'))

    @property
    def total_avoirs_imputes(self):
        """XPUR9 — somme des avoirs fournisseur imputés sur CETTE facture
        (0 si aucun — comportement historique inchangé)."""
        return sum(
            (i.montant for i in self.avoirs_imputes.all()), Decimal('0'))

    @property
    def solde_du(self):
        """Solde dû = TTC − Σ paiements − Σ acomptes imputés − Σ avoirs
        imputés (jamais négatif)."""
        solde = ((self.montant_ttc or Decimal('0')) - self.total_paye
                 - self.total_acomptes_imputes - self.total_avoirs_imputes)
        return max(solde, Decimal('0'))


class LigneFactureFournisseur(models.Model):
    """Ligne (optionnelle) d'une facture fournisseur : désignation libre,
    quantité et prix d'achat unitaire HT. Permet de ventiler une facture par
    article. INTERNE."""

    facture = models.ForeignKey(
        FactureFournisseur, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lignes_facture_fournisseur')
    designation = models.CharField(max_length=255)
    quantite = models.DecimalField(
        max_digits=12, decimal_places=2, default=1)
    prix_unitaire_ht = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    # XPUR17 — TVA PAR LIGNE (taux marocains 20/14/10/7 %/exonéré 0 — miroir
    # de `ventes.LigneFacture.taux_tva`). NULL = ligne historique → le taux
    # global de la facture (montant_tva/montant_ht agrégés) continue de
    # s'appliquer, rendu strictement inchangé pour les factures déjà émises.
    # Défaut 20 % pour une ligne NOUVELLE sans taux explicite.
    taux_tva = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, default=20,
        help_text='Taux TVA de la ligne (%). Vide = taux global de la '
                  'facture (comportement historique).')

    class Meta:
        verbose_name = 'Ligne de facture fournisseur'
        verbose_name_plural = 'Lignes de facture fournisseur'
        db_table = 'stock_lignefacturefournisseur'

    def __str__(self):
        return f'{self.designation} × {self.quantite}'

    @property
    def total_ht(self):
        return (self.quantite or Decimal('0')) * (
            self.prix_unitaire_ht or Decimal('0'))

    @property
    def total_tva(self):
        """XPUR17 — TVA de la ligne (0 si `taux_tva` est vide — la ligne
        suit alors le taux global agrégé de la facture, comportement
        historique)."""
        if self.taux_tva is None:
            return Decimal('0')
        return (self.total_ht * self.taux_tva / Decimal('100')).quantize(
            Decimal('0.01'))


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
    # ── XPUR2 — RAS-TVA fournisseurs (LF 2024, en vigueur 01/07/2024) ───────
    # Montant retenu à la source sur la TVA facturée + le taux appliqué
    # (0/75/100 %), calculés selon FactureFournisseur.type_achat + la
    # validité ARF du fournisseur (XPUR1). 0 par défaut = comportement
    # historique inchangé tant que AchatsParametres.ras_tva_actif est OFF.
    montant_ras_tva = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text='Montant de la retenue à la source sur la TVA (LF 2024).')
    taux_ras = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='Taux de RAS-TVA appliqué (0/75/100 %).')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='paiements_fournisseur')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Paiement fournisseur'
        verbose_name_plural = 'Paiements fournisseur'
        db_table = 'stock_paiementfournisseur'
        ordering = ['-date_paiement', '-date_creation']

    def __str__(self):
        return f'{self.facture_id} — {self.montant}'

    @property
    def montant_net_paye(self):
        """XPUR2 — net réellement décaissé = montant − RAS-TVA retenue."""
        return (self.montant or Decimal('0')) - (
            self.montant_ras_tva or Decimal('0'))


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
        'stock.Fournisseur', on_delete=models.PROTECT, related_name='retours')
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
        db_table = 'stock_retourfournisseur'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference


class LigneRetourFournisseur(models.Model):
    """Ligne d'un retour fournisseur : SKU, quantité retournée, motif."""
    retour = models.ForeignKey(
        RetourFournisseur, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT,
        related_name='lignes_retour_fournisseur')
    quantite = models.IntegerField()
    motif = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = 'Ligne de retour fournisseur'
        verbose_name_plural = 'Lignes de retour fournisseur'
        db_table = 'stock_ligneretourfournisseur'

    def __str__(self):
        return f'{self.produit_id} × {self.quantite}'
