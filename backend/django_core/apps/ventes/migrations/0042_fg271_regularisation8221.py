"""FG271 — Regularisation8221 : workflow Article 33 (installations existantes).

Additive only : crée la table de suivi des régularisations 82-21 (Art. 33) +
référence du PDF de déclaration généré. Lien chantier/devis en FK (SET_NULL).
Entièrement revertable.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('installations', '0001_initial'),
        ('ventes', '0041_fg270_subvention_dossier'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Regularisation8221',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('regime_8221', models.CharField(
                    choices=[
                        ('non_concerne', 'Non concerné (hors loi 82-21)'),
                        ('declaration_bt', 'Déclaration basse tension'),
                        ('accord_raccordement', 'Accord de raccordement'),
                        ('autorisation_anre', 'Autorisation ANRE')],
                    default='declaration_bt', max_length=24,
                    verbose_name='Régime visé')),
                ('statut', models.CharField(
                    choices=[('a_regulariser', 'À régulariser'),
                             ('declaration_generee', 'Déclaration générée'),
                             ('deposee', 'Déposée'),
                             ('regularisee', 'Régularisée'),
                             ('refusee', 'Refusée')],
                    default='a_regulariser', max_length=20,
                    verbose_name='Statut')),
                ('puissance_kwc', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=10, null=True,
                    verbose_name='Puissance (kWc)')),
                ('date_mise_en_service_initiale', models.DateField(
                    blank=True, null=True,
                    verbose_name='Date de mise en service initiale')),
                ('declaration_pdf', models.CharField(
                    blank=True, max_length=500, null=True,
                    verbose_name='Déclaration générée (chemin/clé)')),
                ('notes', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='regularisations_8221',
                    to='authentication.company', verbose_name='Société')),
                ('devis', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='regularisations_8221',
                    to='ventes.devis', verbose_name='Devis')),
                ('chantier', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='regularisations_8221_ventes',
                    to='installations.installation',
                    verbose_name='Chantier')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='regularisations_8221_crees',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Régularisation 82-21 (Art. 33)',
                'verbose_name_plural': 'Régularisations 82-21 (Art. 33)',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='regularisation8221',
            index=models.Index(fields=['company', 'statut'],
                               name='ix_reg33_comp_statut'),
        ),
    ]
