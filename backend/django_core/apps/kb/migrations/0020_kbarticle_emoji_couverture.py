# ZGED10 — Image de couverture + emoji/icône sur l'article KB. Entièrement
# additif : ``emoji``/``couverture_file_key`` défaut '' (comportement
# historique inchangé, aucune icône/couverture sur les articles existants).
# Réversible par ``git revert`` / ``migrate kb 0019``.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kb', '0019_kbparcours'),
    ]

    operations = [
        migrations.AddField(
            model_name='kbarticle',
            name='emoji',
            field=models.CharField(
                blank=True, default='', max_length=8, verbose_name='Emoji'),
        ),
        migrations.AddField(
            model_name='kbarticle',
            name='couverture_file_key',
            field=models.CharField(
                blank=True, default='', max_length=500,
                verbose_name='Couverture'),
        ),
    ]
