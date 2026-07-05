# XMKT9 - tracker de liens + auto-tag UTM : LienTrackee (redirection
# tokenisee company-scoped) + ClicLien (clic par destinataire). Additif,
# nouvelles tables.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0079_xmkt7_campagne_planification_throttling"),
    ]

    operations = [
        migrations.CreateModel(
            name="LienTrackee",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("token", models.CharField(
                    max_length=64, unique=True, verbose_name="Jeton public")),
                ("url_cible", models.URLField(
                    max_length=1000, verbose_name="URL cible")),
                ("nb_clics", models.PositiveIntegerField(
                    default=0, verbose_name="Clics")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("campagne", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="liens_trackes", to="compta.campagne",
                    verbose_name="Campagne")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="liens_trackes", to="authentication.company",
                    verbose_name="Société")),
            ],
            options={
                "verbose_name": "Lien tracké",
                "verbose_name_plural": "Liens trackés",
                "ordering": ["-date_creation"],
            },
        ),
        migrations.CreateModel(
            name="ClicLien",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("destinataire", models.CharField(
                    blank=True, default="", max_length=255,
                    verbose_name="Destinataire (email/téléphone, si connu)")),
                ("clique_le", models.DateTimeField(
                    auto_now_add=True, verbose_name="Cliqué le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="clics_lien", to="authentication.company",
                    verbose_name="Société")),
                ("lien", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="clics", to="compta.lientrackee",
                    verbose_name="Lien tracké")),
            ],
            options={
                "verbose_name": "Clic de lien",
                "verbose_name_plural": "Clics de lien",
                "ordering": ["-clique_le"],
            },
        ),
    ]
