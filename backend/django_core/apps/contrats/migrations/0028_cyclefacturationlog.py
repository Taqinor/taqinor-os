import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('contrats', '0027_piececonformite'),
    ]

    operations = [
        migrations.CreateModel(
            name='CycleFacturationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_type', models.CharField(choices=[('contrat', 'Contrat (échéancier)'), ('sav_maintenance', 'Maintenance SAV')], max_length=20, verbose_name='Type de source')),
                ('source_id', models.PositiveIntegerField(verbose_name='ID de la source')),
                ('periode', models.CharField(max_length=20, verbose_name='Période')),
                ('statut', models.CharField(choices=[('genere', 'Générée'), ('echec', 'Échec'), ('saute', 'Sautée')], max_length=10, verbose_name='Statut')),
                ('motif', models.TextField(blank=True, default='', verbose_name='Motif (échec/saut)')),
                ('facture_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='ID de la facture émise')),
                ('nb_tentatives', models.PositiveIntegerField(default=1, verbose_name='Nombre de tentatives')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contrats_cycles_facturation', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Journal de cycle de facturation',
                'verbose_name_plural': 'Journaux de cycles de facturation',
                'ordering': ['-date_creation', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='cyclefacturationlog',
            index=models.Index(fields=['company', 'statut'], name='contrats_cyclelog_co_st'),
        ),
        migrations.AddIndex(
            model_name='cyclefacturationlog',
            index=models.Index(fields=['source_type', 'source_id', 'periode'], name='contrats_cyclelog_src_per'),
        ),
    ]
