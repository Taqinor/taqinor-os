# XCTR4 — Routage de couverture (garantie / contrat O&M / facturable).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0036_xctr3_contratmaintenance_entitlements'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='couverture',
            field=models.CharField(
                choices=[
                    ('garantie', 'Garantie'),
                    ('contrat', 'Contrat O&M'),
                    ('facturable', 'Facturable'),
                    ('a_determiner', 'À déterminer'),
                ],
                default='a_determiner', max_length=12,
                help_text='Qui couvre cette intervention : garantie, contrat '
                          'de maintenance, ou facturable au client.',
                verbose_name='Couverture'),
        ),
    ]
