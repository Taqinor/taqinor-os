from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0018_xsav10_ticketsatisfaction'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='reopen_count',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
