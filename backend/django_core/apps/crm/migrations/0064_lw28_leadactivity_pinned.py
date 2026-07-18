# LW28 — note épinglée du chatter lead. Un seul champ additif, défaut False
# → comportement historique strictement inchangé. Purement additive et
# révertable (AddField / RemoveField automatique).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0063_forecastentry_plancompte_playbook_playbooketape_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='leadactivity',
            name='pinned',
            field=models.BooleanField(default=False, verbose_name='Épinglée'),
        ),
    ]
