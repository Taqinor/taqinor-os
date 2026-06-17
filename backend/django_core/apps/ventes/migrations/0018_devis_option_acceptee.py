# A1 — option retenue à l'acceptation du devis (« Sans batterie » /
# « Avec batterie »). Additif : colonne optionnelle, vide par défaut, donc le
# comportement existant est inchangé tant qu'aucune acceptation n'est faite.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0017_devis_acceptance_devisactivity"),
    ]

    operations = [
        migrations.AddField(
            model_name="devis",
            name="option_acceptee",
            field=models.CharField(
                blank=True,
                choices=[
                    ("sans_batterie", "Sans batterie"),
                    ("avec_batterie", "Avec batterie"),
                ],
                default="",
                max_length=20,
            ),
        ),
    ]
