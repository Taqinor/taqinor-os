# NTSCM1 — modèle initial PrevisionDemande.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0027_ntadm22_customuser_is_taqinor_support'),
        ('stock', '0085_ntadm2_produit_entite'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PrevisionDemande',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('segment', models.CharField(blank=True, default='', help_text='Ville, canal, type_installation… texte libre, vide = tous segments.', max_length=100, verbose_name='Segment')),
                ('periode', models.CharField(max_length=7, verbose_name='Période (YYYY-MM)')),
                ('quantite_prevue', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Quantité prévue')),
                ('methode', models.CharField(choices=[('moyenne_mobile', 'Moyenne mobile'), ('tendance', 'Tendance'), ('saisonnier', 'Saisonnier'), ('manuel', 'Manuel')], default='manuel', max_length=20, verbose_name='Méthode')),
                ('genere_le', models.DateTimeField(blank=True, null=True, verbose_name='Généré le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scm_previsions_demande', to='authentication.company', verbose_name='Société')),
                ('genere_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='scm_previsions_generees', to=settings.AUTH_USER_MODEL, verbose_name='Généré par')),
                ('produit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scm_previsions_demande', to='stock.produit', verbose_name='Produit')),
            ],
            options={
                'verbose_name': 'Prévision de demande',
                'verbose_name_plural': 'Prévisions de demande',
                'ordering': ['-periode', 'produit_id'],
            },
        ),
        migrations.AddConstraint(
            model_name='previsiondemande',
            constraint=models.UniqueConstraint(fields=('company', 'produit', 'segment', 'periode'), name='uniq_scm_prevision_produit_segment_periode'),
        ),
    ]
