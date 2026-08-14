# NTSCM3 — EvenementDemande (promotions, chantiers planifiés, ruptures fournisseur connues).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0085_ntadm2_produit_entite'),
        ('scm', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EvenementDemande',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date_debut', models.DateField(verbose_name='Début')),
                ('date_fin', models.DateField(verbose_name='Fin')),
                ('impact_pct', models.DecimalField(decimal_places=2, help_text='Signé : +30 = +30% de demande, -100 = rupture connue (demande nulle).', max_digits=6, verbose_name='Impact (%)')),
                ('libelle', models.CharField(max_length=255, verbose_name='Libellé')),
                ('type_evenement', models.CharField(choices=[('promotion', 'Promotion'), ('chantier_majeur', 'Chantier majeur'), ('rupture_fournisseur', 'Rupture fournisseur'), ('saisonnalite_locale', 'Saisonnalité locale'), ('autre', 'Autre')], default='autre', max_length=20, verbose_name="Type d'événement")),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('categorie', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='scm_evenements_demande', to='stock.categorie', verbose_name='Catégorie')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scm_evenements_demande', to='authentication.company', verbose_name='Société')),
                ('produit', models.ForeignKey(blank=True, help_text='Vide = tous les produits de la catégorie (ou toute la société si catégorie aussi vide).', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='scm_evenements_demande', to='stock.produit', verbose_name='Produit')),
            ],
            options={
                'verbose_name': 'Événement de demande',
                'verbose_name_plural': 'Événements de demande',
                'ordering': ['-date_debut'],
            },
        ),
    ]
