"""ASOC98 — motif du refus SAV d'une demande portail (additif, défaut vide)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portail', '0010_ntprt6_invitation_portail'),
    ]

    operations = [
        migrations.AddField(
            model_name='demandeticketportail',
            name='motif_refus',
            field=models.TextField(
                blank=True, default='', verbose_name='Motif du refus'),
        ),
    ]
