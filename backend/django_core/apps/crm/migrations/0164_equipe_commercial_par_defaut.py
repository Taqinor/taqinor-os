# Fondateur 13/11/2026 — commercial par défaut d'une équipe, choisi par son
# responsable (``apps/crm/dispatch.py::repli``). Additif, réversible.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('crm', '0163_ntplt33_client_fts_null'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipecommerciale',
            name='commercial_par_defaut',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to=settings.AUTH_USER_MODEL,
                verbose_name='Commercial par défaut'),
        ),
    ]
