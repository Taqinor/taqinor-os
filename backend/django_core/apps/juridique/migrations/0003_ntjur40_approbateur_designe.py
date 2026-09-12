"""NTJUR40 — approbateur DÉSIGNÉ (optionnel) sur une étape d'approbation.

ADDITIF et nullable : les étapes existantes restent ouvertes à tout porteur de
la permission ``juridique_approuver_engagement``. Être désigné ne donne aucun
droit par soi-même — la permission de rôle reste exigée (défense en
profondeur).
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('juridique', '0002_ntjur19_approbation_engagement'),
    ]

    operations = [
        migrations.AddField(
            model_name='etapeapprobationjuridique',
            name='approbateur_designe',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='juridique_etapes_designees',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Approbateur désigné'),
        ),
    ]
