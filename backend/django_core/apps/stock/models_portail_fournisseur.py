"""Portail FOURNISSEUR — comptes réels (NTPRT3).

Avant NTPRT3, le seul accès d'un fournisseur à ses documents était
``PortailFournisseurToken`` (XPUR22) : un jeton opaque dans un lien email,
valable 90 jours, porteur d'un accès complet. ``CompteFournisseurPortail``
fait du compte utilisateur RÉEL le mécanisme PRIMAIRE — un ``CustomUser``
``portee=portail_fournisseur`` qui se connecte par le login JWT STANDARD
(jamais un second système d'authentification). Le jeton reste en place, sans
une ligne de changement, pour les liens ponctuels (« confirmez ce BCF par
email ») qui n'exigent pas de compte.

Ce module est un satellite de ``models.py`` (même pratique que
``models_qualite_reception.py``) ré-exporté par lui : ``from
apps.stock.models import CompteFournisseurPortail`` fonctionne partout.
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel


class CompteFournisseurPortail(TenantModel):
    """NTPRT3 — rattachement d'un compte utilisateur RÉEL à un fournisseur.

    Une ligne = « ce ``CustomUser`` EST ce fournisseur ». C'est la trace métier
    de l'accès : le rattachement qui BORNE les lectures vit sur le compte
    lui-même (``CustomUser.portail_fournisseur_id``, fondation NTPRT1) et c'est
    lui que lisent les gardes (``roles.permissions.IsPortalFournisseurUser``).
    Ce modèle porte ce que le compte utilisateur ne peut pas porter : quel
    fournisseur, dans quelle société, et si l'accès est encore ouvert.

    ``actif`` est un drapeau MÉTIER (« cet accès est-il ouvert ? »), doublé à
    la révocation par ``CustomUser.is_active = False`` — c'est ce dernier que
    SimpleJWT refuse dès l'authentification, y compris sur un jeton déjà
    distribué. Les deux portes se ferment ensemble
    (``services.revoquer_acces_compte_fournisseur``) : un seul des deux
    drapeaux laisserait une porte ouverte.

    Un seul compte par (société, fournisseur) — contrainte DB, pas une
    convention : deux comptes pour le même fournisseur rendraient la
    révocation ambiguë (lequel ferme l'accès ?).
    """

    fournisseur = models.ForeignKey(
        'stock.Fournisseur', on_delete=models.CASCADE,  # on_delete: CASCADE — un compte d'accès n'existe QUE pour son fournisseur (aucune donnée métier propre, aucune écriture comptable) ; le fournisseur supprimé, son accès n'a plus d'objet
        related_name='comptes_portail', verbose_name='Fournisseur')
    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,  # on_delete: CASCADE — le rattachement n'a aucun sens sans le compte utilisateur qu'il rattache ; le compte supprimé, la ligne ne désigne plus personne
        related_name='compte_fournisseur_portail',
        verbose_name='Compte utilisateur')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    derniere_connexion = models.DateTimeField(
        null=True, blank=True, verbose_name='Dernière connexion')

    class Meta:
        verbose_name = 'Compte portail fournisseur'
        verbose_name_plural = 'Comptes portail fournisseur'
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'fournisseur'],
                name='uniq_cptfourn_portail_co_fou'),
        ]
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='idx_cptfourn_por_co_actif'),
        ]

    def __str__(self):
        return f'Portail fournisseur {self.fournisseur_id} · {self.utilisateur_id}'


class AnnonceLivraisonFournisseur(TenantModel):
    """NTPRT22 — ASN : le fournisseur ANNONCE une expédition sur un BCF.

    Le fournisseur déclare « c'est parti, voici quoi, par qui, quand ». Le stock
    interne le voit sur le bon de commande AVANT que la marchandise arrive, ce
    qui permet de préparer le quai et de repérer un retard le jour de
    l'expédition au lieu du jour de la livraison.

    CE MODÈLE EST INFORMATIF, ET C'EST TOUT SON INTÉRÊT. Une annonce ne bouge
    AUCUN stock : elle ne crée ni ``MouvementStock``, ni ``ReceptionFournisseur``,
    ni ``quantite_recue``. La seule chose qui fait entrer de la marchandise reste
    la réception CONFIRMÉE côté interne. Sinon un fournisseur pourrait, depuis
    son portail, créditer notre stock d'une palette qui n'est jamais arrivée —
    et le stock cesserait d'être une mesure pour devenir une déclaration.

    Distinct de ``services_wms.bordereau_asn_unite`` (NTWMS27), qui est l'ASN
    SORTANT d'une unité logistique scellée que NOUS expédions : ici l'annonce
    est ENTRANTE et adossée à un bon de commande fournisseur. Distinct aussi de
    ``RendezVousTransporteur`` (NTWMS35), qui réserve un CRÉNEAU de quai sans
    rien dire du contenu.

    ``lignes`` porte les quantités annoncées par produit
    (``[{'produit_id', 'produit_nom', 'quantite'}, …]``, normalisées par
    ``services.annoncer_livraison_fournisseur`` contre les lignes du BCF) —
    JAMAIS un prix : le fournisseur annonce ce qu'il envoie, pas ce qu'il
    facture.
    """

    class Statut(models.TextChoices):
        ANNONCEE = 'annoncee', 'Annoncée'
        EN_TRANSIT = 'en_transit', 'En transit'
        LIVREE = 'livree', 'Livrée'

    bon_commande_fournisseur = models.ForeignKey(
        'achats.BonCommandeFournisseur', on_delete=models.CASCADE,  # on_delete: CASCADE — une annonce d'expédition ne désigne QUE son bon de commande (déclaration informative, aucun mouvement de stock, aucune écriture comptable) ; le bon supprimé, elle n'annonce plus rien
        related_name='annonces_livraison', verbose_name='Bon de commande')
    date_expedition = models.DateField(
        null=True, blank=True, verbose_name="Date d'expédition")
    date_livraison_prevue = models.DateField(
        null=True, blank=True, verbose_name='Date de livraison prévue')
    transporteur = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Transporteur')
    numero_suivi = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Numéro de suivi')
    lignes = models.JSONField(
        default=list, blank=True, verbose_name='Quantités annoncées',
        help_text="Quantités annoncées par produit. Jamais un prix : le "
                  "fournisseur annonce ce qu'il envoie, pas ce qu'il facture.")
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.ANNONCEE,
        verbose_name='Statut')

    class Meta:
        verbose_name = 'Annonce de livraison fournisseur'
        verbose_name_plural = 'Annonces de livraison fournisseur'
        ordering = ['-date_expedition', '-id']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_asnfou_co_statut'),
            models.Index(fields=['bon_commande_fournisseur', 'statut'],
                         name='idx_asnfou_bcf_statut'),
        ]

    def __str__(self):
        return (f'Annonce {self.bon_commande_fournisseur_id} · '
                f'{self.get_statut_display()}')
