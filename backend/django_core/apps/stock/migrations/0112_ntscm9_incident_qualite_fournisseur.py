# NTSCM9 — incidents qualité fournisseur.
# Additive : une nouvelle table, aucune colonne touchée sur l'existant.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('achats', '0003_protect_fournisseur_prix'),
        ('authentication', '0028_company_tours_actifs'),
        ('stock', '0111_ntwms40_reappro_casier'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='IncidentQualiteFournisseur',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('type_incident', models.CharField(choices=[('non_conforme', 'Non conforme'), ('endommage', 'Endommagé'), ('erreur_reference', 'Erreur de référence'), ('documentation_manquante', 'Documentation manquante'), ('autre', 'Autre')], default='non_conforme', max_length=30)),
                ('gravite', models.CharField(choices=[('mineure', 'Mineure'), ('majeure', 'Majeure'), ('critique', 'Critique')], default='mineure', max_length=20)),
                ('quantite_affectee', models.PositiveIntegerField(default=0)),
                ('description', models.TextField(blank=True, default='')),
                ('date_incident', models.DateField()),
                ('resolu', models.BooleanField(default=False)),
                ('date_resolution', models.DateField(blank=True, null=True)),
                ('cout_impact_mad', models.DecimalField(blank=True, decimal_places=2, help_text="Coût constaté de l'incident (MAD). INTERNE — alimente le TCO fournisseur (NTSCM26), jamais un document client.", max_digits=12, null=True)),
                ('bon_commande_fournisseur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='incidents_qualite_stock', to='achats.boncommandefournisseur')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('declare_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='incidents_qualite_declares', to=settings.AUTH_USER_MODEL)),
                ('fournisseur', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='incidents_qualite', to='stock.fournisseur')),
                ('produit', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='incidents_qualite_fournisseur', to='stock.produit')),
                ('retour', models.ForeignKey(blank=True, help_text='Retour fournisseur déclenché par cet incident, si créé.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='incidents_qualite_stock', to='achats.retourfournisseur')),
            ],
            options={
                'verbose_name': 'Incident qualité fournisseur',
                'verbose_name_plural': 'Incidents qualité fournisseur',
                'ordering': ['-date_incident', '-id'],
                'indexes': [models.Index(fields=['company', 'fournisseur'], name='idx_incqual_co_fourn'), models.Index(fields=['company', 'resolu'], name='idx_incqual_co_resolu')],
            },
        ),
    ]
