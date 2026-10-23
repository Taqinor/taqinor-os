"""AGQ10 / AGQ39 — colonnes POMPAGE du lead posées par l'audit agricole du
23/10/2026 (D-AGQ-6, D-AGQ-10), portées par un modèle ABSTRAIT hérité par
``Lead`` : ``apps/crm/models.py`` est un fichier-mur (C20) qui ne grossit plus,
chaque groupe de colonnes nouvelles vit dans son module (patron SPL).

Les champs appartiennent à la table ``crm_lead`` (migrations 0138 et 0139) ;
``Lead.ModePompe`` et ``Lead.PompeActuellePhases`` restent accessibles par
héritage. Aucun défaut : un champ vide veut dire « pas encore posée ».
"""
from django.db import models


class LeadPompageMixin(models.Model):
    """Mode de pompe, plaque de la pompe actuelle et jours d'irrigation."""

    # AGQ39 (D-AGQ-10) — le choix du lead lu par le devis automatique : pompe
    # neuve, ou pompe ACTUELLE conservée (D-AGR-7, variateur sur la plaque).
    class ModePompe(models.TextChoices):
        NEUVE = 'neuve', 'Pompe neuve'
        EXISTANTE = 'existante', 'Pompe actuelle conservée'

    class PompeActuellePhases(models.TextChoices):
        MONO = 'mono', 'Monophasé'
        TRI = 'tri', 'Triphasé'

    # AGQ39 (D-AGQ-10) — mode de pompe + plaque de la pompe ACTUELLE. Sans
    # défaut : un mode vide part en « neuve », étiqueté « par défaut » ;
    # « existante » exige la plaque complète (kW, tension, phases).
    mode_pompe = models.CharField(
        max_length=10, choices=ModePompe.choices, null=True, blank=True,
        verbose_name='Mode de pompe',
        help_text="Question à l'appel : « On installe une pompe neuve, ou on "
                  'garde votre pompe actuelle et on la passe au solaire ? » '
                  '(neuve ou existante conservée, vide = pas encore posée).')
    pompe_actuelle_kw = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name='Pompe actuelle — puissance plaque (kW)',
        help_text="Question à l'appel : « Quelle puissance en kW est écrite "
                  'sur la plaque de votre pompe actuelle ? » (kW, vide = pas '
                  'encore posée).')
    pompe_actuelle_tension_v = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='Pompe actuelle — tension plaque (V)',
        help_text="Question à l'appel : « Quelle tension est écrite sur la "
                  'plaque : 220 V ou 380 V ? » (volts, vide = pas encore '
                  'posée).')
    pompe_actuelle_phases = models.CharField(
        max_length=4, choices=PompeActuellePhases.choices, null=True,
        blank=True, verbose_name='Pompe actuelle — phases plaque',
        help_text="Question à l'appel : « Sur la plaque, la pompe est-elle "
                  'monophasée ou triphasée ? » (vide = pas encore posée).')
    # AGQ10 (D-AGQ-6) — la dépense butane « par jour d'irrigation » exige les
    # jours d'irrigation par semaine : sans eux, le bloc « Votre argent » d'un
    # devis automatique reste omis. Aucun défaut (vide = pas encore posée).
    jours_irrigation_semaine = models.DecimalField(
        max_digits=3, decimal_places=1, null=True, blank=True,
        verbose_name="Jours d'irrigation par semaine",
        help_text="Question à l'appel : « Vous irriguez combien de jours par "
                  "semaine en saison ? » (1 à 7, vide = pas encore posée).")

    class Meta:
        abstract = True
