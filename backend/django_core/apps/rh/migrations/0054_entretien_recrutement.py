# XRH17 — Entretiens de recrutement (planification + grille d'évaluation).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("rh", "0053_grille_salariale"),
    ]

    operations = [
        migrations.CreateModel(
            name="EntretienRecrutement",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("date_heure", models.DateTimeField(blank=True, null=True)),
                ("type", models.CharField(
                    choices=[
                        ("telephonique", "Téléphonique"),
                        ("technique", "Technique"),
                        ("rh", "RH"), ("final", "Final")],
                    default="rh", max_length=15)),
                ("statut", models.CharField(
                    choices=[
                        ("planifie", "Planifié"), ("realise", "Réalisé"),
                        ("annule", "Annulé")],
                    default="planifie", max_length=10)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("candidature", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="entretiens", to="rh.candidature")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_entretiens_recrutement",
                    to="authentication.company")),
                ("evaluateurs", models.ManyToManyField(
                    blank=True, related_name="rh_entretiens_a_evaluer",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Entretien de recrutement",
                "verbose_name_plural": "Entretiens de recrutement",
                "ordering": ["-date_heure", "-date_creation"],
            },
        ),
        migrations.AddIndex(
            model_name="entretienrecrutement",
            index=models.Index(
                fields=["company", "candidature"],
                name="rh_entretien_comp_cand_idx"),
        ),
        migrations.CreateModel(
            name="NoteEntretien",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("notes_criteres", models.JSONField(blank=True, default=dict)),
                ("commentaire", models.TextField(blank=True, default="")),
                ("avis", models.CharField(
                    choices=[
                        ("favorable", "Favorable"),
                        ("reserve", "Réservé"),
                        ("defavorable", "Défavorable")],
                    default="reserve", max_length=15)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_notes_entretien",
                    to="authentication.company")),
                ("entretien", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="notes", to="rh.entretienrecrutement")),
                ("evaluateur", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_notes_entretien",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Note d'entretien",
                "verbose_name_plural": "Notes d'entretien",
                "ordering": ["-date_creation"],
            },
        ),
        migrations.AddConstraint(
            model_name="noteentretien",
            constraint=models.UniqueConstraint(
                fields=("entretien", "evaluateur"),
                name="rh_note_entretien_uniq"),
        ),
    ]
