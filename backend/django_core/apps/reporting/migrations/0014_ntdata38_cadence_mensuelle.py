"""NTDATA38 — cadences fines des rapports planifiés : mensuel + fenêtre d'envoi.

Trois changements ADDITIFS, tous inertes par défaut :
  * ``schedule`` gagne le membre ``monthly`` (``AlterField`` sur ``choices`` —
    aucun effet de schéma en base) ;
  * ``heure_envoi`` NULL = comportement historique (envoi au passage du
    planificateur) : aucun rapport existant ne change de fenêtre ;
  * ``jour_du_mois`` par défaut 1, borné à 28 pour qu'un mensuel tombe TOUS les
    mois (février compris).

CHAÎNE : enchaîne explicitement sur la dernière migration de ``reporting``.
"""
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0013_ntscm46_kpi_taux_service_scm'),
    ]

    operations = [
        migrations.AlterField(
            model_name='savedreport',
            name='schedule',
            field=models.CharField(
                choices=[('none', 'Aucune'), ('daily', 'Quotidien'),
                         ('weekly', 'Hebdomadaire'), ('monthly', 'Mensuel')],
                default='none', max_length=10),
        ),
        migrations.AddField(
            model_name='savedreport',
            name='heure_envoi',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="Heure locale (0-23) à laquelle envoyer. Vide = à "
                          "l'heure de passage du planificateur (comportement "
                          "historique).",
                null=True,
                validators=[django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(23)],
                verbose_name="Heure d'envoi"),
        ),
        migrations.AddField(
            model_name='savedreport',
            name='jour_du_mois',
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text="Jour d'envoi de la cadence mensuelle (1-28).",
                validators=[django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(28)],
                verbose_name='Jour du mois'),
        ),
    ]
