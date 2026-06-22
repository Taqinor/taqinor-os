# Generated for FG158 — emergency contact & extended personal coordinates on
# DossierEmploye (personne à prévenir, groupe sanguin, adresse/téléphone/e-mail
# perso). All additive, optional/blank with safe defaults — existing employee
# rows stay valid (no AddField(unique, default) trap). Medical/emergency data
# lives on the dossier under the same admin/responsable access control.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rh", "0004_remuneration"),
    ]

    operations = [
        migrations.AddField(
            model_name="dossieremploye",
            name="adresse_perso",
            field=models.CharField(
                blank=True,
                default="",
                max_length=255,
                verbose_name="Adresse personnelle",
            ),
        ),
        migrations.AddField(
            model_name="dossieremploye",
            name="telephone_perso",
            field=models.CharField(
                blank=True,
                default="",
                max_length=30,
                verbose_name="Téléphone personnel",
            ),
        ),
        migrations.AddField(
            model_name="dossieremploye",
            name="email_perso",
            field=models.EmailField(
                blank=True,
                default="",
                max_length=254,
                verbose_name="E-mail personnel",
            ),
        ),
        migrations.AddField(
            model_name="dossieremploye",
            name="urgence_nom",
            field=models.CharField(
                blank=True,
                default="",
                max_length=120,
                verbose_name="Personne à prévenir — nom",
            ),
        ),
        migrations.AddField(
            model_name="dossieremploye",
            name="urgence_lien",
            field=models.CharField(
                blank=True,
                default="",
                max_length=60,
                verbose_name="Personne à prévenir — lien",
            ),
        ),
        migrations.AddField(
            model_name="dossieremploye",
            name="urgence_telephone",
            field=models.CharField(
                blank=True,
                default="",
                max_length=30,
                verbose_name="Personne à prévenir — téléphone",
            ),
        ),
        migrations.AddField(
            model_name="dossieremploye",
            name="groupe_sanguin",
            field=models.CharField(
                blank=True,
                default="",
                max_length=3,
                verbose_name="Groupe sanguin",
            ),
        ),
    ]
