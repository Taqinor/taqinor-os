"""AGQ10 / AGQ39 — colonnes POMPAGE du lead posées par l'audit agricole du
23/10/2026 (D-AGQ-6, D-AGQ-10), portées par un modèle ABSTRAIT hérité par
``Lead`` : ``apps/crm/models.py`` est un fichier-mur (C20) qui ne grossit plus,
chaque groupe de colonnes nouvelles vit dans son module (patron SPL).

Les champs appartiennent à la table ``crm_lead`` (migrations 0138 et 0139) ;
``Lead.ModePompe`` et ``Lead.PompeActuellePhases`` restent accessibles par
héritage. Aucun défaut : un champ vide veut dire « pas encore posée ».
"""
from django.db import models


def valider_mois_irrigation(valeur):
    """AGR400 — ``Lead.mois_irrigation`` : liste d'entiers 1-12 DISTINCTS.

    Déplacé ici avec les colonnes pompage (AGQ10) ; la migration 0118 le lit
    toujours via ``apps.crm.models`` (même objet, ré-importé).

    Vide (None ou liste vide) = question pas encore posée. Toute autre forme
    est refusée avec un message qui nomme les mois.
    """
    from django.core.exceptions import ValidationError
    if valeur in (None, []):
        return
    message = ("« Mois d'irrigation » : une liste de mois distincts, "
               'chacun entre 1 et 12.')
    if not isinstance(valeur, list):
        raise ValidationError(message)
    for mois in valeur:
        if isinstance(mois, bool) or not isinstance(mois, int) \
                or not 1 <= mois <= 12:
            raise ValidationError(message)
    if len(set(valeur)) != len(valeur):
        raise ValidationError(message)


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

    # AGR4xx — énergie ACTUELLE du pompage (butane/gasoil) : déclarations du
    # client, jamais pré-remplies (déplacées ici avec les colonnes pompage).
    butane_bouteilles_jour = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        verbose_name='Butane — bouteilles par jour',
        help_text="Question à l'appel : « Combien de bouteilles de butane "
                  'par jour en saison ? » (bouteilles de 12 kg par jour '
                  "d'irrigation, vide = pas encore posée).")
    carburant_prix_unitaire_mad = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Prix payé (bouteille ou litre, MAD)',
        help_text="Question à l'appel : « Vous la payez combien, la "
                  'bouteille (ou le litre de gasoil) ? » (MAD, vide = pas '
                  'encore posée). Prix PAYÉ déclaré, jamais pré-rempli.')
    carburant_prix_declare_le = models.DateField(
        null=True, blank=True, verbose_name='Prix du carburant déclaré le')
    depense_carburant_mad_mois = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Dépense carburant (MAD/mois)',
        help_text="Question à l'appel : « Combien dépensez-vous en "
                  'carburant par mois ? » (MAD/mois, vide = pas encore '
                  'posée). Information : jamais convertie en consommation.')
    # AGV1 (D-AGR-5) — pompe actuelle sur le RÉSEAU : sans la facture
    # d'électricité du pompage, les économies d'un client déjà électrique
    # n'ont aucune base déclarée. Facultative, jamais pré-remplie.
    depense_electricite_pompe_mad_mois = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Facture électricité du pompage (MAD/mois)',
        help_text="Question à l'appel : « Si votre pompe actuelle marche "
                  "à l'électricité, combien payez-vous par mois pour le "
                  'pompage ? » (MAD/mois, facultatif, vide = pas encore '
                  "posée).")
    # AGV8 (décision prise pour le fondateur, à revoir) — la part fixe de cette
    # facture : sans elle l'économie réseau est omise, jamais supposée à 0.
    depense_electricite_pompe_part_fixe_mad_mois = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Part fixe de la facture électricité du pompage '
                     '(MAD/mois)',
        help_text="Question à l'appel : « Sur cette facture, combien est "
                  'fixe chaque mois (abonnement, redevance), même sans '
                  'pomper ? » (MAD/mois, facultatif, vide = pas encore '
                  'posée).')

    class Meta:
        abstract = True
