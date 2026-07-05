# ZMKT10 - scoring d'enquete + mode certification + score requis. Additif :
# mode_scoring='aucun' par defaut = comportement actuel (pas de score).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0096_zmkt9_enquete_mise_en_page"),
    ]

    operations = [
        migrations.AddField(
            model_name="enquete",
            name="mode_scoring",
            field=models.CharField(
                choices=[
                    ("aucun", "Aucun"),
                    ("avec_reponses_a_la_fin", "Avec réponses à la fin"),
                    ("sans_reponses", "Sans réponses"),
                ],
                default="aucun", max_length=25, verbose_name="Mode de scoring"),
        ),
        migrations.AddField(
            model_name="enquete",
            name="score_requis_pct",
            field=models.PositiveSmallIntegerField(
                blank=True, null=True, verbose_name="Score requis (%)"),
        ),
        migrations.AddField(
            model_name="enquete",
            name="est_certification",
            field=models.BooleanField(
                default=False, verbose_name="Est une certification"),
        ),
        migrations.AddField(
            model_name="reponseenquete",
            name="score_pct",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True,
                verbose_name="Score obtenu (%)"),
        ),
        migrations.AddField(
            model_name="reponseenquete",
            name="reussi",
            field=models.BooleanField(
                blank=True, null=True,
                verbose_name="Réussi (si scoring/certification)"),
        ),
        migrations.AddField(
            model_name="reponseenquete",
            name="certificat_genere",
            field=models.BooleanField(
                default=False, verbose_name="Certificat généré"),
        ),
    ]
