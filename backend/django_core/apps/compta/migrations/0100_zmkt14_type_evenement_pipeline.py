# ZMKT14 - types d'evenements + modeles reutilisables (TypeEvenement) +
# pipeline d'etapes configurable (etape, type_modele) sur EvenementMarketing.
# Additif : etape par defaut 'nouveau', type_modele NULL = comportement
# actuel.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0099_zmkt12_enquete_partage"),
    ]

    operations = [
        migrations.CreateModel(
            name="TypeEvenement",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("nom", models.CharField(
                    max_length=200, verbose_name="Nom du modèle")),
                ("type_evenement_defaut", models.CharField(
                    default="salon", max_length=20,
                    verbose_name="Type d'événement par défaut")),
                ("config_defaut", models.JSONField(
                    blank=True, default=dict,
                    verbose_name="Configuration par défaut (JSON)")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="types_evenement", to="authentication.company",
                    verbose_name="Société")),
            ],
            options={
                "verbose_name": "Type d'événement (modèle)",
                "verbose_name_plural": "Types d'événement (modèles)",
                "ordering": ["nom"],
            },
        ),
        migrations.AddField(
            model_name="evenementmarketing",
            name="etape",
            field=models.CharField(
                choices=[
                    ("nouveau", "Nouveau"), ("confirme", "Confirmé"),
                    ("annonce", "Annoncé"), ("termine", "Terminé"),
                ],
                default="nouveau", max_length=12,
                verbose_name="Étape (pipeline événement, PAS le funnel CRM)"),
        ),
        migrations.AddField(
            model_name="evenementmarketing",
            name="type_modele",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="evenements_crees", to="compta.typeevenement",
                verbose_name="Créé depuis le modèle"),
        ),
    ]
