# FG372 — E-signature (Yousign/DocuSign…) : suivi de demande de signature.
#
# Ajoute ``EsignRequest`` : suit une demande de signature électronique pour
# n'importe quel document métier, désigné via ``contenttypes`` (fondation
# Django) — AUCUN import d'app métier (contrat import-linter
# ``core-foundation-is-a-base-layer``). Migration ADDITIVE et réversible.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('core', '0003_integrationconfig'),
    ]

    operations = [
        migrations.CreateModel(
            name='EsignRequest',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('object_id', models.PositiveIntegerField(
                    blank=True, null=True,
                    verbose_name='Identifiant du document')),
                ('provider', models.CharField(
                    max_length=60, verbose_name='Fournisseur')),
                ('external_id', models.CharField(
                    blank=True, default='',
                    help_text='Identifiant retourné par le fournisseur e-sign.',
                    max_length=128, verbose_name='Référence externe')),
                ('statut', models.CharField(
                    choices=[
                        ('brouillon', 'Brouillon'), ('envoye', 'Envoyé'),
                        ('signe', 'Signé'), ('refuse', 'Refusé'),
                        ('expire', 'Expiré'), ('erreur', 'Erreur')],
                    default='brouillon', max_length=16, verbose_name='Statut')),
                ('signataire_email', models.EmailField(
                    blank=True, default='', max_length=254,
                    verbose_name='Email signataire')),
                ('signataire_nom', models.CharField(
                    blank=True, default='', max_length=160,
                    verbose_name='Nom signataire')),
                ('signed_url', models.URLField(
                    blank=True, default='',
                    verbose_name='URL document signé')),
                ('sent_le', models.DateTimeField(
                    blank=True, null=True, verbose_name='Envoyé le')),
                ('signed_le', models.DateTimeField(
                    blank=True, null=True, verbose_name='Signé le')),
                ('detail', models.JSONField(
                    blank=True, default=dict, verbose_name='Détail')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='esign_requests',
                    to='authentication.company', verbose_name='Société')),
                ('content_type', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='+', to='contenttypes.contenttype',
                    verbose_name='Type de document')),
            ],
            options={
                'verbose_name': 'Demande de signature électronique',
                'verbose_name_plural': 'Demandes de signature électronique',
                'ordering': ['-id'],
            },
        ),
        migrations.AddIndex(
            model_name='esignrequest',
            index=models.Index(
                fields=['company', 'statut'],
                name='core_esign_co_statut_idx'),
        ),
        migrations.AddIndex(
            model_name='esignrequest',
            index=models.Index(
                fields=['provider', 'external_id'],
                name='core_esign_ext_idx'),
        ),
    ]
