"""NTMOB9 — type de franchissement (entrée/sortie) sur ``GeofenceAlert``.

Le check-in/out géofencé se construit sur les modèles GPS EXISTANTS
(consentement ``GpsConsentRecord``, position ``PositionTechnicien``,
franchissement ``GeofenceAlert``) plutôt que sur une deuxième table de
pointage — arbitrage WIR113 (``docs/module-map.md``).

ADDITIF STRICT : défaut ``sortie``, la valeur exacte de tout l'historique
(chaque ligne existante était un dépassement de rayon), donc aucune migration
de données n'est nécessaire et aucune alerte existante ne change de sens.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0106_ntp2p35_demandeachat_archivage'),
    ]

    operations = [
        migrations.AddField(
            model_name='geofencealert',
            name='type_franchissement',
            field=models.CharField(
                choices=[('entree', 'Entrée'), ('sortie', 'Sortie')],
                default='sortie', max_length=10,
                verbose_name='Type de franchissement'),
        ),
    ]
