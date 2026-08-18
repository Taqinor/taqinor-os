"""PVMRQ — ParametresGammes : offre à deux gammes paramétrable (fondateur 18/08/2026).

Additive only : crée la table ``ventes_parametresgammes`` (singleton par
société, get-or-create via ``services.get_parametres_gammes``). Aucune table
ni colonne existante n'est modifiée. Entièrement révertable.

Multi-tenancy : ``company`` forcée au niveau vue/service ; jamais acceptée du
corps de la requête.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('ventes', '0096_pv41_conception_electrique'),
    ]

    operations = [
        migrations.CreateModel(
            name='ParametresGammes',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deux_gammes', models.BooleanField(
                    default=False,
                    verbose_name='Offre à deux gammes',
                    help_text="False = le devis n'utilise QU'UNE gamme "
                              "(comportement historique). True = les deux "
                              "gammes Essentielle/Premium sont produites "
                              "(paire de devis frères).")),
                ('nom_essentielle', models.CharField(
                    default='Essentielle', max_length=60,
                    verbose_name='Libellé de la gamme Essentielle',
                    help_text='Libellé affiché, renommable sans changement '
                              'de code (ex. « Standard »).')),
                ('nom_premium', models.CharField(
                    default='Premium', max_length=60,
                    verbose_name='Libellé de la gamme Premium',
                    help_text='Libellé affiché, renommable sans changement '
                              'de code (ex. « Luxe »).')),
                ('marques', models.JSONField(
                    blank=True, default=dict,
                    verbose_name='Marques préférées par gamme et par rôle',
                    help_text="{'Essentielle': {rôle: marque}, 'Premium': "
                              "{rôle: marque}} — voir la docstring de la "
                              "classe.")),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company',
                    verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Paramètres gammes',
                'verbose_name_plural': 'Paramètres gammes',
            },
        ),
        migrations.AddConstraint(
            model_name='parametresgammes',
            constraint=models.UniqueConstraint(
                fields=('company',), name='uniq_parametres_gammes_company'),
        ),
    ]
