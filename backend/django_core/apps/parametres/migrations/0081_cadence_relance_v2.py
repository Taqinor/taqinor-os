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

L'index `(company, cadence, actif)` n'est PAS ici : il est posé EN CONCURRENT
par 0084 (YOPSB6), pour ne pas verrouiller la table en écriture.
"""
from django.db import migrations, models


#: Taille de lot du backfill. Le gabarit compte quelques lignes par société,
#: mais un `.update()` GLOBAL non borné prendrait quand même un verrou sur
#: toute la table — on découpe donc explicitement (garde
#: `check_safe_migrations`, UNBATCHED_RUNPYTHON_UPDATE).
TAILLE_LOT = 500


def etiqueter_generique(apps, schema_editor):
    """Toutes les lignes EXISTANTES sont l'échelle neutre historique.

    Backfill PAR LOTS : on parcourt les identifiants avec `.iterator()` et on
    met à jour par tranches de `TAILLE_LOT`, plutôt qu'un `.update()` global
    qui verrouillerait la table entière d'un coup."""
    Etape = apps.get_model('parametres', 'CadenceRelanceEtape')
    lot = []
    for pk in Etape.objects.values_list('pk', flat=True).iterator(
            chunk_size=TAILLE_LOT):
        lot.append(pk)
        if len(lot) >= TAILLE_LOT:
            Etape.objects.filter(pk__in=lot).update(cadence='generique')
            lot = []
    if lot:
        Etape.objects.filter(pk__in=lot).update(cadence='generique')


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
    ]
