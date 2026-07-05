"""XFAC14 — Compensation AR/AP (netting) pour un tiers à la fois client et
fournisseur.

Additif : deux nouveaux modèles ``Compensation`` (en-tête) et
``LigneCompensation`` (factures AR/AP imputées) — aucun champ existant
touché.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0014_customuser_account_lockout'),
        ('compta', '0073_campagne_sms_sender_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='Compensation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference', models.CharField(blank=True, default='', max_length=50, verbose_name='Référence')),
                ('client_id', models.PositiveIntegerField(verbose_name='Client (id crm)')),
                ('client_nom', models.CharField(blank=True, default='', max_length=200, verbose_name='Client')),
                ('fournisseur_id', models.PositiveIntegerField(verbose_name='Fournisseur (id stock)')),
                ('fournisseur_nom', models.CharField(blank=True, default='', max_length=200, verbose_name='Fournisseur')),
                ('montant_compense', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Montant compensé')),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('validee', 'Validée')], default='brouillon', max_length=12, verbose_name='Statut')),
                ('ecriture_id', models.PositiveIntegerField(blank=True, null=True, verbose_name="ID de l'écriture GL")),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créée le')),
                ('date_validation', models.DateTimeField(blank=True, null=True, verbose_name='Validée le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='compensations', to='authentication.company', verbose_name='Société')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='compensations_creees', to=settings.AUTH_USER_MODEL, verbose_name='Créée par')),
            ],
            options={
                'verbose_name': 'Compensation AR/AP',
                'verbose_name_plural': 'Compensations AR/AP',
                'ordering': ['-date_creation', '-id'],
            },
        ),
        migrations.CreateModel(
            name='LigneCompensation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type_facture', models.CharField(choices=[('ar', 'Facture client (AR)'), ('ap', 'Facture fournisseur (AP)')], max_length=2)),
                ('facture_id', models.PositiveIntegerField(verbose_name='Facture (id ventes ou stock selon type)')),
                ('reference_facture', models.CharField(blank=True, default='', max_length=50, verbose_name='Référence')),
                ('montant_impute', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Montant imputé')),
                ('compensation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='compta.compensation')),
            ],
            options={
                'verbose_name': 'Ligne de compensation',
                'verbose_name_plural': 'Lignes de compensation',
                'ordering': ['id'],
            },
        ),
    ]
