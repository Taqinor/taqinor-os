"""MRY10 — `LeadActivity.Kind.WHATSAPP` : le WhatsApp devient une interaction
typée, au même rang qu'un appel ou un e-mail.

`AlterField(choices)` seul (`max_length=15` suffit pour « whatsapp ») : aucune
donnée touchée. Sans ce type, le canal principal de Meryem se noyait dans les
notes libres — invisible au compteur de tentatives (MRY20) comme au chatter.
"""
from django.db import migrations, models

from apps.crm.models import LeadActivity


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0090_relanceetape_v2'),
    ]

    operations = [
        migrations.AlterField(
            model_name='leadactivity',
            name='kind',
            field=models.CharField(
                choices=LeadActivity.Kind.choices, max_length=15),
        ),
    ]
