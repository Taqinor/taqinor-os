# Generated manually — ZRH13 demande d'allocation de congés self-service.
# Additif, nouveau modèle.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """ZRH13 — DemandeAllocation (additif)."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("rh", "0076_zrh14_badges_reconnaissance"),
    ]

    operations = [
        migrations.CreateModel(
            name="DemandeAllocation",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("jours", models.DecimalField(
                    decimal_places=2, max_digits=6,
                    verbose_name="Jours demandés")),
                ("motif", models.CharField(
                    blank=True, default="", max_length=255,
                    verbose_name="Motif")),
                ("statut", models.CharField(
                    choices=[
                        ("soumise", "Soumise"),
                        ("validee", "Validée"),
                        ("refusee", "Refusée"),
                    ],
                    default="soumise", max_length=10,
                    verbose_name="Statut")),
                ("date_decision", models.DateTimeField(
                    blank=True, null=True, verbose_name="Date de décision")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_demandes_allocation",
                    to="authentication.company", verbose_name="Société")),
                ("decide_par", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="rh_allocations_decidees",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Décidé par")),
                ("employe", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="demandes_allocation",
                    to="rh.dossieremploye", verbose_name="Employé")),
                ("type_absence", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="demandes_allocation",
                    to="rh.typeabsence", verbose_name="Type d'absence")),
            ],
            options={
                "verbose_name": "Demande d'allocation de congés",
                "verbose_name_plural": "Demandes d'allocation de congés",
                "ordering": ["-date_creation"],
            },
        ),
        migrations.AddIndex(
            model_name="demandeallocation",
            index=models.Index(
                fields=["company", "employe", "statut"],
                name="rh_demande_alloc_emp_st_idx"),
        ),
    ]
