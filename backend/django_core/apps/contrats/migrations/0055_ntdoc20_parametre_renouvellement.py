"""NTDOC20 — Delai de prevenance d'echeance PAR type de contrat.

Purement ADDITIF (creation de table) et revertable : aucune donnee existante
n'est touchee, aucun champ existant n'est modifie. La table part VIDE, et un
type de contrat sans ligne garde exactement le delai historique de
``semer_alertes_echeances`` — aucune societe ne voit son comportement changer
tant qu'elle n'a rien configure.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('contrats', '0054_ntdoc7_etape_assigne_a'),
    ]

    operations = [
        migrations.CreateModel(
            name='ParametreRenouvellement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('type_contrat', models.CharField(choices=[('vente', 'Vente'), ('om', 'O&M'), ('monitoring', 'Monitoring'), ('garantie', 'Garantie'), ('ppa', 'PPA'), ('fournisseur', 'Fournisseur'), ('sous_traitance', 'Sous-traitance'), ('location', 'Location'), ('emploi', 'Emploi'), ('nda', 'NDA'), ('maintenance', 'Maintenance'), ('autre', 'Autre')], max_length=20, verbose_name='Type de contrat')),
                ('delai_avant_echeance_jours', models.PositiveIntegerField(default=30, help_text="Nombre de jours avant l'échéance à partir duquel une alerte est semée pour les contrats de ce type.", verbose_name='Délai de prévenance avant échéance (jours)')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Délai de renouvellement par type',
                'verbose_name_plural': 'Délais de renouvellement par type',
                'ordering': ['company_id', 'type_contrat'],
            },
        ),
        migrations.AddConstraint(
            model_name='parametrerenouvellement',
            constraint=models.UniqueConstraint(fields=('company', 'type_contrat'), name='contrats_paramrenouv_uniq'),
        ),
    ]
