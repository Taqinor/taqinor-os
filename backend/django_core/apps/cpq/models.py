"""Modèles CPQ (Configure-Price-Quote enterprise).

Toutes les liaisons vers les autres apps DOMAINE (``stock``, ``ventes``,
``crm``) sont des string-FK (M3 : aucun import de leurs ``models``). Chaque
modèle porte un FK ``company`` (multi-tenant) posé côté serveur.
"""
from django.conf import settings
from django.db import models


class OptionProduit(models.Model):
    """NTCPQ1 — Option de configuration d'un produit.

    Regroupe des produits par ``groupe_option`` (ex. « Onduleur », « Batterie »)
    et marque si le groupe est obligatoire dans une configuration. String-FK
    vers ``stock.Produit`` (aucun import cross-app)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='cpq_options_produit')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,
        related_name='cpq_options')
    groupe_option = models.CharField(
        max_length=100,
        help_text="Groupe de l'option (ex. « Onduleur », « Batterie »).")
    obligatoire = models.BooleanField(
        default=False,
        help_text='Le groupe doit être renseigné dans la configuration.')

    class Meta:
        verbose_name = 'Option produit'
        verbose_name_plural = 'Options produit'
        ordering = ['groupe_option', 'id']
        indexes = [
            models.Index(fields=['company', 'groupe_option'],
                         name='cpq_optprod_co_grp'),
        ]

    def __str__(self):
        return f'{self.groupe_option} · produit {self.produit_id}'


class ContrainteCompatibilite(models.Model):
    """NTCPQ1 — Contrainte de compatibilité entre deux produits.

    ``INCOMPATIBLE`` : les deux produits ne peuvent coexister (violation
    bloquante). ``REQUIERT`` : si ``produit_a`` est présent, ``produit_b`` doit
    l'être aussi (bloquant). ``RECOMMANDE`` : suggestion (avertissement seul)."""
    class TypeContrainte(models.TextChoices):
        INCOMPATIBLE = 'INCOMPATIBLE', 'Incompatible'
        REQUIERT = 'REQUIERT', 'Requiert'
        RECOMMANDE = 'RECOMMANDE', 'Recommandé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='cpq_contraintes_compatibilite')
    produit_a = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,
        related_name='cpq_contraintes_a')
    produit_b = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,
        related_name='cpq_contraintes_b')
    type = models.CharField(
        max_length=20, choices=TypeContrainte.choices)
    message_utilisateur = models.CharField(
        max_length=255, blank=True, default='',
        help_text="Message affiché à l'utilisateur quand la contrainte joue.")

    class Meta:
        verbose_name = 'Contrainte de compatibilité'
        verbose_name_plural = 'Contraintes de compatibilité'
        ordering = ['id']
        indexes = [
            models.Index(fields=['company', 'type'],
                         name='cpq_contr_co_type'),
            models.Index(fields=['company', 'produit_a'],
                         name='cpq_contr_co_pa'),
        ]

    def __str__(self):
        return f'{self.produit_a_id} {self.type} {self.produit_b_id}'

    @property
    def bloquante(self):
        """``INCOMPATIBLE`` et ``REQUIERT`` sont bloquantes ; ``RECOMMANDE``
        est un simple avertissement."""
        return self.type in (
            self.TypeContrainte.INCOMPATIBLE, self.TypeContrainte.REQUIERT)


