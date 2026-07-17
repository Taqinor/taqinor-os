"""NTAPI24 — additif uniquement : nouveau champ `ChangelogEntry.breaking`
(défaut False, n'affecte aucune note existante). Alimente le fil dédié
`changelog API` (`apps.publicapi`, `GET /api/public/changelog/`), qui
réutilise/étend FG399 au lieu d'un modèle dupliqué."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0039_ntapi7_apiusageplan_named_quotas'),
    ]

    operations = [
        migrations.AddField(
            model_name='changelogentry',
            name='breaking',
            field=models.BooleanField(
                default=False,
                help_text='Coché pour une note du fil « changelog API » qui '
                          "casse une intégration existante (NTAPI24).",
                verbose_name='Changement cassant (API)',
            ),
        ),
    ]
