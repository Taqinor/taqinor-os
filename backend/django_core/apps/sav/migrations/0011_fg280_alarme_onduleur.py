"""FG280 — Alarmes / défauts onduleur (acquittement / escalade).

Additif + réversible. Nouvelle table `AlarmeOnduleur`, DISTINCTE du ticket SAV :
elle capture un code de défaut onduleur (code / gravité / équipement) avec son
propre cycle de vie d'acquittement et d'escalade (lien optionnel vers un Ticket
SAV). Aucune table existante n'est modifiée — `git revert` la retire proprement.

Index ≤ 30 chars (sav_alarme_co_statut / sav_alarme_co_gravite).
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sav", "0010_fg88_ticket_date_tournee"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AlarmeOnduleur",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="alarmes_onduleur",
                    to="authentication.company")),
                ("equipement", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="alarmes_onduleur", to="sav.equipement")),
                ("code", models.CharField(max_length=60)),
                ("gravite", models.CharField(
                    choices=[
                        ("info", "Information"),
                        ("warning", "Avertissement"),
                        ("critique", "Critique"),
                    ],
                    default="warning", max_length=10)),
                ("libelle", models.CharField(
                    blank=True, default="", max_length=180)),
                ("description", models.TextField(blank=True, default="")),
                ("date_detection", models.DateTimeField(
                    blank=True, null=True)),
                ("statut", models.CharField(
                    choices=[
                        ("active", "Active"),
                        ("acquittee", "Acquittée"),
                        ("resolue", "Résolue"),
                        ("escaladee", "Escaladée"),
                    ],
                    default="active", max_length=12)),
                ("acquittee_par", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="alarmes_onduleur_acquittees",
                    to=settings.AUTH_USER_MODEL)),
                ("date_acquittement", models.DateTimeField(
                    blank=True, null=True)),
                ("ticket", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="alarmes_onduleur", to="sav.ticket")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+", to=settings.AUTH_USER_MODEL)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_modification", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Alarme onduleur",
                "verbose_name_plural": "Alarmes onduleur",
                "ordering": ["-date_creation"],
            },
        ),
        migrations.AddIndex(
            model_name="alarmeonduleur",
            index=models.Index(
                fields=["company", "statut"], name="sav_alarme_co_statut"),
        ),
        migrations.AddIndex(
            model_name="alarmeonduleur",
            index=models.Index(
                fields=["company", "gravite"], name="sav_alarme_co_gravite"),
        ),
    ]
