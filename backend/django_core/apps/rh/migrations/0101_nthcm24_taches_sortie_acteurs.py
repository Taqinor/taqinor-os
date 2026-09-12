# NTHCM24 — tâches d'offboarding multi-acteurs (symétrique de NTHCM23).
#
# ADDITIF et SÛR : AddField à défaut / NULL uniquement (piège YDATA20 évité).
# Les défauts (`rh`, assignation et échéance nulles) reproduisent exactement le
# comportement historique de la checklist de sortie.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('rh', '0100_nthcm23_taches_integration_acteurs'),
    ]

    operations = [
        migrations.AddField(
            model_name='elementsortie',
            name='acteur_type',
            field=models.CharField(
                choices=[('rh', 'RH'), ('manager', 'Manager'),
                         ('it', 'Informatique'),
                         ('employe_lui_meme', "L'employé lui-même")],
                default='rh', max_length=16, verbose_name='Acteur'),
        ),
        migrations.AddField(
            model_name='elementsortie',
            name='assigne_a',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='rh_taches_sortie',
                to=settings.AUTH_USER_MODEL, verbose_name='Assignée à'),
        ),
        migrations.AddField(
            model_name='elementsortie',
            name='echeance',
            field=models.DateField(
                blank=True, null=True, verbose_name='Échéance'),
        ),
    ]
