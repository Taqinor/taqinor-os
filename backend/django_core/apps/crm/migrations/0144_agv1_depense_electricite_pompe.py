"""AGV1 — facture d'électricité du pompage déclarée (pompe actuelle sur le
réseau, D-AGR-5) + AGV8 sa part fixe. Colonnes nullables, aucun défaut : additive et revertable."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0143_equipecommerciale_departement'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='depense_electricite_pompe_mad_mois',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
                verbose_name='Facture électricité du pompage (MAD/mois)',
                help_text="Question à l'appel : « Si votre pompe actuelle "
                          "marche à l'électricité, combien payez-vous par "
                          'mois pour le pompage ? » (MAD/mois, facultatif, '
                          "vide = pas encore posée)."),
        ),
        migrations.AddField(
            model_name='lead',
            name='depense_electricite_pompe_part_fixe_mad_mois',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
                verbose_name='Part fixe de la facture électricité du pompage '
                             '(MAD/mois)',
                help_text="Question à l'appel : « Sur cette facture, combien "
                          'est fixe chaque mois (abonnement, redevance), même '
                          'sans pomper ? » (MAD/mois, facultatif, vide = pas '
                          'encore posée).'),
        ),
    ]
