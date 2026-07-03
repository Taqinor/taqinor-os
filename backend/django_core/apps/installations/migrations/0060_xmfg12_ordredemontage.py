import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0059_xmfg11_taux_perte'),
        ('stock', '0029_xmfg11_rebut'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='OrdreDemontage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference', models.CharField(max_length=50)),
                ('quantite', models.PositiveIntegerField(default=1)),
                ('statut', models.CharField(choices=[('planifie', 'Planifié'), ('termine', 'Terminé')], default='planifie', max_length=20)),
                ('note', models.TextField(blank=True, null=True)),
                ('stock_mouvemente', models.BooleanField(default=False)),
                ('date_terminaison', models.DateTimeField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_ordres_demontage', to='authentication.company')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_ordres_demontage_crees', to=settings.AUTH_USER_MODEL)),
                ('emplacement_destination', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_ordres_demontage_destination', to='stock.emplacementstock')),
                ('emplacement_source', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_ordres_demontage_source', to='stock.emplacementstock')),
                ('kit', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='ordres_demontage', to='installations.kit')),
            ],
            options={
                'verbose_name': 'Ordre de démontage',
                'verbose_name_plural': 'Ordres de démontage',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.CreateModel(
            name='OrdreDemontageLigne',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('designation', models.CharField(blank=True, max_length=255, null=True)),
                ('quantite_attendue', models.PositiveIntegerField(default=0)),
                ('quantite_recuperee', models.PositiveIntegerField(default=0)),
                ('ordre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='installations.ordredemontage')),
                ('produit', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_ordre_demontage_lignes', to='stock.produit')),
            ],
            options={
                'verbose_name': 'Ligne de démontage',
                'verbose_name_plural': 'Lignes de démontage',
                'ordering': ['ordre_id', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='ordredemontage',
            index=models.Index(fields=['company', 'statut'], name='idx_dsm_co_statut'),
        ),
        migrations.AddIndex(
            model_name='ordredemontage',
            index=models.Index(fields=['company', 'kit'], name='idx_dsm_co_kit'),
        ),
        migrations.AlterUniqueTogether(
            name='ordredemontage',
            unique_together={('company', 'reference')},
        ),
        migrations.AddIndex(
            model_name='ordredemontageligne',
            index=models.Index(fields=['ordre'], name='idx_dsmligne_ordre'),
        ),
    ]
