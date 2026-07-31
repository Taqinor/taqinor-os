"""NTEXT4 — séquence d'actions : AutomationStep (additif, réversible).

Purement ADDITIF : une nouvelle table. Aucune règle existante ne porte d'étape,
donc le moteur garde son chemin mono-action historique tant qu'aucune étape
n'est créée.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("automation", "0011_yopsb11_automationrunarchive"),
    ]

    operations = [
        migrations.CreateModel(
            name="AutomationStep",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                (
                    "ordre",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Rang d'exécution (croissant, id à "
                                  "égalité)."),
                ),
                (
                    "action_type",
                    models.CharField(
                        choices=[
                            ("send_whatsapp", "Envoyer un WhatsApp"),
                            ("send_email", "Envoyer un email"),
                            ("send_sms", "Envoyer un SMS"),
                            ("create_activity", "Créer une activité / tâche"),
                            ("assign_record", "Assigner un enregistrement"),
                            ("set_field", "Mettre à jour un champ"),
                            ("create_sav_ticket", "Créer un ticket SAV"),
                        ],
                        max_length=40),
                ),
                ("action_config", models.JSONField(blank=True, default=dict)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_modification", models.DateTimeField(auto_now=True)),
                (
                    "rule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="steps",
                        to="automation.automationrule",
                        verbose_name="Règle"),
                ),
            ],
            options={
                "verbose_name": "Étape d'automatisation",
                "verbose_name_plural": "Étapes d'automatisation",
                "ordering": ["ordre", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="automationstep",
            index=models.Index(
                fields=["rule", "ordre"], name="automation_step_rule_idx"),
        ),
    ]
