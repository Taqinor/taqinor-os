"""
FG305 — Ordres de travaux émis à un sous-traitant chantier.

``OrdreSousTraitance`` matérialise la commande de PRESTATION passée à un
sous-traitant de l'annuaire (``SousTraitant``, FG304) : pour TEL chantier
(``Installation``, même app), TELLE prestation (terrassement, génie civil,
pose…), pour TEL montant, à émettre/réceptionner/clôturer. C'est le pendant
« main-d'œuvre sous-traitée » du bon de commande matériel — mais distinct : on
ne commande pas du panneau ici, on commande une intervention de pose/travaux.

Couche de statut PROPRE — distincte des trois couches de l'OS (entonnoir
``STAGES.py``, statut document devis/facture, statut chantier). Le ``Statut``
ci-dessous (brouillon → émis → en cours → réceptionné → clos) est le cycle de
vie de l'ORDRE lui-même, jamais l'un des autres. « annulé » n'en fait pas
partie ; un ordre se clôt, il ne s'annule pas (la liste reste fermée et courte).

Numérotation : la référence ``OST-YYYYMM-NNNN`` est posée CÔTÉ SERVEUR via le
numéroteur anti-collision partagé (``apps.ventes.utils.references`` ; jamais
``count()+1``), tenant-scopée par l'unicité ``(company, reference)``.

Additif & multi-tenant : on AJOUTE une table avec une FK ``company`` posée côté
serveur, jamais lue du corps de la requête. ``sous_traitant`` et ``chantier``
sont validés tenant (même société) côté vue.
"""
from django.conf import settings
from django.db import models


class OrdreSousTraitance(models.Model):
    """FG305 — un ordre de travaux émis à un sous-traitant chantier.

    Relie un ``SousTraitant`` (FG304, prestataire de main-d'œuvre) à un
    ``chantier`` (``Installation``, même app, optionnel) pour une ``prestation``
    décrite, un ``montant`` engagé et une ``date_echeance``. ``montant_realise``
    (optionnel) capture le réalisé à la réception. Le ``statut`` suit le cycle de
    vie de l'ordre, distinct de toute autre couche de statut de l'OS.

    Multi-tenant : la société est posée côté serveur. La référence
    ``OST-YYYYMM-NNNN`` est anti-collision (jamais count()+1)."""

    class Statut(models.TextChoices):
        # Machine à états PROPRE à l'ordre — distincte de toute autre couche.
        BROUILLON = 'brouillon', 'Brouillon'
        EMIS = 'emis', 'Émis'
        EN_COURS = 'en_cours', 'En cours'
        RECEPTIONNE = 'receptionne', 'Réceptionné'
        CLOS = 'clos', 'Clos'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_ordres_sous_traitance')
    reference = models.CharField(max_length=50)
    # Prestataire de main-d'œuvre (annuaire FG304). PROTECT : on ne supprime pas
    # un sous-traitant qui porte des ordres.
    sous_traitant = models.ForeignKey(
        'installations.SousTraitant', on_delete=models.PROTECT,
        related_name='installations_ordres_sous_traitance')
    # Chantier concerné (même app). Optionnel : un ordre cadre peut précéder
    # l'affectation à un chantier précis. SET_NULL : la suppression d'un chantier
    # ne détruit pas l'historique de l'ordre.
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_ordres_sous_traitance')
    prestation = models.TextField()
    # Montant engagé (HT, MAD). DecimalField : jamais de flottant sur de l'argent.
    montant = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    # Réalisé à la réception (optionnel) — peut différer du montant engagé.
    montant_realise = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    date_emission = models.DateField(null=True, blank=True)
    date_echeance = models.DateField(null=True, blank=True)
    # max_length=20 couvre le plus long code de Statut ('receptionne' = 11).
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_ordres_sous_traitance_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Ordre de sous-traitance'
        verbose_name_plural = 'Ordres de sous-traitance'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]
        indexes = [
            # Noms d'index ≤ 30 caractères (contrainte Django/Postgres).
            models.Index(fields=['company', 'statut'],
                         name='idx_ost_co_statut'),
            models.Index(fields=['company', 'sous_traitant'],
                         name='idx_ost_co_soustrait'),
        ]

    def __str__(self):
        return f'{self.reference} · {self.sous_traitant_id}'
