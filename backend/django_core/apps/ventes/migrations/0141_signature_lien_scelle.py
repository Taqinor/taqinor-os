# ADEV104 (C-L3-LIEN-10) — le sceau v3 couvre ce que CE lien a montré : le
# niveau du lien et ses sections masquées sont stockés sur la signature
# (``lien_scelle``) et entrent dans l'empreinte. Additif (nullable),
# réversible : NULL = acceptation sans lien ou antérieure (sceau inchangé).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0140_signature_figures_scellees'),
    ]

    operations = [
        migrations.AddField(
            model_name='devissignature',
            name='lien_scelle',
            field=models.JSONField(
                blank=True, null=True,
                verbose_name='Niveau et sections du lien scellés à la signature'),
        ),
    ]
