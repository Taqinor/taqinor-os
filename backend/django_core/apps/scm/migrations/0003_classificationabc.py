# NTSCM4 — ClassificationABC (classement Pareto A/B/C, persisté cote scm — cf. models.py).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0085_ntadm2_produit_entite'),
        ('scm', '0002_evenementdemande'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClassificationABC',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('classe', models.CharField(choices=[('A', 'A'), ('B', 'B'), ('C', 'C')], max_length=1, verbose_name='Classe')),
                ('valeur_cumulee_ht', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Valeur de sortie (HT, sur la fenêtre)')),
                ('part_valeur_pct', models.DecimalField(decimal_places=2, default=0, max_digits=6, verbose_name='Part individuelle de la valeur totale (%)')),
                ('rang', models.PositiveIntegerField(default=0, verbose_name='Rang (1 = plus grosse valeur)')),
                ('fenetre_mois', models.PositiveSmallIntegerField(default=12, verbose_name="Fenêtre d'analyse (mois)")),
                ('calcule_le', models.DateTimeField(auto_now=True, verbose_name='Calculé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scm_classifications_abc', to='authentication.company', verbose_name='Société')),
                ('produit', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='scm_classification_abc', to='stock.produit', verbose_name='Produit')),
            ],
            options={
                'verbose_name': 'Classification ABC',
                'verbose_name_plural': 'Classifications ABC',
                'ordering': ['rang'],
            },
        ),
    ]
