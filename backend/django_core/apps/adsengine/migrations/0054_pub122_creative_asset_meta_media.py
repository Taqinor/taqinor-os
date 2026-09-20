"""PUB122 — Identifiants du média UPLOADÉ AU COMPTE sur ``CreativeAsset``.

``file_key`` est une clé MinIO que Meta ne sait pas lire : un créatif
publicitaire ne référence QUE des identifiants de COMPTE (``image_hash`` /
``video_id``). Ces deux colonnes les portent et rendent le service d'upload
idempotent (déjà renseigné ⇒ aucun ré-upload).

Purement ADDITIVE (deux CharField vides par défaut, aucune contrainte, aucun
index) : les lignes existantes restent intactes avec une valeur vide — ce qui
est la vérité (aucun asset n'avait encore été uploadé au compte). Entièrement
revertable.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0053_metaleadmirror_origine'),
    ]

    operations = [
        migrations.AddField(
            model_name='creativeasset',
            name='meta_image_hash',
            field=models.CharField(
                blank=True, default='', max_length=128,
                verbose_name='Hash image Meta (compte)'),
        ),
        migrations.AddField(
            model_name='creativeasset',
            name='meta_video_id',
            field=models.CharField(
                blank=True, default='', max_length=64,
                verbose_name='ID vidéo Meta (compte)'),
        ),
    ]
