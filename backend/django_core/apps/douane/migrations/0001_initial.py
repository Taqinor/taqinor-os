# NTLOG14 — DossierExport / PieceDossierExport.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0027_ntadm22_customuser_is_taqinor_support'),
        ('ventes', '0092_ntadm2_devis_entite'),
        ('facturation', '0003_ntadm2_facture_entite'),
        ('records', '0013_vx210_snooze_trigger_event'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DossierExport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('numero', models.CharField(blank=True, db_index=True, default='', max_length=30)),
                ('incoterm', models.CharField(blank=True, choices=[('exw', "EXW — À l'usine"), ('fob', 'FOB — Franco à bord'), ('cfr', 'CFR — Coût et fret'), ('cif', 'CIF — Coût, assurance, fret'), ('dap', 'DAP — Rendu au lieu'), ('ddp', 'DDP — Rendu droits acquittés')], default='', max_length=3)),
                ('port_embarquement', models.CharField(blank=True, default='', max_length=120)),
                ('port_debarquement', models.CharField(blank=True, default='', max_length=120)),
                ('pays_destinataire', models.CharField(blank=True, default='', max_length=100)),
                ('statut', models.CharField(choices=[('a_preparer', 'À préparer'), ('dum_deposee', 'DUM déposée'), ('en_dedouanement', 'En dédouanement'), ('leve', 'Levé'), ('cloture', 'Clôturé')], default='a_preparer', max_length=20)),
                ('devise', models.CharField(blank=True, default='', max_length=3)),
                ('valeur_marchandise_devise', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('note', models.TextField(blank=True, default='')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='dossiers_export_crees', to=settings.AUTH_USER_MODEL)),
                ('devis', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='dossiers_export', to='ventes.devis', verbose_name='Devis lié')),
                ('facture', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='dossiers_export', to='facturation.facture', verbose_name='Facture liée')),
            ],
            options={
                'verbose_name': "Dossier d'export",
                'verbose_name_plural': "Dossiers d'export",
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PieceDossierExport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('type_piece', models.CharField(choices=[('facture_export', 'Facture export'), ('packing_list', 'Packing list'), ('certificat_origine', "Certificat d'origine"), ('dum_export', 'DUM export'), ('eur1', 'EUR.1')], max_length=24)),
                ('statut_piece', models.CharField(choices=[('manquante', 'Manquante'), ('deposee', 'Déposée'), ('validee', 'Validée')], default='manquante', max_length=10)),
                ('date_depot', models.DateField(blank=True, null=True)),
                ('attachment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pieces_dossier_export', to='records.attachment')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('dossier', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pieces', to='douane.dossierexport')),
            ],
            options={
                'verbose_name': "Pièce de dossier d'export",
                'verbose_name_plural': "Pièces de dossier d'export",
                'ordering': ['type_piece'],
            },
        ),
        migrations.AddIndex(
            model_name='dossierexport',
            index=models.Index(fields=['company', 'statut'], name='idx_exp_co_statut'),
        ),
        migrations.AlterUniqueTogether(
            name='dossierexport',
            unique_together={('company', 'numero')},
        ),
        migrations.AlterUniqueTogether(
            name='piecedossierexport',
            unique_together={('dossier', 'type_piece')},
        ),
    ]
