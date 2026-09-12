# NTSRV19 — ajoute "ticket" aux TypeCible valides de KbArticleLien (cible =
# le ticket SAV d'où provient un article créé via "Créer un article KB"
# depuis un ticket résolu). Ne change QUE la liste des choix affichés/
# validés (colonne déjà CharField(max_length=20), "ticket" y tient) —
# aucune donnée existante n'est touchée. Entièrement additive, réversible
# par `git revert` / `migrate kb 0024`. Même patron que 0011 (XKB11).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("kb", "0024_ntmig21_playbook"),
    ]

    operations = [
        migrations.AlterField(
            model_name="kbarticlelien",
            name="type_cible",
            field=models.CharField(
                choices=[
                    ("produit", "Produit"),
                    ("equipement", "Équipement"),
                    ("type_intervention", "Type d'intervention"),
                    ("article", "Article"),
                    ("ticket", "Ticket"),
                ],
                max_length=20,
                verbose_name="Type de cible",
            ),
        ),
    ]
