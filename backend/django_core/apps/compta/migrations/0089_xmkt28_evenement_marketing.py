# XMKT28 - evenements marketing legers : EvenementMarketing (salon/porte
# ouverte/webinaire) + InscriptionEvenement (statut present/absent, QR
# check-in, lead_id opaque). Additif, nouvelles tables.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0088_xmkt27_enquete_reponseenquete"),
    ]

    operations = [
        migrations.CreateModel(
            name="EvenementMarketing",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("nom", models.CharField(
                    max_length=200, verbose_name="Nom de l'événement")),
                ("type_evenement", models.CharField(
                    choices=[
                        ("salon", "Salon"),
                        ("porte_ouverte", "Porte ouverte"),
                        ("webinaire", "Webinaire"),
                    ],
                    default="salon", max_length=20,
                    verbose_name="Type d'événement")),
                ("date_debut", models.DateTimeField(
                    verbose_name="Date de début")),
                ("date_fin", models.DateTimeField(
                    blank=True, null=True, verbose_name="Date de fin")),
                ("lieu", models.CharField(
                    blank=True, default="", max_length=255,
                    verbose_name="Lieu (ou lien visio)")),
                ("capacite", models.PositiveIntegerField(
                    blank=True, null=True, verbose_name="Capacité")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="evenements_marketing",
                    to="authentication.company", verbose_name="Société")),
            ],
            options={
                "verbose_name": "Événement marketing",
                "verbose_name_plural": "Événements marketing",
                "ordering": ["-date_debut"],
            },
        ),
        migrations.CreateModel(
            name="InscriptionEvenement",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("nom", models.CharField(max_length=200, verbose_name="Nom")),
                ("email", models.EmailField(
                    blank=True, default="", max_length=254,
                    verbose_name="Email")),
                ("telephone", models.CharField(
                    blank=True, default="", max_length=32,
                    verbose_name="Téléphone (normalisé)")),
                ("statut", models.CharField(
                    choices=[
                        ("inscrit", "Inscrit"), ("confirme", "Confirmé"),
                        ("present", "Présent"), ("absent", "Absent"),
                    ],
                    default="inscrit", max_length=10, verbose_name="Statut")),
                ("qr_token", models.CharField(
                    blank=True, default="", max_length=64, null=True,
                    unique=True, verbose_name="Jeton QR de check-in")),
                ("lead_id", models.PositiveIntegerField(
                    blank=True, null=True,
                    verbose_name="Lead créé (id crm)")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Inscrit le")),
                ("date_pointage", models.DateTimeField(
                    blank=True, null=True,
                    verbose_name="Pointé (check-in) le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="inscriptions_evenement",
                    to="authentication.company", verbose_name="Société")),
                ("evenement", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="inscriptions", to="compta.evenementmarketing",
                    verbose_name="Événement")),
            ],
            options={
                "verbose_name": "Inscription à un événement",
                "verbose_name_plural": "Inscriptions à un événement",
                "ordering": ["-date_creation"],
            },
        ),
    ]
