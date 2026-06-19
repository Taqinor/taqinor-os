# L636 — unicité du n° de série par société (additif). Contrainte conditionnelle :
# les séries vides/NULL sont permises et exclues de l'unicité. Si des lignes
# existantes entraient en collision au déploiement, la contrainte DB peut être
# omise — le serializer impose l'unicité dans tous les cas (message FR clair).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sav", "0005_contrat_renouvellement"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="equipement",
            constraint=models.UniqueConstraint(
                fields=["company", "numero_serie"],
                condition=models.Q(numero_serie__isnull=False)
                & ~models.Q(numero_serie=""),
                name="uniq_equipement_serie_par_societe",
            ),
        ),
    ]
