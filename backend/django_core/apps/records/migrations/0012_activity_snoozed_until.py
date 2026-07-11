# VX85(a) — additif : snooze non destructif (n'écrit jamais due_date).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('records', '0011_activity_body_activity_field_activity_field_label_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='activity',
            name='snoozed_until',
            field=models.DateField(blank=True, null=True, verbose_name="Reportée (snooze) jusqu'au"),
        ),
    ]
