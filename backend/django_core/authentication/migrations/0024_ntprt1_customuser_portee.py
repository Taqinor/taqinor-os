# NTPRT1 — portée du compte (interne vs portail externe) + ids de rattachement
# portail par STRING-REF (entier seul, jamais un FK cross-app). Additif : défaut
# ``interne`` / NULL, aucun compte existant n'est affecté.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="portee",
            field=models.CharField(
                choices=[
                    ("interne", "Interne"),
                    ("portail_client", "Portail client"),
                    ("portail_fournisseur", "Portail fournisseur"),
                    ("portail_partenaire", "Portail partenaire"),
                ],
                default="interne",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="customuser",
            name="portail_client_id",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="customuser",
            name="portail_fournisseur_id",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="customuser",
            name="portail_partenaire_id",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
