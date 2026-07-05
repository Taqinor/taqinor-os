from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0072_xfsm13_reverification'),
    ]

    operations = [
        migrations.AddField(
            model_name='reserve',
            name='devis_repare_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
