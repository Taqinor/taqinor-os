# XKB11 — Liens internes article↔article : ajoute ``article`` aux
# ``TypeCible`` valides de ``KbArticleLien`` (cible = un autre KbArticle,
# même société). Ne change QUE la liste des choix affichés/validés (colonne
# déjà ``CharField(max_length=20)``, ``article`` y tient) — aucune donnée
# existante n'est touchée. Entièrement additive, réversible par
# ``git revert`` / ``migrate kb 0010``.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("kb", "0010_kbarticle_corps_format"),
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
                ],
                max_length=20,
                verbose_name="Type de cible",
            ),
        ),
    ]
