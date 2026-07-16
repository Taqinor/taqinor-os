"""Modèles CPQ (Configure-Price-Quote enterprise).

Toutes les liaisons vers les autres apps DOMAINE (``stock``, ``ventes``,
``crm``) sont des string-FK (M3 : aucun import de leurs ``models``). Chaque
modèle porte un FK ``company`` (multi-tenant) posé côté serveur.
"""
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
