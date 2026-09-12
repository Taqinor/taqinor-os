# NTHCM23 — tâches d'onboarding multi-acteurs (acteur + échéance + assignation).
#
# ADDITIF et SÛR : AddField à défaut / NULL uniquement — aucun AddField(unique),
# aucun NOT NULL sans défaut (piège YDATA20). Les défauts (`rh`, 0 jour,
# assignation nulle) reproduisent EXACTEMENT le comportement historique : une
# ligne existante ne change pas de sens.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('rh', '0099_nthcm21_titre_delivre_parcours'),
    ]

    operations = [
        migrations.AddField(
            model_name='elementintegration',
            name='acteur_type',
            field=models.CharField(
                choices=[('rh', 'RH'), ('manager', 'Manager'),
                         ('it', 'Informatique'),
                         ('employe_lui_meme', "L'employé lui-même")],
                default='rh', max_length=16, verbose_name='Acteur'),
        ),
        migrations.AddField(
            model_name='elementintegration',
            name='delai_jours',
            field=models.PositiveIntegerField(
                default=0,
                verbose_name="Échéance (jours après l'embauche)"),
        ),
        migrations.AddField(
            model_name='elementintegrationemploye',
            name='acteur_type',
            field=models.CharField(
                choices=[('rh', 'RH'), ('manager', 'Manager'),
                         ('it', 'Informatique'),
                         ('employe_lui_meme', "L'employé lui-même")],
                default='rh', max_length=16, verbose_name='Acteur'),
        ),
        migrations.AddField(
            model_name='elementintegrationemploye',
            name='assigne_a',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='rh_taches_integration',
                to=settings.AUTH_USER_MODEL, verbose_name='Assignée à'),
        ),
        migrations.AddField(
            model_name='elementintegrationemploye',
            name='echeance',
            field=models.DateField(
                blank=True, null=True, verbose_name='Échéance'),
        ),
        migrations.AddField(
            model_name='reglagerh',
            name='contact_it_defaut',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='rh_contact_it_par_defaut',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Contact informatique par défaut'),
        ),
    ]
