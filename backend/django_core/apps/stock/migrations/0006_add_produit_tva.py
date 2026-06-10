from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0005_add_produit_is_archived'),
    ]

    operations = [
        migrations.AddField(
            model_name='produit',
            name='tva',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
    ]
