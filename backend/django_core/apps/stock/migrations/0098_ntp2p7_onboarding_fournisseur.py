"""NTP2P7 — onboarding fournisseur avec documents légaux.

Additif pur : deux tables neuves (``DossierOnboardingFournisseur`` /
``DocumentFournisseur``) et un interrupteur
``AchatsParametres.onboarding_fournisseur_obligatoire`` à ``False``.
``Fournisseur.statut`` n'est PAS touché : sans activation du flag, la création
d'un bon de commande reste strictement inchangée.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0027_ntadm22_customuser_is_taqinor_support'),
        ('stock', '0097_ntp2p4_budget_departement'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='achatsparametres',
            name='onboarding_fournisseur_obligatoire',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='DossierOnboardingFournisseur',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('statut', models.CharField(choices=[('en_attente', 'En attente'), ('documents_recus', 'Documents reçus'), ('valide', 'Validé'), ('rejete', 'Rejeté')], default='en_attente', max_length=20)),
                ('motif_rejet', models.TextField(blank=True, default='')),
                ('date_decision', models.DateTimeField(blank=True, null=True)),
                ('note', models.TextField(blank=True, default='')),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('fournisseur', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='dossier_onboarding', to='stock.fournisseur', verbose_name='Fournisseur')),
                ('valide_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='dossiers_onboarding_valides', to=settings.AUTH_USER_MODEL, verbose_name='Validé par')),
            ],
            options={
                'verbose_name': 'Dossier onboarding fournisseur',
                'verbose_name_plural': 'Dossiers onboarding fournisseur',
                'ordering': ['-date_creation', '-id'],
            },
        ),
        migrations.CreateModel(
            name='DocumentFournisseur',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('type_document', models.CharField(choices=[('rc', 'Registre du commerce'), ('attestation_fiscale', 'Attestation fiscale'), ('attestation_cnss', 'Attestation CNSS'), ('rib_certifie', 'RIB certifié'), ('assurance', 'Assurance'), ('autre', 'Autre pièce')], default='autre', max_length=25, verbose_name='Type de pièce')),
                ('file_key', models.CharField(blank=True, default='', max_length=500, verbose_name='Clé de stockage')),
                ('filename', models.CharField(blank=True, default='', max_length=255)),
                ('mime', models.CharField(blank=True, default='', max_length=100)),
                ('taille', models.PositiveIntegerField(default=0)),
                ('reference', models.CharField(blank=True, default='', max_length=120)),
                ('date_emission', models.DateField(blank=True, null=True)),
                ('date_expiration', models.DateField(blank=True, null=True)),
                ('note', models.TextField(blank=True, default='')),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('televerse_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='documents_fournisseur_televerses', to=settings.AUTH_USER_MODEL)),
                ('dossier', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='stock.dossieronboardingfournisseur', verbose_name='Dossier')),
            ],
            options={
                'verbose_name': 'Document fournisseur',
                'verbose_name_plural': 'Documents fournisseur',
                'ordering': ['type_document', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='dossieronboardingfournisseur',
            index=models.Index(fields=['company', 'statut'], name='idx_onbfou_co_statut'),
        ),
        migrations.AddIndex(
            model_name='documentfournisseur',
            index=models.Index(fields=['company', 'type_document'], name='idx_docfou_co_type'),
        ),
        migrations.AddIndex(
            model_name='documentfournisseur',
            index=models.Index(fields=['dossier', 'type_document'], name='idx_docfou_dos_type'),
        ),
    ]
