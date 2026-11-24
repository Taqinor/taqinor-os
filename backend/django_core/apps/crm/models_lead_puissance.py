"""Colonnes « puissance maximale appelée » du lead PRO (décision fondateur du
24/11/2026, lead « Karim Hasnaoui »), portées par un modèle ABSTRAIT hérité
par ``Lead`` : ``apps/crm/models.py`` est un fichier-mur (C20) qui ne grossit
plus, chaque groupe de colonnes nouvelles vit dans son module (patron SPL,
comme ``models_lead_pompage``).

Un client qui ne connaît que la puissance MAXIMALE de son site (380 kVA) n'a
pas de consommation : le moteur C&I l'ESTIME en dernier recours —
kVA max × cos φ × charge moyenne × heures d'ouverture du mois
(``apps/ventes/domain/estimation_puissance_ci.py``), une estimation dite,
sous réserve de visite, que toute consommation réelle remplace.

Les champs appartiennent à la table ``crm_lead`` (migration 0166). Aucun
défaut enregistré : un champ vide veut dire « pas encore posée » (la charge
vide est SUPPOSÉE à 50 % par le calcul, jamais écrite sur le lead).

``valider_cos_phi`` (validateur de ``Lead.cos_phi``, la grandeur électrique
que l'estimation lit aussi) vit ici depuis le 24/11/2026 : ``models.py`` le
ré-importe (même objet), les migrations le lisent toujours via
``apps.crm.models``.
"""
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def valider_cos_phi(valeur):
    """CIQ401 — un cos φ est dans ]0 ; 1] (jamais supposé : vide sinon)."""
    from django.core.exceptions import ValidationError
    if valeur is None:
        return
    if not 0 < valeur <= 1:
        raise ValidationError(
            '« Cos φ » : une valeur strictement positive, au plus 1.')


class LeadPuissanceMaxMixin(models.Model):
    """Puissance maximale appelée et charge moyenne pendant les heures d'ouverture."""

    # DISTINCTE de ``compteur_puissance_kva`` (la puissance SOUSCRITE au
    # contrat, qui plafonne la puissance AC des onduleurs) : celle-ci ne sert
    # qu'à estimer une consommation quand aucune n'est connue.
    puissance_max_appelee_kva = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Puissance maximale appelée (kVA)',
        help_text="Question à l'appel : « Quelle est la puissance maximale que "
                  'votre site appelle, en kVA ? » (vide = pas encore posée). '
                  "DISTINCTE de la puissance souscrite du compteur : elle "
                  "ne sert qu'à ESTIMER la consommation quand aucune n'est "
                  'connue (estimation dite, sous réserve de visite).')
    charge_moyenne_pct = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name="Charge moyenne pendant les heures d'ouverture (%)",
        help_text="Question à l'appel : « Pendant vos heures d'ouverture, le "
                  'site tourne en moyenne à quel pourcentage de cette '
                  'puissance maximale ? » (1 à 100 ; vide = 50 % supposés '
                  "par le calcul, décision fondateur du 24/11/2026).")

    class Meta:
        abstract = True
