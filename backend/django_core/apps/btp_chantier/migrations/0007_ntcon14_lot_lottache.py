"""NTCON14 — planning TCE multi-lots avec jalons contractuels.

Migration ADDITIVE : deux nouvelles tables (``Lot``, ``LotTache``) dans
``btp_chantier`` uniquement. AUCUNE migration n'est ajoutée chez
``gestion_projet``/``installations``/``stock`` — les références croisées
passent par des FK déclarées PAR CHAÎNE depuis cette app (pattern déjà en
place pour ``chantier`` → ``installations.Installation``).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('btp_chantier', '0006_avenantchantier_decomptegeneral_diffusionplan'),
        ('gestion_projet', '0044_aud178_lignesituation_libelle_uniq'),
        ('installations', '0096_odx19_repoint_achats_crossapp'),
        ('stock', '0141_fichetechnique_pdf_filename_fichetechnique_pdf_key_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Lot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('nom', models.CharField(max_length=120, verbose_name='Nom du lot (gros-œuvre, électricité, plomberie…)')),
                ('ordre', models.PositiveIntegerField(default=0, verbose_name='Ordre')),
                ('couleur', models.CharField(blank=True, default='', max_length=7, verbose_name='Couleur du lot (Gantt)')),
                ('interne', models.BooleanField(default=True, verbose_name='Exécuté en interne (régie)')),
                ('date_debut_prevue', models.DateField(blank=True, null=True, verbose_name='Début prévu')),
                ('date_fin_prevue', models.DateField(blank=True, null=True, verbose_name='Fin prévue')),
                ('date_fin_reelle', models.DateField(blank=True, null=True, verbose_name='Fin réelle')),
                ('jalon_contractuel', models.BooleanField(default=False, verbose_name='Jalon contractuel')),
                ('montant_ht', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Montant du lot HT')),
                ('taux_penalite_retard_pmil', models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True, verbose_name='Taux de pénalité de retard (‰/jour)')),
                ('plafond_penalite_pct', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Plafond de pénalité (% du montant du lot)')),
                ('statut', models.CharField(choices=[('planifie', 'Planifié'), ('en_cours', 'En cours'), ('termine', 'Terminé')], default='planifie', max_length=10, verbose_name='Statut')),
                ('chantier', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='btp_lots', to='installations.installation', verbose_name='Chantier')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='btp_lots', to='authentication.company', verbose_name='Société')),
                ('sous_traitant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='btp_lots', to='stock.fournisseur', verbose_name='Entreprise (sous-traitant)')),
            ],
            options={
                'verbose_name': 'Lot de chantier',
                'verbose_name_plural': 'Lots de chantier',
                'ordering': ['ordre', 'id'],
            },
        ),
        migrations.CreateModel(
            name='LotTache',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date_rattachement', models.DateTimeField(auto_now_add=True, verbose_name='Rattachée le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='btp_lot_taches', to='authentication.company', verbose_name='Société')),
                ('lot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rattachements', to='btp_chantier.lot', verbose_name='Lot')),
                ('tache', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='btp_lot_rattachements', to='gestion_projet.tache', verbose_name='Tâche')),
            ],
            options={
                'verbose_name': 'Rattachement tâche ↔ lot',
                'verbose_name_plural': 'Rattachements tâche ↔ lot',
                'ordering': ['lot_id', 'id'],
            },
        ),
        migrations.AddField(
            model_name='lot',
            name='taches',
            field=models.ManyToManyField(blank=True, related_name='btp_lots', through='btp_chantier.LotTache', to='gestion_projet.tache', verbose_name='Tâches rattachées'),
        ),
        migrations.AddIndex(
            model_name='lot',
            index=models.Index(fields=['company', 'chantier', 'statut'], name='btp_lot_co_chan_statut'),
        ),
        migrations.AddIndex(
            model_name='lot',
            index=models.Index(fields=['company', 'jalon_contractuel'], name='btp_lot_co_jalon'),
        ),
        migrations.AddConstraint(
            model_name='lot',
            constraint=models.UniqueConstraint(fields=('chantier', 'nom'), name='btp_lot_chantier_nom_uniq'),
        ),
        migrations.AddConstraint(
            model_name='lottache',
            constraint=models.UniqueConstraint(fields=('tache',), name='btp_lot_tache_unique_lot'),
        ),
    ]
