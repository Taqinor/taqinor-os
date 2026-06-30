"""FG274 — CommissioningTest : fiche de recette IEC 62446.

Additive only : crée la table des essais de mise en service (isolement/polarité/
continuité terre/contrôle onduleur + résultat global) rattachée au chantier et au
devis (FK SET_NULL). Entièrement revertable.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('installations', '0001_initial'),
        ('ventes', '0042_fg271_regularisation8221'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CommissioningTest',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('date_essai', models.DateField(
                    blank=True, null=True, verbose_name='Date des essais')),
                ('isolement_mohm', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=8, null=True,
                    verbose_name="Résistance d'isolement (MΩ)")),
                ('isolement_ok', models.BooleanField(
                    blank=True, null=True,
                    verbose_name='Isolement conforme')),
                ('polarite_ok', models.BooleanField(
                    blank=True, null=True,
                    verbose_name='Polarité correcte')),
                ('continuite_terre_ohm', models.DecimalField(
                    blank=True, decimal_places=3, max_digits=8, null=True,
                    verbose_name='Continuité terre (Ω)')),
                ('continuite_terre_ok', models.BooleanField(
                    blank=True, null=True,
                    verbose_name='Continuité terre conforme')),
                ('controle_onduleur_ok', models.BooleanField(
                    blank=True, null=True,
                    verbose_name='Contrôle onduleur conforme')),
                ('resultat', models.CharField(
                    choices=[('en_cours', 'En cours'),
                             ('conforme', 'Conforme'),
                             ('non_conforme', 'Non conforme'),
                             ('reserves', 'Conforme avec réserves')],
                    default='en_cours', max_length=14,
                    verbose_name='Résultat global')),
                ('technicien', models.CharField(
                    blank=True, max_length=120, null=True,
                    verbose_name='Technicien')),
                ('observations', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='commissioning_tests',
                    to='authentication.company', verbose_name='Société')),
                ('chantier', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='commissioning_tests',
                    to='installations.installation',
                    verbose_name='Chantier')),
                ('devis', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='commissioning_tests',
                    to='ventes.devis', verbose_name='Devis')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='commissioning_tests_crees',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Fiche de recette (IEC 62446)',
                'verbose_name_plural': 'Fiches de recette (IEC 62446)',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='commissioningtest',
            index=models.Index(fields=['company', 'resultat'],
                               name='ix_comm_comp_resultat'),
        ),
    ]
