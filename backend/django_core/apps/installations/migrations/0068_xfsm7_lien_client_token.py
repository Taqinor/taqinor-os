from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0067_xmfg16_assemblage_soustraite'),
    ]

    operations = [
        migrations.AddField(
            model_name='intervention',
            name='lien_client_token',
            field=models.CharField(
                blank=True, editable=False, max_length=64, null=True,
                unique=True,
                help_text="Jeton public du lien « technicien en route » (XFSM7)."),
        ),
        migrations.AddField(
            model_name='intervention',
            name='depart_gps_lat',
            field=models.DecimalField(
                blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='intervention',
            name='depart_gps_lng',
            field=models.DecimalField(
                blank=True, decimal_places=6, max_digits=9, null=True),
        ),
    ]
