# GED21 — Filigrane & contrôle de diffusion.
#
# Ajoute deux drapeaux booléens de CONTRÔLE DE DIFFUSION, additifs et
# réversibles :
#   - `Document.watermark_diffusion` : quand vrai, le document est filigrané
#     (« CONFIDENTIEL ») à chaque diffusion — aperçu authentifié (GED14) ET
#     téléchargement public (GED20).
#   - `PartageGed.watermark` : force le filigrane sur un lien public précis,
#     même si le document n'est pas globalement marqué.
#
# Tous deux par défaut FAUX : aucun document/partage existant ne change de
# comportement (le flux reste byte-identique à l'original). Le filigrane est un
# RENDU à la volée (`services.apply_watermark`) — il ne touche jamais le binaire
# stocké en base/MinIO ni aucun statut documentaire. Aucune dépendance dure
# n'est requise : le filigrane PDF/image charge sa lib paresseusement et
# dégrade proprement (renvoie l'original) si la lib est absente.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ged", "0014_partageged"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="watermark_diffusion",
            field=models.BooleanField(
                default=False,
                verbose_name="filigraner à la diffusion",
            ),
        ),
        migrations.AddField(
            model_name="partageged",
            name="watermark",
            field=models.BooleanField(
                default=False,
                verbose_name="filigraner le partage",
            ),
        ),
    ]
