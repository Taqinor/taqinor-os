"""NTWMS40 — Réapprovisionnement d'un casier PICKING depuis le STOCKAGE.

Un casier de prélèvement qui tombe à zéro arrête la vague : le magasinier
découvre la rupture au moment où il vient chercher la pièce. Ce lot pose le
SEUIL par casier et la TÂCHE de réappro interne qui transfère depuis le casier
de stockage le plus proche — avant la rupture, pas après.

ADAPTATION DE PÉRIMÈTRE (assumée, testée). ``installations.BinLocation``
(FG319) ne porte NI ``type_bin`` NI seuil — le constat est déjà celui de
NTWMS31 et NTWMS39, et cette lane n'écrit jamais dans ``installations``. Le
seuil est donc un satellite 1-1 de ``stock`` : poser un seuil sur un casier,
c'est le DÉCLARER casier de picking. Un casier sans seuil n'est jamais dû —
donc rien ne change pour les sociétés qui n'en déclarent aucun.

La tâche demandait un « ``TachePicking`` de type REAPPRO_INTERNE, distincte
d'une ``LignePicking`` client » : c'est exactement ce qu'est
``TacheReapproInterne`` — un document séparé, qui ne pollue jamais une vague
de prélèvement client (NTWMS4).
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel


class SeuilReapproCasier(TenantModel):
    """Seuil de réapprovisionnement d'UN casier de picking.

    ``quantite_cible`` vide = on remonte au double du seuil (règle
    conservatrice identique à ``Produit.quantite_reappro_cible``, FG54).
    """

    bin = models.OneToOneField(
        'installations.BinLocation', on_delete=models.CASCADE,  # on_delete: CASCADE — le seuil ne décrit QUE ce casier ; sans lui il ne déclenche plus rien (composition stricte)
        related_name='seuil_reappro_stock')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,  # on_delete: CASCADE — un seuil vise UN produit dans UN casier ; le produit supprimé, le seuil n'a plus d'objet (paramétrage reconstructible, aucune donnée réelle)
        related_name='seuils_reappro_casier')
    seuil = models.PositiveIntegerField(
        default=0,
        help_text='Sous cette quantité, le casier est dû en réappro interne.')
    quantite_cible = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Quantité à remonter (vide = seuil × 2).')
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Seuil de réappro casier'
        verbose_name_plural = 'Seuils de réappro casier'
        ordering = ['bin_id']
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='idx_seuilreap_co_actif'),
        ]

    def __str__(self):
        return f'{self.bin_id} < {self.seuil}'

    @property
    def cible(self):
        return self.quantite_cible or (self.seuil * 2)


class TacheReapproInterne(TenantModel):
    """Mouvement INTERNE demandé : remonter un casier picking sous son seuil.

    DISTINCTE d'une ``LignePicking`` (NTWMS4) : celle-ci sert un client ou un
    chantier, celle-là ne sert que le magasin. Elle ne bouge aucun stock par
    elle-même — c'est un ORDRE de travail, exécuté au poste scanner comme tout
    déplacement de casier.
    """

    class Statut(models.TextChoices):
        A_FAIRE = 'a_faire', 'À faire'
        FAITE = 'faite', 'Faite'
        ANNULEE = 'annulee', 'Annulée'

    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT,  # on_delete: PROTECT — trace d'exécution magasin (aligné sur MouvementStock/LignePicking)
        related_name='taches_reappro_interne')
    bin_cible = models.ForeignKey(
        'installations.BinLocation', on_delete=models.CASCADE,  # on_delete: CASCADE — la tâche remplit CE casier ; sans lui elle n'a plus de destination (composition stricte)
        related_name='taches_reappro_cible_stock')
    bin_source = models.ForeignKey(
        'installations.BinLocation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='taches_reappro_source_stock')
    quantite = models.PositiveIntegerField(default=0)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.A_FAIRE)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='taches_reappro_interne_creees')
    note = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Tâche de réappro interne'
        verbose_name_plural = 'Tâches de réappro interne'
        ordering = ['-created_at']
        constraints = [
            # Une seule tâche OUVERTE par casier cible : sans elle, chaque
            # passage du calcul empilerait un doublon sur le même casier.
            models.UniqueConstraint(
                fields=['company', 'bin_cible'],
                condition=models.Q(statut='a_faire'),
                name='stock_reappro_bin_cible_ouverte_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_reappro_co_statut'),
        ]

    def __str__(self):
        return f'Réappro {self.bin_cible_id} × {self.quantite}'
