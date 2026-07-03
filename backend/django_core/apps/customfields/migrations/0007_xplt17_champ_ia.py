# XPLT17 — champ type=ia (valeur générée par LLM, à la demande, NO-OP-safe).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customfields", "0006_xplt16_custom_objects"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customfielddef",
            name="type",
            field=models.CharField(
                choices=[
                    ("text", "Texte"),
                    ("number", "Nombre"),
                    ("date", "Date"),
                    ("choice", "Choix"),
                    ("boolean", "Oui/Non"),
                    ("relation", "Relation"),
                    ("fichier", "Fichier"),
                    ("ia", "Champ IA"),
                ],
                default="text",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="customfielddef",
            name="ia_prompt",
            field=models.TextField(blank=True, default=""),
        ),
    ]
