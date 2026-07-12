# XPLT20 — Écritures inter-sociétés miroir (vente A → achat B). Nouvelle
# règle opt-in par paire de sociétés (désactivée par défaut) + trace
# lettrable/idempotence des miroirs générés. Migration standard (nouvelles
# tables, aucune donnée existante affectée).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0020_company_benchmarking_opt_in'),
        ('compta', '0109_odx13_partenaires_split'),
    ]

    operations = [
        migrations.CreateModel(
            name='RegleInterSociete',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('actif', models.BooleanField(default=False, verbose_name='Actif')),
                ('compte_liaison', models.CharField(blank=True, default='', max_length=20, verbose_name='Compte de liaison (CGNC)')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créée le')),
                ('societe_a', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='regles_intersociete_source', to='authentication.company', verbose_name='Société A (vendeuse)')),
                ('societe_b', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='regles_intersociete_cible', to='authentication.company', verbose_name='Société B (acheteuse)')),
            ],
            options={
                'verbose_name': 'Règle inter-sociétés',
                'verbose_name_plural': 'Règles inter-sociétés',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.CreateModel(
            name='EcritureLiaisonInterSociete',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('facture_source_id', models.PositiveIntegerField(verbose_name='Id de la facture (société A)')),
                ('facture_fournisseur_miroir_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Id de la facture fournisseur miroir (société B)')),
                ('montant_ht', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Montant HT')),
                ('montant_tva', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Montant TVA')),
                ('montant_ttc', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Montant TTC')),
                ('compte_liaison', models.CharField(blank=True, default='', max_length=20, verbose_name='Compte de liaison (CGNC)')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créée le')),
                ('regle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ecritures_liaison', to='compta.regleintersociete', verbose_name='Règle')),
            ],
            options={
                'verbose_name': 'Écriture de liaison inter-sociétés',
                'verbose_name_plural': 'Écritures de liaison inter-sociétés',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.AddConstraint(
            model_name='regleintersociete',
            constraint=models.UniqueConstraint(fields=('societe_a', 'societe_b'), name='uniq_regle_intersociete_paire'),
        ),
        migrations.AddConstraint(
            model_name='ecritureliaisonintersociete',
            constraint=models.UniqueConstraint(fields=('regle', 'facture_source_id'), name='uniq_ecriture_liaison_regle_facture'),
        ),
    ]
