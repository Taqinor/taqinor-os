# AMON7 — date et auteur de la résiliation d'un abonnement de supervision.
# Additive : deux colonnes NULL (NULL = abonnement actif ou résilié avant).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('monitoring', '0013_amon93_certificat_annulation'),
    ]

    operations = [
        migrations.AddField(
            model_name='abonnementmonitoring',
            name='date_resiliation',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='Résilié le'),
        ),
        migrations.AddField(
            model_name='abonnementmonitoring',
            name='resilie_par',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to=settings.AUTH_USER_MODEL,
                verbose_name='Résilié par'),
        ),
    ]
