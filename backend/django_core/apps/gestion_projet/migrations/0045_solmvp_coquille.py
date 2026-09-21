"""SOLMVP — coquille de migrations de l'app « gestion_projet ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app gestion_projet`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate gestion_projet 0044_aud178_lignesituation_libelle_uniq`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_projet', '0044_aud178_lignesituation_libelle_uniq'),
        ('btp_chantier', '0015_solmvp_coquille'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='ActionProjet'),
                migrations.DeleteModel(name='AffectationRessource'),
                migrations.DeleteModel(name='BaselineTache'),
                migrations.DeleteModel(name='ChronoEnCours'),
                migrations.DeleteModel(name='ClotureProjet'),
                migrations.DeleteModel(name='CommentaireProjet'),
                migrations.DeleteModel(name='CompteRenduReunion'),
                migrations.DeleteModel(name='DependanceTache'),
                migrations.DeleteModel(name='EvaluationProjet'),
                migrations.DeleteModel(name='Indisponibilite'),
                migrations.DeleteModel(name='ItemChecklistTache'),
                migrations.DeleteModel(name='Jalon'),
                migrations.DeleteModel(name='JourFerie'),
                migrations.DeleteModel(name='LigneBudgetProjet'),
                migrations.DeleteModel(name='LigneSituation'),
                migrations.DeleteModel(name='LotSousTraitance'),
                migrations.DeleteModel(name='ModeleTache'),
                migrations.DeleteModel(name='PeriodeVerrouilleeTemps'),
                migrations.DeleteModel(name='PointAvancement'),
                migrations.DeleteModel(name='PortailProjetToken'),
                migrations.DeleteModel(name='ProjetActivity'),
                migrations.DeleteModel(name='ProjetChantier'),
                migrations.DeleteModel(name='ProjetLien'),
                migrations.DeleteModel(name='RecurrenceTache'),
                migrations.DeleteModel(name='ReglageTemps'),
                migrations.DeleteModel(name='Timesheet'),
                migrations.DeleteModel(name='VersionDocument'),
                migrations.DeleteModel(name='BaselinePlanning'),
                migrations.DeleteModel(name='BudgetProjet'),
                migrations.DeleteModel(name='CalendrierProjet'),
                migrations.DeleteModel(name='DocumentProjet'),
                migrations.DeleteModel(name='Equipe'),
                migrations.DeleteModel(name='ModeleProjet'),
                migrations.DeleteModel(name='Risque'),
                migrations.DeleteModel(name='SituationTravaux'),
                migrations.DeleteModel(name='SousTraitant'),
                migrations.DeleteModel(name='Tache'),
                migrations.DeleteModel(name='PhaseProjet'),
                migrations.DeleteModel(name='RessourceProfil'),
                migrations.DeleteModel(name='Projet'),
            ],
            database_operations=[],
        ),
    ]
