import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """ZFSM3 — récurrences d'intervention autonomes (sans contrat de
    maintenance). Génère la prochaine Intervention à échéance via
    `manage.py generer_interventions_recurrentes` (pattern FG1/XPRJ13).
    Additive — aucune migration destructive."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('installations', '0086_zfsm2_lien_rapport_token'),
    ]

    operations = [
        migrations.CreateModel(
            name='RecurrenceIntervention',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('type_intervention', models.CharField(max_length=20)),
                ('regle', models.CharField(choices=[
                    ('mensuelle', 'Mensuelle'),
                    ('trimestrielle', 'Trimestrielle'),
                    ('semestrielle', 'Semestrielle'),
                    ('annuelle', 'Annuelle'),
                ], max_length=15)),
                ('intervalle', models.PositiveSmallIntegerField(default=1)),
                ('prochaine_echeance', models.DateField()),
                ('date_fin', models.DateField(blank=True, null=True)),
                ('nb_occurrences', models.PositiveIntegerField(
                    blank=True, null=True)),
                ('nb_generees', models.PositiveIntegerField(default=0)),
                ('actif', models.BooleanField(default=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='recurrences_intervention',
                    to='authentication.company')),
                ('installation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='recurrences_intervention',
                    to='installations.installation')),
                ('technicien_defaut', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='recurrences_intervention_defaut',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': "Récurrence d'intervention",
                'verbose_name_plural': "Récurrences d'intervention",
                'ordering': ['prochaine_echeance', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='recurrenceintervention',
            index=models.Index(
                fields=['actif', 'prochaine_echeance'],
                name='inst_recur_actif_echeance_idx'),
        ),
    ]
