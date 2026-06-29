# Generated for FG302 — Calendrier de disponibilité des ressources terrain.
# Additif : on AJOUTE une seule table (IndisponibiliteRessource). Aucune colonne
# d'une table existante n'est modifiée. Aucune migration destructive.
#
# IndisponibiliteRessource référence stock.EmplacementStock (la camionnette) par
# string-FK : le modèle stock n'est jamais importé côté Python ; la dépendance de
# migration sur `stock` suffit. Le technicien est l'utilisateur (swappable).
# Noms d'index ≤ 30 caractères (contrainte Django/Postgres).

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('installations', '0018_fg294_budget_projet'),
        ('stock', '0023_fg54_fg61_fg62_fg63_fg64_stock_features'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='IndisponibiliteRessource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type_indispo', models.CharField(choices=[('conge', 'Congé'), ('formation', 'Formation'), ('arret', 'Arrêt (maladie / panne)'), ('autre', 'Autre')], default='conge', max_length=10)),
                ('date_debut', models.DateField()),
                ('date_fin', models.DateField()),
                ('motif', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_indispos', to='authentication.company')),
                ('technicien', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_indispos', to=settings.AUTH_USER_MODEL)),
                ('camionnette', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_indispos', to='stock.emplacementstock')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_indispos_crees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Indisponibilité de ressource',
                'verbose_name_plural': 'Indisponibilités de ressource',
                'ordering': ['-date_debut', '-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='indisponibiliteressource',
            index=models.Index(fields=['company', 'technicien'], name='idx_indispo_co_tech'),
        ),
        migrations.AddIndex(
            model_name='indisponibiliteressource',
            index=models.Index(fields=['company', 'camionnette'], name='idx_indispo_co_camion'),
        ),
        migrations.AddIndex(
            model_name='indisponibiliteressource',
            index=models.Index(fields=['company', 'date_debut', 'date_fin'], name='idx_indispo_co_dates'),
        ),
    ]
