# ZMKT17 - communications programmees d'evenement (rappels avant/relance
# apres). Additif, nouvelle table.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0102_zmkt16_question_evenement"),
    ]

    operations = [
        migrations.CreateModel(
            name="CommunicationEvenement",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("canal", models.CharField(
                    choices=[
                        ("email", "Email"), ("sms", "SMS"),
                        ("whatsapp", "WhatsApp"),
                    ],
                    default="email", max_length=10, verbose_name="Canal")),
                ("gabarit", models.TextField(
                    blank=True, default="", verbose_name="Corps")),
                ("intervalle", models.IntegerField(
                    verbose_name="Intervalle (signé)")),
                ("unite_intervalle", models.CharField(
                    choices=[("heures", "Heures"), ("jours", "Jours")],
                    default="jours", max_length=10, verbose_name="Unité")),
                ("envoyee_le", models.DateTimeField(
                    blank=True, null=True, verbose_name="Envoyée le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="communications_evenement",
                    to="authentication.company", verbose_name="Société")),
                ("evenement", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="communications",
                    to="compta.evenementmarketing", verbose_name="Événement")),
            ],
            options={
                "verbose_name": "Communication d'événement",
                "verbose_name_plural": "Communications d'événement",
                "ordering": ["intervalle"],
            },
        ),
    ]
