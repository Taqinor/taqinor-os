# QW2 — Lead columns for site-sent fields with nowhere to land (all
# additive + nullable, reversible via the automatic AddField reverse).
# raisonSociale REUSES the existing `societe` column — no migration needed
# for it.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0041_zsal3_equipe_commerciale"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="facility_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("bureau", "Bureau"),
                    ("entrepot", "Entrepôt"),
                    ("usine", "Usine"),
                    ("commerce", "Commerce"),
                    ("agricole", "Agricole"),
                    ("autre", "Autre"),
                ],
                max_length=12,
                null=True,
                verbose_name="Type de site (pro)",
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="site_count",
            field=models.CharField(
                blank=True,
                choices=[
                    ("1", "1 site"),
                    ("2-5", "2 à 5 sites"),
                    ("6+", "6 sites ou plus"),
                ],
                max_length=4,
                null=True,
                verbose_name="Nombre de sites (pro)",
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="visit_window_part",
            field=models.CharField(
                blank=True,
                choices=[("matin", "Matin"), ("apres_midi", "Après-midi")],
                max_length=12,
                null=True,
                verbose_name="Créneau de visite préféré",
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="visit_window_week",
            field=models.CharField(
                blank=True,
                choices=[
                    ("cette_semaine", "Cette semaine"),
                    ("semaine_prochaine", "Semaine prochaine"),
                ],
                max_length=20,
                null=True,
                verbose_name="Semaine de visite préférée",
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="client_ref",
            field=models.CharField(
                blank=True,
                max_length=24,
                null=True,
                verbose_name="Référence client (générée navigateur)",
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="phone_is_foreign",
            field=models.BooleanField(
                blank=True,
                null=True,
                verbose_name="Numéro étranger (diaspora/MRE)",
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="page",
            field=models.CharField(
                blank=True,
                max_length=300,
                null=True,
                verbose_name="Page de landing (first-touch)",
            ),
        ),
    ]
