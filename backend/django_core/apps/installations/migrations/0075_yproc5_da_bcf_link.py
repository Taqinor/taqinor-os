import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0058_xstk17_profil_saisonnier'),
        ('installations', '0074_xfsm21_meteo_risque'),
    ]

    operations = [
        migrations.AddField(
            model_name='demandeachat',
            name='bon_commande',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='installations_demandes_achat',
                to='stock.boncommandefournisseur'),
        ),
    ]
