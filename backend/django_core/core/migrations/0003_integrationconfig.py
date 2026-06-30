# FG371+ — Configuration générique des intégrations externes (fondation).
#
# Ajoute le modèle ``IntegrationConfig`` : paramétrage multi-tenant d'un
# connecteur externe (SMS, e-signature, IMAP, calendrier, géocodage,
# Sage/CEGID, Odoo, open banking…) désigné de façon GÉNÉRIQUE par deux chaînes
# (integration_type + provider) — AUCUN import d'app métier (contrat
# import-linter ``core-foundation-is-a-base-layer``). Le secret réel est
# référencé par nom de variable d'environnement (``secret_ref``), jamais stocké
# en clair. Migration purement ADDITIVE et réversible.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('core', '0002_workflow'),
    ]

    operations = [
        migrations.CreateModel(
            name='IntegrationConfig',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('integration_type', models.CharField(
                    help_text='Catégorie, ex. « sms », « esign », « geocoding ».',
                    max_length=40, verbose_name="Type d'intégration")),
                ('provider', models.CharField(
                    help_text='Code du connecteur enregistré, ex. « infobip ».',
                    max_length=60, verbose_name='Fournisseur')),
                ('label', models.CharField(
                    blank=True, default='', max_length=120,
                    verbose_name='Libellé')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('settings', models.JSONField(
                    blank=True, default=dict,
                    help_text='Paramètres NON sensibles (JSON). Jamais de '
                              'secret en clair.',
                    verbose_name='Paramètres')),
                ('secret_ref', models.CharField(
                    blank=True, default='',
                    help_text="Nom de variable d'environnement contenant le "
                              "secret.",
                    max_length=120, verbose_name='Référence du secret')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='integration_configs',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': "Configuration d'intégration",
                'verbose_name_plural': "Configurations d'intégration",
                'ordering': ['integration_type', 'provider', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='integrationconfig',
            constraint=models.UniqueConstraint(
                fields=('company', 'integration_type', 'provider'),
                name='core_integration_co_type_prov'),
        ),
        migrations.AddIndex(
            model_name='integrationconfig',
            index=models.Index(
                fields=['company', 'integration_type'],
                name='core_integ_co_type_idx'),
        ),
        migrations.AddIndex(
            model_name='integrationconfig',
            index=models.Index(
                fields=['company', 'actif'],
                name='core_integ_co_actif_idx'),
        ),
    ]
