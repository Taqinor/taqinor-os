"""NTSUB26 — Archive de synthese des compteurs d'usage purges.

Les ``CompteurUsage`` ingeres s'accumulent ligne a ligne indefiniment. La
purge mensuelle agrege en UNE ligne par (societe, code compteur, periode) les
releves d'une periode DEJA FACTUREE et vieille de plus de 24 mois, puis
supprime le detail brut. Cette table porte l'agregat conserve.

Purement ADDITIF (creation de table) et revertable : aucune donnee existante
n'est touchee.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('contrats', '0047_ntsub24_parametres_abonnement'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompteurUsageArchive',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('code_compteur', models.CharField(max_length=100, verbose_name='Code du compteur')),
                ('periode', models.CharField(max_length=7, verbose_name='Période (AAAA-MM)')),
                ('quantite_totale', models.DecimalField(decimal_places=4, default=0, max_digits=18, verbose_name='Quantité totale')),
                ('nb_lignes', models.PositiveIntegerField(default=0, verbose_name='Relevés fondus dans l’agrégat')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': "Archive de compteur d'usage",
                'verbose_name_plural': "Archives de compteurs d'usage",
                'ordering': ['-periode', 'code_compteur', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='compteurusagearchive',
            constraint=models.UniqueConstraint(fields=('company', 'code_compteur', 'periode'), name='contrats_compteurarch_uniq'),
        ),
        migrations.AddIndex(
            model_name='compteurusagearchive',
            index=models.Index(fields=['company', 'periode'], name='contrats_compteurarch_co_pe'),
        ),
    ]
