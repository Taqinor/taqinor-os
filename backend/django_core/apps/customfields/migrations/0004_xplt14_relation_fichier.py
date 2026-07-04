# XPLT14 — types RELATION/FICHIER + modules fournisseur/employé (additif).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customfields", "0003_alter_customfielddef_module"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customfielddef",
            name="module",
            field=models.CharField(
                choices=[
                    ("lead", "Lead"),
                    ("client", "Client"),
                    ("produit", "Produit"),
                    ("devis", "Devis"),
                    ("installation", "Chantier"),
                    ("ticket", "Ticket SAV"),
                    ("document", "Document GED"),
                    ("fournisseur", "Fournisseur"),
                    ("employe", "Employé"),
                ],
                max_length=20,
            ),
        ),
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
                ],
                default="text",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="customfielddef",
            name="relation_module",
            field=models.CharField(
                blank=True,
                choices=[
                    ("lead", "Lead"),
                    ("client", "Client"),
                    ("produit", "Produit"),
                    ("devis", "Devis"),
                    ("installation", "Chantier"),
                    ("ticket", "Ticket SAV"),
                    ("document", "Document GED"),
                    ("fournisseur", "Fournisseur"),
                    ("employe", "Employé"),
                ],
                max_length=20,
                null=True,
            ),
        ),
    ]
