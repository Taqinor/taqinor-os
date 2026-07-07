# ZMKT11 - mode d'acces, connexion requise et nombre de tentatives
# d'enquete + entree de test. Additif : defaut lien_public/illimite =
# comportement actuel (ouvert, sans controle d'acces).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0097_zmkt10_enquete_scoring_certification"),
    ]

    operations = [
        migrations.AddField(
            model_name="enquete",
            name="mode_acces",
            field=models.CharField(
                choices=[
                    ("lien_public", "Lien public"),
                    ("invites_seulement", "Invités seulement"),
                ],
                default="lien_public", max_length=20,
                verbose_name="Mode d'accès"),
        ),
        migrations.AddField(
            model_name="enquete",
            name="connexion_requise",
            field=models.BooleanField(
                default=False,
                verbose_name="Connexion requise (email de contact)"),
        ),
        migrations.AddField(
            model_name="enquete",
            name="tentatives_max",
            field=models.PositiveSmallIntegerField(
                blank=True, null=True,
                verbose_name="Tentatives max par répondant"),
        ),
        migrations.AddField(
            model_name="enquete",
            name="jetons_invites",
            field=models.JSONField(
                blank=True, default=list,
                verbose_name="Jetons d'invitation (JSON)"),
        ),
    ]
