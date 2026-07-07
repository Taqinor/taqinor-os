# ZMKT9 - options de mise en page & anti-biais d'enquete (pagination,
# barre de progression, bouton retour, limite de temps, ordre aleatoire).
# Additif : defauts = comportement une-page actuel (aucune limite, ordre
# fixe).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0095_zmkt5_trace_sequence_statut"),
    ]

    operations = [
        migrations.AddField(
            model_name="enquete",
            name="mode_pagination",
            field=models.CharField(
                choices=[
                    ("une_page", "Une page"),
                    ("une_page_par_section", "Une page par section"),
                    ("une_page_par_question", "Une page par question"),
                ],
                default="une_page", max_length=25,
                verbose_name="Mode de pagination"),
        ),
        migrations.AddField(
            model_name="enquete",
            name="barre_progression",
            field=models.CharField(
                choices=[
                    ("aucune", "Aucune"), ("pourcentage", "Pourcentage"),
                    ("nombre", "Nombre"),
                ],
                default="aucune", max_length=12,
                verbose_name="Barre de progression"),
        ),
        migrations.AddField(
            model_name="enquete",
            name="bouton_retour",
            field=models.BooleanField(
                default=False, verbose_name="Bouton retour"),
        ),
        migrations.AddField(
            model_name="enquete",
            name="limite_temps_minutes",
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name="Limite de temps (minutes)"),
        ),
        migrations.AddField(
            model_name="enquete",
            name="ordre_aleatoire",
            field=models.BooleanField(
                default=False, verbose_name="Ordre aléatoire des questions"),
        ),
    ]
