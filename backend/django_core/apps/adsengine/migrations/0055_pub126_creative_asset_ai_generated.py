"""PUB126 — Étiquette « généré par IA » par asset (``CreativeAsset.ai_generated``).

Meta exige la divulgation du contenu généré par IA ; aucun champ ne la portait.
Le flag est posé PAR LA LANE de fabrique (``creative_factory.
lane_is_ai_generated``) et la check-list policy bloque un asset issu d'une lane
IA qui n'aurait pas son étiquette.

Purement ADDITIVE (un BooleanField ``default=False``) : les lignes existantes
(uploads manuels, photos de chantier, témoignages) restent NON étiquetées — ce
qui est la vérité, et le contraire aurait été un sur-étiquetage mensonger.
Entièrement revertable.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0054_pub122_creative_asset_meta_media'),
    ]

    operations = [
        migrations.AddField(
            model_name='creativeasset',
            name='ai_generated',
            field=models.BooleanField(
                default=False,
                help_text="Vrai si tout ou partie de l'asset est généré par IA "
                          "(divulgation exigée par Meta).",
                verbose_name='Généré par IA'),
        ),
    ]
