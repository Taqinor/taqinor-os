# CIQ622 (Groupe CIQ, D-CIQ-12 / D-CIQ-14) — réglages société C&I de recette,
# de suivi et de garantie de production, TOUS SANS DÉFAUT (NULL / False / '').
# Additive et réversible (RemoveField sans perte : colonnes neuves).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0118_ciq614_seuils_8221_surcharge'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='recette_ecart_pmax_pct',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='recette_echantillon_iv_pct',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='recette_pr_seuil_interne',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='delai_intervention_suivi_heures',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='delai_reception_definitive_mois',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='securite_obligatoire_avant_demarrage',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='garantie_production_autorisee',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='garantie_production_validation',
            field=models.TextField(blank=True, default=''),
        ),
    ]
