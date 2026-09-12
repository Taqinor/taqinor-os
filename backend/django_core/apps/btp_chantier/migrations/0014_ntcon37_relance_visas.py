"""NTCON37 — idempotence du sweep de relance des visas en attente de revue.

Migration ADDITIVE : une colonne nullable sur ``VisaDocument``. ``NULL`` =
jamais relancé — donc le premier passage du balayage relance normalement et le
comportement au déploiement est inchangé.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('btp_chantier', '0013_ntcon28_penalite_cache'),
    ]

    operations = [
        migrations.AddField(
            model_name='visadocument',
            name='derniere_relance_retard',
            field=models.DateField(
                blank=True, null=True,
                verbose_name='Dernière relance de revue'),
        ),
    ]
