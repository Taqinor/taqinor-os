# ZSAL1 — enchaînement d'activités : champs additifs sur ActivityType
# (type_suivant self-FK nullable, mode_enchainement, delai_jours), tous par
# défaut inertes (mode='aucun', type_suivant=None) donc aucun changement de
# comportement pour les types existants. Additive et réversible
# (`migrate records 0008`).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("records", "0008_activity_personnelle"),
    ]

    operations = [
        migrations.AddField(
            model_name="activitytype",
            name="mode_enchainement",
            field=models.CharField(
                choices=[
                    ("aucun", "Aucun"),
                    ("suggerer", "Suggérer"),
                    ("declencher", "Déclencher"),
                ],
                default="aucun", max_length=10,
                verbose_name="Mode d'enchaînement"),
        ),
        migrations.AddField(
            model_name="activitytype",
            name="delai_jours",
            field=models.PositiveIntegerField(
                default=0, verbose_name="Délai (jours) avant la suite"),
        ),
        migrations.AddField(
            model_name="activitytype",
            name="type_suivant",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="types_precedents", to="records.activitytype",
                verbose_name="Type suivant suggéré/déclenché"),
        ),
    ]
