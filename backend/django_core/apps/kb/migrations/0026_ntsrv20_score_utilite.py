# NTSRV20 — Score d'utilité d'article KCS (deux compteurs additifs, défaut 0
# = comportement historique inchangé pour tout article existant).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("kb", "0025_ntsrv19_kbarticlelien_type_cible_ticket"),
    ]

    operations = [
        migrations.AddField(
            model_name="kbarticle",
            name="nb_vues_depuis_ticket",
            field=models.PositiveIntegerField(
                default=0, verbose_name="Vues depuis un ticket"),
        ),
        migrations.AddField(
            model_name="kbarticle",
            name="nb_resolutions_attribuees",
            field=models.PositiveIntegerField(
                default=0, verbose_name="Résolutions attribuées"),
        ),
    ]