class RegleProduitCPQ(models.Model):
    """NTCPQ2 — Règle produit data-driven réutilisant ``core.rules``.

    ``condition_group`` est un arbre de conditions ET/OU/NON évalué par
    ``core.rules.evaluate_condition_group`` (le moteur GÉNÉRIQUE existant, jamais
    réécrit). ``actions`` est une liste libre de dicts (ex.
    ``[{"type": "exiger_option", "valeur": "triphase"}]``) renvoyée quand la
    règle se déclenche. Aucune action n'est exécutée par le modèle : le
    déclenchement est purement déclaratif (l'appelant décide de la suite)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='cpq_regles_produit')
    nom = models.CharField(max_length=150)
    condition_group = models.JSONField(
        default=dict, blank=True,
        help_text="Arbre de conditions ET/OU/NON (core.rules).")
    actions = models.JSONField(
        default=list, blank=True,
        help_text='Liste d\'actions déclenchées quand la règle est vraie.')
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Règle produit CPQ'
        verbose_name_plural = 'Règles produit CPQ'
        ordering = ['-date_creation', 'id']
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='cpq_regle_co_actif'),
        ]

    def __str__(self):
        return self.nom


class OffreGroupee(models.Model):
    """NTCPQ3 — Bundle produit à prix cascadé.

    ``prix_total`` (optionnel) : quand il est renseigné et que les lignes sont
    en mode ``FIXE``, le total du bundle PRIME et est réparti au prorata du prix
    catalogue sur les lignes lors de l'application au devis. Sinon chaque ligne
    est valorisée selon son propre ``mode_prix``."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='cpq_offres_groupees')
    nom = models.CharField(max_length=150)
    prix_total = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Prix fixe du bundle (mode FIXE) réparti au prorata.')
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Offre groupée'
        verbose_name_plural = 'Offres groupées'
        ordering = ['-date_creation', 'id']
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='cpq_offre_co_actif'),
        ]

    def __str__(self):
        return self.nom


class LigneOffreGroupee(models.Model):
    """NTCPQ3 — Composant d'une offre groupée.

    ``mode_prix`` : ``FIXE`` (le total du bundle prime, réparti au prorata),
    ``REMISE_PCT`` (prix catalogue moins ``valeur`` %), ``PRIX_COMPOSANT``
    (prix imposé = ``valeur``)."""
    class ModePrix(models.TextChoices):
        FIXE = 'FIXE', 'Prix fixe (bundle)'
        REMISE_PCT = 'REMISE_PCT', 'Remise %'
        PRIX_COMPOSANT = 'PRIX_COMPOSANT', 'Prix composant imposé'

    offre = models.ForeignKey(
        OffreGroupee, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,
        related_name='cpq_lignes_offre')
    quantite = models.DecimalField(
        max_digits=10, decimal_places=2, default=1)
    mode_prix = models.CharField(
        max_length=20, choices=ModePrix.choices, default=ModePrix.FIXE)
    valeur = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='% de remise (REMISE_PCT) ou prix imposé (PRIX_COMPOSANT).')

    class Meta:
        verbose_name = 'Ligne offre groupée'
        verbose_name_plural = 'Lignes offre groupée'
        ordering = ['offre_id', 'id']

    def __str__(self):
        return f'{self.offre_id} · produit {self.produit_id} × {self.quantite}'


class PrixContractuel(models.Model):
    """NTCPQ5 — Prix négocié par contrat nommé pour un couple client/produit.

    Prime sur TOUTE liste de prix générique (segment, assignée…) pour ce couple
    client/produit tant qu'il est dans sa fenêtre de validité (priorité 1 dans
    ``ventes.services.prix_applicable``). Liaisons string-FK (aucun import des
    modèles crm/stock)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='cpq_prix_contractuels')
    client = models.ForeignKey(
        'crm.Client', on_delete=models.CASCADE,
        related_name='cpq_prix_contractuels')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,
        related_name='cpq_prix_contractuels')
    prix_ht = models.DecimalField(max_digits=12, decimal_places=2)
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    motif = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='cpq_prix_contractuels_crees')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Prix contractuel'
        verbose_name_plural = 'Prix contractuels'
        ordering = ['-date_creation', 'id']
        indexes = [
            models.Index(fields=['company', 'client', 'produit'],
                         name='cpq_prixctr_co_cl_pr'),
        ]

    def __str__(self):
        return f'{self.client_id}/{self.produit_id} @ {self.prix_ht}'

    @property
    def est_actif(self):
        """Dans sa fenêtre de validité (bornes optionnelles, ouvertes si
        non renseignées)."""
        from django.utils import timezone
        today = timezone.now().date()
        if self.date_debut and today < self.date_debut:
            return False
        if self.date_fin and today > self.date_fin:
            return False
        return True
