from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0071_alter_equipement_installation_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipement',
            name='garantie_plancher',
            field=models.DateField(blank=True, null=True),
        ),
    ]
