"""NTAPI7 — plans d'API nommés (gratuit/pro/entreprise) + quotas étendus.

Additif : `code` gagne des `choices` (gratuit/pro/entreprise — les lignes
existantes ont déjà `default='gratuit'`, valeur toujours valide) ; trois
nouveaux champs à défaut sûr (`quota_burst`, `retention_livraisons_jours`,
`nb_webhooks_max`) n'affectent aucune ligne existante."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0038_ntsec23_fieldpermissionrule'),
    ]

    operations = [
        migrations.AlterField(
            model_name='apiusageplan',
            name='code',
            field=models.CharField(
                choices=[
                    ('gratuit', 'Gratuit'),
                    ('pro', 'Pro'),
                    ('entreprise', 'Entreprise'),
                ],
                default='gratuit', max_length=40,
                help_text='Nom lisible du palier (gratuit / pro / entreprise).',
                verbose_name='Palier'),
        ),
        migrations.AddField(
            model_name='apiusageplan',
            name='quota_burst',
            field=models.PositiveIntegerField(
                default=0,
                help_text=(
                    'Requêtes en rafale tolérées au-delà du quota/minute '
                    '(0 = pas de marge supplémentaire).'),
                verbose_name='Marge de rafale'),
        ),
        migrations.AddField(
            model_name='apiusageplan',
            name='retention_livraisons_jours',
            field=models.PositiveIntegerField(
                default=30,
                help_text=(
                    'Durée de rétention des livraisons webhook (jours) avant '
                    'purge/archivage.'),
                verbose_name='Rétention livraisons (jours)'),
        ),
        migrations.AddField(
            model_name='apiusageplan',
            name='nb_webhooks_max',
            field=models.PositiveIntegerField(
                default=5,
                help_text='Nombre maximum de webhooks actifs pour cette société.',
                verbose_name='Webhooks max'),
        ),
    ]
