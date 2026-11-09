"""AAPV85 (D-AAPV-5 = recommander) — BCF dont l'annulation a rouvert la
demande d'achat. ADDITIF : une colonne nullable.
Réversible : ``migrate installations 0134``."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0134_equipe_departement'),
        ('achats', '0010_aapv20_ligne_retour_lot_series'),
    ]

    operations = [
        migrations.AddField(
            model_name='demandeachat',
            name='bcf_annule',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='+', to='achats.boncommandefournisseur'),
        ),
    ]
