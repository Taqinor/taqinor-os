from django.db import migrations, models

# AGR603 — loi 82-21 art. 3 : une installation non raccordée relève d'une
# déclaration. Ajout du code ``declaration_hors_reseau`` aux choix (AlterField
# de choix pur : aucune colonne, aucun backfill ; réversible).
_CHOICES = [
    ('non_concerne', 'Non concerné (hors loi 82-21)'),
    ('declaration_bt', 'Déclaration basse tension'),
    ('accord_raccordement', 'Accord de raccordement'),
    ('autorisation_anre', 'Autorisation ANRE'),
    ('declaration_hors_reseau', 'Déclaration hors réseau (loi 82-21, art. 3)'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0122_agr217_tva_base_legale'),
    ]

    operations = [
        migrations.AlterField(
            model_name='regulatorydossier',
            name='regime_8221',
            field=models.CharField(
                choices=_CHOICES, default='non_concerne', max_length=24,
                verbose_name='Régime loi 82-21'),
        ),
        migrations.AlterField(
            model_name='regularisation8221',
            name='regime_8221',
            field=models.CharField(
                choices=_CHOICES, default='declaration_bt', max_length=24,
                verbose_name='Régime visé'),
        ),
    ]
