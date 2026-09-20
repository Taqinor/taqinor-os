"""CAL130 — la section « norme électrique applicable » des réglages société.

Migration ADDITIVE et réversible : un ``JSONField`` avec ``default=dict``.
Aucune donnée existante n'est touchée, et une société qui n'a jamais rien
réglé reçoit ``{}`` — c'est-à-dire « aucune norme choisie », le comportement
d'aujourd'hui exactement (règle D5 : pour ``pays=ma``, aucune norme n'est
supposée, et le calcul concerné est OMIS avec sa mention).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0003_cal64_releve_terrain'),
    ]

    operations = [
        migrations.AddField(
            model_name='parametrescalepinage',
            name='norme_electrique',
            field=models.JSONField(blank=True, default=dict,
                                   verbose_name='Norme électrique applicable'),
        ),
    ]
