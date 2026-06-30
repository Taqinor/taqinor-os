"""Migration additive CONTRAT22 — AlerteContrat (rappels via notifications).

Ajoute le modèle ``AlerteContrat`` : un rappel daté sur un ``Contrat`` (préavis,
échéance/renouvellement, ou date personnalisée), dispatché à sa date de
déclenchement via le système de notifications existant
(``apps.notifications.services.notify``) puis marqué ``envoyee``.

Purement additive et réversible (``DeleteModel``). Aucune donnée existante n'est
modifiée. Les index sont nommés explicitement (≤30 chars) pour éviter la
divergence d'auto-nommage Django (leçon migration index-name divergence).
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contrats", "0015_contrat_preavis_tacite_reconduction"),
    ]

    operations = [
        migrations.CreateModel(
            name="AlerteContrat",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("type_alerte", models.CharField(
                    choices=[
                        ("preavis", "Échéance de préavis"),
                        ("echeance", "Échéance / renouvellement"),
                        ("personnalise", "Date personnalisée"),
                    ],
                    default="personnalise", max_length=20,
                    verbose_name="Type d'alerte")),
                ("date_declenchement", models.DateField(
                    verbose_name="Date de déclenchement")),
                ("message", models.TextField(
                    blank=True, default="", verbose_name="Message")),
                ("statut", models.CharField(
                    choices=[
                        ("planifiee", "Planifiée"),
                        ("envoyee", "Envoyée"),
                        ("annulee", "Annulée"),
                    ],
                    default="planifiee", max_length=20,
                    verbose_name="Statut")),
                ("date_envoi", models.DateTimeField(
                    blank=True, null=True, verbose_name="Envoyée le")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créée le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="contrats_alertes",
                    to="authentication.company",
                    verbose_name="Société")),
                ("contrat", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="alertes",
                    to="contrats.contrat",
                    verbose_name="Contrat")),
                ("cree_par", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="contrats_alertes_creees",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Créée par")),
            ],
            options={
                "verbose_name": "Alerte de contrat",
                "verbose_name_plural": "Alertes de contrat",
                "ordering": ["date_declenchement", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="alertecontrat",
            index=models.Index(
                fields=["company", "statut", "date_declenchement"],
                name="contrats_alerte_co_st_dt"),
        ),
        migrations.AddIndex(
            model_name="alertecontrat",
            index=models.Index(
                fields=["contrat", "statut"],
                name="contrats_alerte_ct_st"),
        ),
    ]
