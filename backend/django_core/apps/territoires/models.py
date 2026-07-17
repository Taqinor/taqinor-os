"""NTCRM1 — Moteur de territoires (règles d'affectation).

Nouvelle app scopée société : un ``Territoire`` (géo/segment/secteur) porte des
règles ordonnées (``TerritoireRegle``, conditions réutilisant le moteur pur
``core.rules`` — FG367) qui, une fois matchées, déclenchent une rotation
round-robin PARMI les membres du territoire (``TerritoireMembre``). Aucun
import de modèle cross-app ici (Territoire ne dépend que de la fondation
``authentication.Company`` + ``AUTH_USER_MODEL``) — la consultation d'un lead
réel passe par ``apps.crm.selectors`` (lecture) et l'écriture (assignation +
chatter) reste orchestrée depuis ``apps.crm.services`` / ``apps.territoires.
services`` (imports fonction-locaux, jamais au niveau module).
"""
from django.conf import settings
from django.db import models


class Territoire(models.Model):
    class TypeTerritoire(models.TextChoices):
        GEO = 'geo', 'Géographique'
        SEGMENT = 'segment', 'Segment'
        SECTEUR = 'secteur', 'Secteur'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='territoires')
    nom = models.CharField(max_length=120)
    type_territoire = models.CharField(
        max_length=10, choices=TypeTerritoire.choices,
        default=TypeTerritoire.GEO, verbose_name='Type')
    # Description informative des critères (région/ville/CP, type_installation,
    # tranche CA) — affichée dans l'UI. Le matching RÉEL passe TOUJOURS par les
    # conditions structurées de ``TerritoireRegle.condition`` (core.rules).
    criteres = models.JSONField(
        null=True, blank=True,
        help_text="Description libre des critères (région/ville/CP, "
                  "type_installation, tranche CA) — informative.")
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nom']
        verbose_name = 'Territoire'
        verbose_name_plural = 'Territoires'

    def __str__(self):
        return self.nom


class TerritoireRegle(models.Model):
    """Règle de matching d'un territoire, évaluée par ``core.rules.
    evaluate_condition_group`` contre un contexte plat dérivé du lead (ville,
    type_installation, montant_estime, canal…). Ordonnée par priorité
    croissante ; la première règle ACTIVE qui matche, parmi tous les
    territoires actifs de la société, gagne."""
    territoire = models.ForeignKey(
        Territoire, on_delete=models.CASCADE, related_name='regles')
    ordre = models.PositiveIntegerField(
        default=0, verbose_name='Ordre de priorité')
    condition = models.JSONField(
        help_text="Arbre de conditions (core.rules FG367) évalué contre les "
                  "attributs du lead entrant.")
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ['ordre', 'id']
        verbose_name = 'Règle de territoire'
        verbose_name_plural = 'Règles de territoire'

    def __str__(self):
        return f'{self.territoire.nom} — règle #{self.ordre}'


class TerritoireMembre(models.Model):
    """Un commercial rattaché à un territoire, avec un quota de rotation
    optionnel. ``nb_assignations``/``dernier_assigne_at`` portent l'état de la
    rotation round-robin (NTCRM2) — jamais un pur modulo sur ``count()``."""
    territoire = models.ForeignKey(
        Territoire, on_delete=models.CASCADE, related_name='membres')
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='territoires_membre')
    quota_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='Quota de rotation (%)',
        help_text='Vide = pas de quota, rotation équitable simple.')
    nb_assignations = models.PositiveIntegerField(default=0)
    dernier_assigne_at = models.DateTimeField(null=True, blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ['id']
        unique_together = [('territoire', 'utilisateur')]
        verbose_name = 'Membre de territoire'
        verbose_name_plural = 'Membres de territoire'

    def __str__(self):
        return f'{self.territoire.nom} — {self.utilisateur}'
