# NTRET10 — Paliers de fidélité (Bronze/Argent/Or) + CompteFidelite.palier_actuel.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fidelite', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PalierFidelite',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('libelle', models.CharField(max_length=60)),
                (
                    'ordre',
                    models.PositiveSmallIntegerField(
                        help_text=(
                            'Rang croissant (1 = le plus bas). Détermine le '
                            'palier retenu (le plus haut `ordre` atteint '
                            'gagne).')),
                ),
                ('seuil_points', models.PositiveIntegerField(blank=True, null=True)),
                (
                    'seuil_ca_cumule',
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=12, null=True,
                        help_text=(
                            "Seuil de chiffre d'affaires TTC cumulé sur "
                            "l'année civile.")),
                ),
                (
                    'remise_pct',
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=5, null=True,
                        help_text=(
                            'Remise automatique (%) appliquée à la caisse '
                            'pour ce palier.')),
                ),
                (
                    'points_bonus_pct',
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=5, null=True,
                        help_text=(
                            'Bonus (%) de points supplémentaires accordé à '
                            'ce palier.')),
                ),
                (
                    'programme',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='paliers', to='fidelite.programmefidelite'),
                ),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='%(app_label)s_%(class)s_set',
                        to='authentication.company', verbose_name='Société'),
                ),
            ],
            options={
                'verbose_name': 'Palier de fidélité',
                'verbose_name_plural': 'Paliers de fidélité',
                'ordering': ['programme', 'ordre'],
            },
        ),
        migrations.AddField(
            model_name='comptefidelite',
            name='palier_actuel',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='comptes', to='fidelite.palierfidelite'),
        ),
        migrations.AddConstraint(
            model_name='palierfidelite',
            constraint=models.UniqueConstraint(
                fields=('programme', 'ordre'),
                name='uniq_palierfidelite_programme_ordre'),
        ),
        migrations.AddConstraint(
            model_name='palierfidelite',
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(('seuil_points__isnull', False))
                    | models.Q(('seuil_ca_cumule__isnull', False))),
                name='chk_palierfidelite_seuil_requis'),
        ),
    ]
