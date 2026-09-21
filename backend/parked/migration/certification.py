"""NTMIG27 — barème & scoring de certification des partenaires intégrateurs.

Ce module PROPOSE un niveau ; il n'en ATTRIBUE jamais aucun. L'attribution
reste une action admin explicite sur la fiche partenaire (``crm.Partenaire.
niveau_certification``) : un score est une aide à la décision, pas une
promotion automatique — un partenaire ne doit jamais se retrouver « Or » parce
qu'il a saisi lui-même cinq déploiements.

Frontières cross-app respectées :

* la fiche partenaire vit dans ``crm`` — elle est LUE telle qu'on la reçoit et
  n'est jamais écrite ici (``crm.services`` seul écrit, cf. NTMIG28) ;
* la satisfaction client vient de ``qhse.selectors`` (jamais ``qhse.models``),
  en import PARESSEUX et en dégradation propre si l'app n'est pas installée ;
* les déploiements et projets de migration sont les modèles de CETTE app.

Barème (100 points au total) :

===========================  =======  ==================================
Composante                    Poids    Source
===========================  =======  ==================================
Déploiements réussis             45    ``DeploiementPartenaire`` (réussis)
                                       + projets de migration terminés
Satisfaction client              25    notes des déploiements, sinon QHSE
Ancienneté                       15    ``Partenaire.date_creation``
Spécialités déclarées            15    ``Partenaire.specialites``
===========================  =======  ==================================
"""
from datetime import date

from django.db.models import Avg

# Poids maximum de chaque composante (leur somme fait 100).
POIDS_DEPLOIEMENTS = 45
POIDS_SATISFACTION = 25
POIDS_ANCIENNETE = 15
POIDS_SPECIALITES = 15

POINTS_PAR_DEPLOIEMENT = 9
POINTS_PAR_ANNEE = 5
POINTS_PAR_SPECIALITE = 5

# Note maximale d'un ``DeploiementPartenaire.note_satisfaction`` (0-10).
NOTE_DEPLOIEMENT_MAX = 10

# Seuils de PROPOSITION de niveau (score → niveau proposé). Ordre décroissant.
SEUILS = (
    (85, 'platine'),
    (65, 'or'),
    (45, 'certifie'),
    (20, 'enregistre'),
)
NIVEAU_PLANCHER = 'aucun'


def _borner(valeur, maximum):
    return int(min(max(valeur, 0), maximum))


def _satisfaction_partenaire(partenaire):
    """Satisfaction du partenaire ramenée sur [0, 1], ou ``None``.

    PRIORITÉ aux notes de SES propres déploiements : la satisfaction QHSE de la
    société est un repli, pas un équivalent — l'attribuer telle quelle à un
    partenaire créditerait chacun de la moyenne de tous les autres.
    """
    from .models import DeploiementPartenaire

    moyenne = (DeploiementPartenaire.objects
               .filter(company_id=partenaire.company_id,
                       partenaire_id=partenaire.pk,
                       note_satisfaction__isnull=False)
               .aggregate(moy=Avg('note_satisfaction'))['moy'])
    if moyenne is not None and NOTE_DEPLOIEMENT_MAX:
        return ('deploiements',
                max(0.0, min(1.0, float(moyenne) / NOTE_DEPLOIEMENT_MAX)))

    # Repli QHSE — import PARESSEUX + dégradation propre : l'app peut être
    # absente, sans retour client, ou ne pas exposer le sélecteur.
    try:
        from apps.qhse import selectors as qhse_selectors

        valeur = qhse_selectors.satisfaction_normalisee(partenaire.company)
    except Exception:  # pragma: no cover - dégradation défensive
        valeur = None
    if valeur is None:
        return (None, None)
    return ('qhse', valeur)


def _anciennete_annees(partenaire):
    debut = getattr(partenaire, 'date_creation', None)
    if debut is None:
        return 0
    debut = getattr(debut, 'date', lambda: debut)()
    if not isinstance(debut, date):
        return 0
    aujourdhui = date.today()
    annees = aujourdhui.year - debut.year
    if (aujourdhui.month, aujourdhui.day) < (debut.month, debut.day):
        annees -= 1
    return max(0, annees)


