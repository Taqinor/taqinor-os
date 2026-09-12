# VTA6 — deux jalons de progression terrain, horodatés SERVEUR :
# ``en_route_le`` (le commercial part) et ``arrivee_le`` (il est sur place).
#
# Migration purement ADDITIVE et sûre : deux colonnes NULL sans défaut, donc
# aucune réécriture de table et aucun verrou long sur ``crm_visiteterrain``
# (une visite déjà enregistrée reste simplement « sans jalon franchi », ce qui
# est la vérité — jamais une valeur inventée qui ferait croire à un passage).
# Réversible sans perte de données historiques autre que les deux colonnes.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('visites', '0002_vta2_rename_stale_contenttypes'),
    ]

    operations = [
        migrations.AddField(
            model_name='visiteterrain',
            name='en_route_le',
            field=models.DateTimeField(blank=True, null=True,
                                       verbose_name='Départ vers le site'),
        ),
        migrations.AddField(
            model_name='visiteterrain',
            name='arrivee_le',
            field=models.DateTimeField(blank=True, null=True,
                                       verbose_name='Arrivée sur le site'),
        ),
    ]
