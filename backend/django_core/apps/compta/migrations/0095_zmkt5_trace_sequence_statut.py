# ZMKT5 - traces d'activite de sequence (planifie/traite/rejete) + motif de
# rejet sur ExecutionEtapeSequence. Additif : defaut 'traite' + motif vide =
# comportement actuel (chaque execution etait deja consideree traitee).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0094_zmkt3_campagne_est_modele"),
    ]

    operations = [
        migrations.AddField(
            model_name="executionetapesequence",
            name="statut_trace",
            field=models.CharField(
                choices=[
                    ("planifie", "Planifié"), ("traite", "Traité"),
                    ("rejete", "Rejeté"),
                ],
                default="traite", max_length=10,
                verbose_name="Statut de trace"),
        ),
        migrations.AddField(
            model_name="executionetapesequence",
            name="motif_rejet",
            field=models.CharField(
                blank=True, default="",
                choices=[
                    ("sans_consentement", "Pas de consentement"),
                    ("supprime", "Supprimé (liste de suppression)"),
                    ("hors_fenetre", "Hors fenêtre de silence"),
                    ("erreur_envoi", "Erreur d'envoi"),
                ],
                max_length=20, verbose_name="Motif de rejet"),
        ),
    ]
