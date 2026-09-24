"""CALX406 — le RESPONSABLE d'un calepinage.

ADDITIVE : ``responsable`` naît à ``NULL`` pour tout l'existant — aucun
calepinage n'est confié d'office à personne, aucune ligne n'est réécrite. La
vue restreinte au responsable est un RÉGLAGE société (section ``presets``,
JSON existant) : absente, la liste de chacun reste exactement celle
d'aujourd'hui (D12). ``PROTECT`` et non ``SET_NULL`` (garde YDATA3
``check_on_delete``) : un compte qui porte des calepinages se désactive, il
ne vide jamais ce champ en silence.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0015_calx364_provenance_releve_photo'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='calepinage',
            name='responsable',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='calepinages_responsable',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Responsable'),
        ),
    ]
