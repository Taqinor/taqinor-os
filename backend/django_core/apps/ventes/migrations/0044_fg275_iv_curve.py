"""FG275 — IVCurveCapture : mesure I-V par string vs datasheet.

Additive only : crée la table des captures I-V (valeurs mesurées vs attendues +
écart Pmax + drapeau défaut) rattachée à une fiche de recette (FG274).
Entièrement revertable.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('ventes', '0043_fg274_commissioning_test'),
    ]

    operations = [
        migrations.CreateModel(
            name='IVCurveCapture',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('string_label', models.CharField(
                    max_length=60, verbose_name='Chaîne (string)')),
                ('n_modules_serie', models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    verbose_name='Modules en série')),
                ('voc_mesure_v', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=8, null=True,
                    verbose_name='Voc mesurée (V)')),
                ('isc_mesure_a', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=8, null=True,
                    verbose_name='Isc mesurée (A)')),
                ('vmp_mesure_v', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=8, null=True,
                    verbose_name='Vmp mesurée (V)')),
                ('imp_mesure_a', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=8, null=True,
                    verbose_name='Imp mesurée (A)')),
                ('pmax_mesure_w', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=10, null=True,
                    verbose_name='Pmax mesurée (W)')),
                ('voc_attendu_v', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=8, null=True,
                    verbose_name='Voc attendue (V)')),
                ('isc_attendu_a', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=8, null=True,
                    verbose_name='Isc attendue (A)')),
                ('pmax_attendu_w', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=10, null=True,
                    verbose_name='Pmax attendue (W)')),
                ('ecart_pmax_pct', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=6, null=True,
                    verbose_name='Écart Pmax (%)')),
                ('defaut_detecte', models.BooleanField(
                    default=False, verbose_name='Défaut détecté')),
                ('observations', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='iv_curve_captures',
                    to='authentication.company', verbose_name='Société')),
                ('recette', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='iv_curves',
                    to='ventes.commissioningtest',
                    verbose_name='Fiche de recette')),
            ],
            options={
                'verbose_name': 'Capture I-V (string)',
                'verbose_name_plural': 'Captures I-V (string)',
                'ordering': ['recette', 'string_label'],
            },
        ),
        migrations.AddIndex(
            model_name='ivcurvecapture',
            index=models.Index(fields=['company', 'recette'],
                               name='ix_ivc_comp_recette'),
        ),
    ]
