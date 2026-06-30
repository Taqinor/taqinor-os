# GED28 — Génération de document → classement automatique (hors /proposal).
#
# Ajoute à `ModeleDocument` la RÈGLE de classement du document généré :
#   - `cabinet_cible` : nom du cabinet de destination (défaut « Documents ») ;
#   - `dossier_cible` : nom du dossier racine de destination, pouvant porter des
#     jetons `{{ champ }}` résolus depuis le contexte de fusion (ex.
#     « Attestations {{ annee }} ») — routage par année/client.
# `services.generer_document` (via `resoudre_classement`) dépose désormais le PDF
# généré dans ce cabinet/dossier (auto-créé si absent) au lieu d'un dossier par
# défaut ; vide = comportement rétro-compatible. Couche de documents INTERNES,
# SÉPARÉE du chemin `/proposal` (rule #4). Migration strictement additive ;
# aucune donnée existante touchée.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ged", "0020_modeledocument"),
    ]

    operations = [
        migrations.AddField(
            model_name="modeledocument",
            name="cabinet_cible",
            field=models.CharField(
                blank=True, default="Documents", max_length=120,
                verbose_name="cabinet de classement",
            ),
        ),
        migrations.AddField(
            model_name="modeledocument",
            name="dossier_cible",
            field=models.CharField(
                blank=True, default="", max_length=200,
                verbose_name="dossier de classement (avec {{ champs }})",
            ),
        ),
    ]
