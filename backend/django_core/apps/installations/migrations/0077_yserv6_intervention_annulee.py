from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0076_yproc6_rfq_bcf_link'),
    ]

    operations = [
        migrations.AddField(
            model_name='intervention',
            name='annulee',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='intervention',
            name='motif_annulation',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
