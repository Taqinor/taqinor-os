"""NTWMS4 — vagues et bons de prélèvement optimisés (wave picking).

Deux NOUVEAUX modèles, purement additifs :
  * ``VaguePicking`` — la tournée multi-source (référence VAG-YYYYMM-NNNN) ;
  * ``LignePicking`` — la ligne à prélever, son casier source (string-FK vers
    la hiérarchie FG319 ``installations.BinLocation``, jamais dupliquée), son
    lot et sa source de demande (chantier / bon de commande).

Aucune table existante n'est touchée.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('achats', '0001_odx19_achats_split'),
        ('authentication', '0001_initial'),
        ('installations', '0034_binlocation_binaffectation_and_more'),
        ('stock', '0086_ntwms3_strategie_picking'),
    ]

    operations = [
        migrations.CreateModel(
            name='VaguePicking',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reference', models.CharField(max_length=50)),
                ('statut', models.CharField(
                    choices=[('brouillon', 'Brouillon'),
                             ('lancee', 'Lancée'),
                             ('terminee', 'Terminée')],
                    default='brouillon', max_length=20)),
                ('note', models.TextField(blank=True, null=True)),
                ('date_lancement', models.DateTimeField(blank=True, null=True)),
                ('date_cloture', models.DateTimeField(blank=True, null=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('cree_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='vagues_picking_creees',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Vague de prélèvement',
                'verbose_name_plural': 'Vagues de prélèvement',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='LignePicking',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('quantite_demandee', models.PositiveIntegerField(default=0)),
                ('quantite_prelevee', models.PositiveIntegerField(default=0)),
                ('ordre_parcours', models.PositiveIntegerField(default=1000)),
                ('bin', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='lignes_picking',
                    to='installations.binlocation')),
                ('bon_commande', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='lignes_picking',
                    to='achats.boncommandefournisseur')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('installation', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='lignes_picking',
                    to='installations.installation')),
                ('lot', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='lignes_picking', to='stock.lotentrepot')),
                ('produit', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='lignes_picking', to='stock.produit')),
                ('vague', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='lignes', to='stock.vaguepicking')),
            ],
            options={
                'verbose_name': 'Ligne de prélèvement',
                'verbose_name_plural': 'Lignes de prélèvement',
                'ordering': ['ordre_parcours', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='vaguepicking',
            index=models.Index(fields=['company', 'statut'],
                               name='idx_vaguepick_co_statut'),
        ),
        migrations.AddConstraint(
            model_name='vaguepicking',
            constraint=models.UniqueConstraint(
                fields=('company', 'reference'),
                name='stock_vaguepicking_company_reference_uniq'),
        ),
        migrations.AddIndex(
            model_name='lignepicking',
            index=models.Index(fields=['company', 'vague'],
                               name='idx_lignepick_co_vague'),
        ),
    ]
