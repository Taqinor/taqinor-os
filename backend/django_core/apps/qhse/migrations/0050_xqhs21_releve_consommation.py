import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0049_xqhs20_aspect_environnemental'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReleveConsommation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('site_libelle', models.CharField(max_length=255, verbose_name='Site / libellé')),
                ('type_energie', models.CharField(choices=[('electricite', 'Électricité (kWh)'), ('gasoil', 'Gasoil (L)'), ('essence', 'Essence (L)'), ('eau', 'Eau (m³)')], default='electricite', max_length=15, verbose_name="Type d'énergie")),
                ('periode', models.DateField(verbose_name='Période (mois)')),
                ('quantite', models.DecimalField(decimal_places=3, default=0, max_digits=14, verbose_name='Quantité')),
                ('source', models.CharField(choices=[('facture', 'Facture'), ('compteur', 'Compteur')], default='facture', max_length=15, verbose_name='Source')),
                ('piece_jointe_url', models.CharField(blank=True, default='', max_length=500, verbose_name='Pièce jointe (URL)')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_releves_consommation', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Relevé de consommation',
                'verbose_name_plural': 'Relevés de consommation',
                'ordering': ['-periode', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='releveconsommation',
            constraint=models.UniqueConstraint(fields=('company', 'site_libelle', 'type_energie', 'periode'), name='qhse_relconso_co_site_type_periode_uniq'),
        ),
        migrations.AddIndex(
            model_name='releveconsommation',
            index=models.Index(fields=['company', 'periode'], name='qhse_relconso_co_periode'),
        ),
    ]
