"""NTWMS9 — expédition multi-transporteurs (étiquette réelle GATED).

NOUVEAU modèle purement additif. Le paramétrage et la CLÉ d'API de chaque
transporteur réel vivent dans la primitive plateforme
``core.models.IntegrationConfig`` (``secret_ref`` = nom de variable
d'environnement) : aucun secret n'est stocké ici, et sans intégration
configurée le connecteur NoOp produit une étiquette interne sans appel réseau.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('installations', '0034_binlocation_binaffectation_and_more'),
        ('stock', '0091_ntwms8_code_checkin'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExpeditionTransporteur',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('transporteur_provider', models.CharField(
                    choices=[('aucun', 'Aucun (étiquette interne)'),
                             ('amana', 'Amana'), ('dhl', 'DHL'),
                             ('chronopost', 'Chronopost'),
                             ('autre', 'Autre')],
                    default='aucun', max_length=20)),
                ('numero_suivi', models.CharField(
                    blank=True, default='', max_length=120)),
                ('cout_reel', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True)),
                ('etiquette_pdf_key', models.CharField(
                    blank=True, default='', max_length=500)),
                ('statut', models.CharField(
                    choices=[('brouillon', 'Brouillon'),
                             ('etiquette', 'Étiquette générée'),
                             ('expedie', 'Expédié'), ('livre', 'Livré'),
                             ('annule', 'Annulé')],
                    default='brouillon', max_length=20)),
                ('destination', models.CharField(
                    blank=True, default='', max_length=200)),
                ('date_expedition', models.DateTimeField(
                    blank=True, null=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('transporteur', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='expeditions_stock',
                    to='installations.transporteur')),
                ('unite_logistique', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='expeditions', to='stock.unitelogistique')),
            ],
            options={
                'verbose_name': 'Expédition transporteur',
                'verbose_name_plural': 'Expéditions transporteur',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='expeditiontransporteur',
            index=models.Index(fields=['company', 'statut'],
                               name='idx_expedtr_co_statut'),
        ),
        migrations.AddIndex(
            model_name='expeditiontransporteur',
            index=models.Index(fields=['company', 'numero_suivi'],
                               name='idx_expedtr_co_suivi'),
        ),
    ]
