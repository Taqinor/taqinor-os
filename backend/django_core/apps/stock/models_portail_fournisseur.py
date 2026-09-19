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
