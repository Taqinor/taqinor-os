# Generated for N74 — checklists configurables en modèles nommés.

import django.db.models.deletion
from django.db import migrations, models


# N74 — pour chaque société ayant déjà des étapes de checklist « orphelines »
# (template=NULL, amorcées avant N74), on crée le modèle « Défaut » (protégé,
# type vide) et on rattache ces étapes existantes — la checklist d'un chantier
# reste donc identique (comportement préservé, additif, non destructif).
def attach_orphans_to_default_template(apps, schema_editor):
    ChecklistTemplate = apps.get_model("installations", "ChecklistTemplate")
    ChecklistEtapeModele = apps.get_model(
        "installations", "ChecklistEtapeModele")
    company_ids = (
        ChecklistEtapeModele.objects.filter(template__isnull=True)
        .values_list("company_id", flat=True)
        .distinct()
    )
    for company_id in company_ids:
        if company_id is None:
            # Étapes sans société (cas marginal) — laissées telles quelles ;
            # l'amorçage paresseux ne les concerne pas.
            continue
        template, _ = ChecklistTemplate.objects.get_or_create(
            company_id=company_id, type_installation=None,
            defaults={"nom": "Défaut", "ordre": 0,
                      "protege": True, "actif": True})
        ChecklistEtapeModele.objects.filter(
            company_id=company_id, template__isnull=True
        ).update(template=template)


def noop_reverse(apps, schema_editor):
    # Réversible sans perte : la suppression du champ/modèle (par
    # RemoveField/DeleteModel) suffit ; aucune donnée d'étape n'est supprimée.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("installations", "0005_installation_art33_regularisation_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChecklistTemplate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("nom", models.CharField(max_length=120)),
                (
                    "type_installation",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("residentiel", "Résidentiel"),
                            ("industriel", "Industriel / Commercial"),
                            ("agricole", "Agricole (pompage)"),
                        ],
                        max_length=20,
                        null=True,
                    ),
                ),
                ("ordre", models.PositiveIntegerField(default=0)),
                ("actif", models.BooleanField(default=True)),
                ("protege", models.BooleanField(default=False)),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="checklist_templates",
                        to="authentication.company",
                    ),
                ),
            ],
            options={
                "verbose_name": "Modèle de checklist chantier",
                "verbose_name_plural": "Modèles de checklist chantier",
                "ordering": ["ordre", "nom"],
            },
        ),
        migrations.AddField(
            model_name="checklistetapemodele",
            name="template",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="etapes",
                to="installations.checklisttemplate",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="checklistetapemodele",
            unique_together={("company", "template", "cle")},
        ),
        migrations.RunPython(
            attach_orphans_to_default_template, noop_reverse),
    ]
