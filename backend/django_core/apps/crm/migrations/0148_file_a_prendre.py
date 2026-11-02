from django.db import migrations, models


class Migration(migrations.Migration):
    """CADV31 — file « À prendre » : interrupteur par équipe (additif, faux par défaut)."""

    dependencies = [
        ('crm', '0147_enf15_code_parrainage_par_societe'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipecommerciale',
            name='file_a_prendre',
            field=models.BooleanField(
                default=False,
                verbose_name='File « À prendre » (tout membre prend un lead)'),
        ),
    ]
