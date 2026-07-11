# VX98 — puce de fraîcheur : horodatage (updated_at, auto_now) + dernier auteur
# d'une modification (updated_by) sur Devis et Facture. Migration ADDITIVE :
# updated_at nullable (auto_now, NULL sur les documents antérieurs jusqu'au
# prochain save), updated_by FK nullable posé server-side dans perform_update
# (jamais accepté du corps de requête).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0081_qx30_engagement_triggers'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='devis',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.AddField(
            model_name='devis',
            name='updated_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='devis_modifies',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='facture',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.AddField(
            model_name='facture',
            name='updated_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='factures_modifiees',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
