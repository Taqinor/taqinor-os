import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0058_xstk17_profil_saisonnier'),
        ('installations', '0075_yproc5_da_bcf_link'),
    ]

    operations = [
        migrations.AddField(
            model_name='rfq',
            name='bon_commande',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='installations_rfqs',
                to='stock.boncommandefournisseur'),
        ),
    ]
