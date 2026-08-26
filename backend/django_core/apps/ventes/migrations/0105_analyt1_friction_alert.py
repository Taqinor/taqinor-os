"""ANALYT1 (audit item 64, 26/08/2026) — alerte de FRICTION par relecture de
section.

Deux champs additifs/nullables sur ``ShareLink`` : ``friction_alert_logged_at``
(horodatage de la note chatter posée UNE SEULE fois par lien, même idiome que
``deep_engagement_logged_at``) et ``friction_alert_section`` (quelle section a
déclenché l'alerte). Aucun backfill — tout lien existant garde ``NULL`` sur les
deux champs et se comporte exactement comme avant.

``ShareLink.engagement`` (JSONField déjà existant, XSAL16) accueille en plus,
PAR SECTION, ``visits``/``visit_ids`` — additif à l'intérieur du même champ
JSON, donc aucune migration de schéma n'est nécessaire pour cette partie.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0104_tailles_offres_config'),
    ]

    operations = [
        migrations.AddField(
            model_name='sharelink',
            name='friction_alert_logged_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='sharelink',
            name='friction_alert_section',
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
    ]
