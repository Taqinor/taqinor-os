from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0011_fg280_alarme_onduleur'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='devis_id_ext',
            field=models.IntegerField(
                blank=True, null=True,
                help_text='ID du Devis ventes créé depuis ce ticket (XSAV3).'),
        ),
    ]
