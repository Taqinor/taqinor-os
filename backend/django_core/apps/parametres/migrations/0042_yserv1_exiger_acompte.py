# YSERV1 — Gate « acompte encaissé » avant planification (opt-in, défaut OFF
# = comportement historique byte-identique).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0041_xfsm1_taux_horaire_sav"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="exiger_acompte_avant_planification",
            field=models.BooleanField(
                default=False,
                help_text="Bloque la planification d'un chantier (statut "
                          "PLANIFIE) tant que l'acompte du devis lié n'est "
                          "pas encaissé. Désactivé par défaut."),
        ),
    ]
