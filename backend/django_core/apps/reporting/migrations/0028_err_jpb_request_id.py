from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0027_yjpb1_probleme_client'),
    ]

    operations = [
        migrations.AddField(
            model_name='problemeclient',
            name='request_id',
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
    ]
