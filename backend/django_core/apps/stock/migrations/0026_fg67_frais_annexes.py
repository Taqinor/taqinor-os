from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0025_fg66_kit_bom"),
    ]

    operations = [
        migrations.AddField(
            model_name="ligneboncommandefournisseur",
            name="frais_annexes",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=12,
                help_text="Frais annexes TOTAUX de la ligne (fret/douane/TVA "
                          "import/transit), répartis sur les unités. INTERNE."),
        ),
    ]
