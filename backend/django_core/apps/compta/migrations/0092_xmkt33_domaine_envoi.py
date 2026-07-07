# XMKT33 - assistant d'authentification du domaine d'envoi (SPF/DKIM/DMARC).
# Additif, nouvelle table.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0091_xmkt31_campagneparente"),
    ]

    operations = [
        migrations.CreateModel(
            name="DomaineEnvoi",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("domaine", models.CharField(
                    max_length=255, verbose_name="Domaine")),
                ("spf_verifie", models.BooleanField(
                    default=False, verbose_name="SPF vérifié")),
                ("dkim_verifie", models.BooleanField(
                    default=False, verbose_name="DKIM vérifié")),
                ("dmarc_verifie", models.BooleanField(
                    default=False, verbose_name="DMARC vérifié")),
                ("derniere_verification_le", models.DateTimeField(
                    blank=True, null=True,
                    verbose_name="Dernière vérification le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="domaines_envoi", to="authentication.company",
                    verbose_name="Société")),
            ],
            options={
                "verbose_name": "Domaine d'envoi",
                "verbose_name_plural": "Domaines d'envoi",
                "ordering": ["domaine"],
            },
        ),
        migrations.AddConstraint(
            model_name="domaineenvoi",
            constraint=models.UniqueConstraint(
                fields=("company", "domaine"),
                name="uniq_domaine_envoi_par_societe"),
        ),
    ]
