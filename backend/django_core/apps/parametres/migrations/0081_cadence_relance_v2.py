"""MRY4 — `CadenceRelanceEtape` v2 : trois cadences nommées, minutes, gabarit.

DEUX temps, dans cet ordre, pour ne RIEN perdre :

  1. les cinq champs additifs (`cadence`, `delai_minutes`, `heure_cible`,
     `template_cle`, `dimanche_ok`) ;
  2. un `RunPython` qui étiquette `cadence='generique'` TOUTES les lignes
     existantes — les 5 barreaux neutres J+2/5/10/20/35. Sans lui, elles
     hériteraient du défaut `contact` et se percuteraient avec les barreaux
     du protocole de rappel sur la nouvelle clé d'unicité.

L'unicité passe de `(company, ordre)` à `(company, cadence, ordre)` APRÈS
l'étiquetage : l'ordre 1 existe désormais dans chaque cadence.

Rien n'est supprimé, rien n'est réécrit. `reverse` de l'étiquetage = no-op :
la colonne disparaît de toute façon au rollback du `AddField`.
"""
from django.db import migrations, models


def etiqueter_generique(apps, schema_editor):
    """Toutes les lignes EXISTANTES sont l'échelle neutre historique."""
    Etape = apps.get_model('parametres', 'CadenceRelanceEtape')
    Etape.objects.all().update(cadence='generique')


def noop(apps, schema_editor):
    """Rollback : la colonne `cadence` est retirée par le AddField inverse."""


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0080_remove_companyprofile_panneaux_par_900mad'),
    ]

    operations = [
        migrations.AddField(
            model_name='cadencerelanceetape',
            name='cadence',
            field=models.CharField(
                choices=[('contact', 'Prise de contact'),
                         ('apres_devis', 'Après devis'),
                         ('reveil', 'Réveil'),
                         ('generique', 'Générique (historique)')],
                default='contact', max_length=20, verbose_name='Cadence'),
        ),
        migrations.AddField(
            model_name='cadencerelanceetape',
            name='delai_minutes',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Minutes ajoutées au délai en jours (0 à 1439).'),
        ),
        migrations.AddField(
            model_name='cadencerelanceetape',
            name='heure_cible',
            field=models.TimeField(
                blank=True, null=True, verbose_name='Heure cible'),
        ),
        migrations.AddField(
            model_name='cadencerelanceetape',
            name='template_cle',
            field=models.CharField(
                blank=True, default='', max_length=40,
                verbose_name='Clé du gabarit de message'),
        ),
        migrations.AddField(
            model_name='cadencerelanceetape',
            name='dimanche_ok',
            field=models.BooleanField(
                default=False, verbose_name='Autorisée le dimanche'),
        ),
        # L'étiquetage tombe AVANT le changement d'unicité : sinon deux
        # cadences partageant l'ordre 1 entreraient en collision.
        migrations.RunPython(etiqueter_generique, noop),
        migrations.AlterUniqueTogether(
            name='cadencerelanceetape',
            unique_together={('company', 'cadence', 'ordre')},
        ),
        migrations.AlterModelOptions(
            name='cadencerelanceetape',
            options={
                'ordering': ['cadence', 'ordre', 'delai_jours'],
                'verbose_name': 'Étape de cadence de relance',
                'verbose_name_plural': 'Étapes de cadence de relance',
            },
        ),
        migrations.AddIndex(
            model_name='cadencerelanceetape',
            index=models.Index(fields=['company', 'cadence', 'actif'],
                               name='param_cad_co_cad_act_idx'),
        ),
    ]