def _projets_termines(partenaire):
    """Projets de migration TERMINÉS rattachés à un déploiement du partenaire.

    Un projet terminé sans déploiement enregistré ne crédite personne : c'est
    le déploiement qui dit QUI l'a mené (NTMIG28).
    """
    from .models import DeploiementPartenaire, ProjetMigration

    ids = (DeploiementPartenaire.objects
           .filter(company_id=partenaire.company_id,
                   partenaire_id=partenaire.pk,
                   projet_migration__isnull=False)
           .values_list('projet_migration_id', flat=True))
    if not ids:
        return 0
    return (ProjetMigration.objects
            .filter(company_id=partenaire.company_id, pk__in=list(ids),
                    statut=ProjetMigration.Statut.TERMINE)
            .count())


def niveau_propose_pour(score):
    """Niveau PROPOSÉ pour un score (jamais attribué automatiquement)."""
    for seuil, niveau in SEUILS:
        if score >= seuil:
            return niveau
    return NIVEAU_PLANCHER


def calculer_score_certification(partenaire):
    """Score de certification d'un partenaire + niveau PROPOSÉ.

    Renvoie un dict lisible tel quel par un écran d'administration :

    ``score`` (0-100), ``niveau_propose``, ``niveau_actuel``,
    ``proposition_differente`` (le niveau proposé diffère-t-il de l'actuel ?),
    ``detail`` (points par composante + la mesure brute qui les produit) et
    ``source_satisfaction``.

    N'ÉCRIT RIEN : l'attribution du niveau reste une action admin explicite.
    """
    from .models import DeploiementPartenaire

    nb_reussis = (DeploiementPartenaire.objects
                  .filter(company_id=partenaire.company_id,
                          partenaire_id=partenaire.pk,
                          statut=DeploiementPartenaire.Statut.REUSSI)
                  .count())
    nb_projets_termines = _projets_termines(partenaire)
    # Un projet de migration terminé ne s'ADDITIONNE pas au déploiement qui le
    # porte : il en est la preuve. Le compte retenu est celui des déploiements
    # réussis, jamais la somme des deux (elle compterait deux fois le même
    # travail).
    points_deploiements = _borner(
        nb_reussis * POINTS_PAR_DEPLOIEMENT, POIDS_DEPLOIEMENTS)

    source_satisfaction, satisfaction = _satisfaction_partenaire(partenaire)
    points_satisfaction = _borner(
        round((satisfaction or 0) * POIDS_SATISFACTION), POIDS_SATISFACTION)

    annees = _anciennete_annees(partenaire)
    points_anciennete = _borner(
        annees * POINTS_PAR_ANNEE, POIDS_ANCIENNETE)

    specialites = partenaire.specialites or []
    nb_specialites = len(specialites) if isinstance(specialites, list) else 0
    points_specialites = _borner(
        nb_specialites * POINTS_PAR_SPECIALITE, POIDS_SPECIALITES)

    score = (points_deploiements + points_satisfaction
             + points_anciennete + points_specialites)
    niveau_propose = niveau_propose_pour(score)
    niveau_actuel = partenaire.niveau_certification
    return {
        'partenaire': partenaire.pk,
        'partenaire_nom': partenaire.nom,
        'score': score,
        'niveau_propose': niveau_propose,
        'niveau_actuel': niveau_actuel,
        'proposition_differente': niveau_propose != niveau_actuel,
        'source_satisfaction': source_satisfaction,
        'detail': {
            'deploiements': {
                'nb_reussis': nb_reussis,
                'nb_projets_termines': nb_projets_termines,
                'points': points_deploiements,
                'maximum': POIDS_DEPLOIEMENTS,
            },
            'satisfaction': {
                # ``is not None`` et pas la véracité : une satisfaction
                # MESURÉE à 0 est une information, pas une absence de mesure.
                'ratio': (round(satisfaction, 3)
                          if satisfaction is not None else None),
                'points': points_satisfaction,
                'maximum': POIDS_SATISFACTION,
            },
            'anciennete': {
                'annees': annees,
                'points': points_anciennete,
                'maximum': POIDS_ANCIENNETE,
            },
            'specialites': {
                'nb': nb_specialites,
                'points': points_specialites,
                'maximum': POIDS_SPECIALITES,
            },
        },
        # Rappel porté par la donnée elle-même : aucun écran ne doit croire
        # que ce calcul a promu qui que ce soit.
        'attribution': 'manuelle',
    }
