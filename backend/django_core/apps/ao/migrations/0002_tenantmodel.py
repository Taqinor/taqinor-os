# AOF4 — les 8 modèles legacy AO passent au socle ``core.models.TenantModel``.
#
# La migration est PUREMENT ADDITIVE : deux horodatages (``created_at`` /
# ``updated_at``) par table, avec un défaut one-off pour les lignes existantes.
# Elle ne contient AUCUN ``AlterModelTable`` — les ``db_table = 'compta_*'``
# posées state-only par ODX11 restent strictement inchangées (un renommage de
# table serait irréversible en production). La FK ``company`` est REDÉCLARÉE
# à l'identique dans le corps de chaque modèle pour conserver son
# ``related_name`` historique : l'état ne bouge donc pas pour elle non plus, et
# aucune opération n'est générée.

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ao', '0001_odx11_ao_split'),
    ]

    operations = [
        migrations.AddField(
            model_name='appeloffre',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='appeloffre',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='bordereauprix',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='bordereauprix',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='cautionsoumission',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='cautionsoumission',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='dossiersoumission',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='dossiersoumission',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='echeanceao',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='echeanceao',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='lignebordereau',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='lignebordereau',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='piecesoumission',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='piecesoumission',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='resultatao',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='resultatao',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
