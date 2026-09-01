# QJR-OFFGRID (fondateur 01/09/2026) — choix ADDITIF « aucun » (« Non raccordé
# (site isolé) ») sur le raccordement. Aucune donnée ne bouge : les valeurs
# 'monophase' / 'triphase' / 'inconnu' existantes restent intactes, et
# `max_length=12` couvre déjà la nouvelle valeur (5 caractères).
#
# Les DEUX champs qui partagent la taxonomie `Lead.Raccordement` sont alignés
# dans la même migration — `SiteProfile.raccordement` la RÉUTILISE (jamais une
# seconde liste de choix), donc les laisser diverger ferait rouge la garde de
# dérive modèle↔migration.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0084_relanceetape"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lead",
            name="raccordement",
            field=models.CharField(
                blank=True,
                choices=[
                    ("monophase", "Monophasé"),
                    ("triphase", "Triphasé"),
                    ("inconnu", "Je ne sais pas"),
                    ("aucun", "Non raccordé (site isolé)"),
                ],
                max_length=12,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="siteprofile",
            name="raccordement",
            field=models.CharField(
                blank=True,
                choices=[
                    ("monophase", "Monophasé"),
                    ("triphase", "Triphasé"),
                    ("inconnu", "Je ne sais pas"),
                    ("aucun", "Non raccordé (site isolé)"),
                ],
                max_length=12,
                null=True,
            ),
        ),
    ]
