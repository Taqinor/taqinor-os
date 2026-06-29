"""Migration additive : création du modèle ``SignatureContrat``
(CONTRAT16 — signature électronique IN-APP + point e-sign).

Entièrement additive (``CreateModel`` + contrainte d'unicité + index) —
réversible via ``DeleteModel``. Une ``SignatureContrat`` matérialise la
signature électronique INTERNE d'un contrat : aucun prestataire d'e-sign
externe, aucune dépendance tierce. La validité juridique repose sur la **loi
marocaine 53-05** (un nom dactylographié consenti vaut signature). On enregistre
qui a signé (``signataire_nom`` + ``signataire`` utilisateur agissant éventuel),
à quel titre (``role_signataire``) et les preuves (``ip_adresse``,
``user_agent``, ``date_signature``, ``methode``). La société et l'utilisateur
agissant sont posés côté serveur (jamais lus du corps de requête).

RUNTIME-SAFETY (leçon FG136) : ``ip_adresse`` ≤ 45 (IPv6) ; ``user_agent`` est
un ``TextField`` car potentiellement très long. La contrainte d'unicité et
l'index sont nommés explicitement (≤30 chars) pour éviter la divergence
d'auto-nommage Django.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contrats", "0012_contratactivity"),
    ]

    operations = [
        migrations.CreateModel(
            name="SignatureContrat",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "signataire_nom",
                    models.CharField(
                        max_length=255, verbose_name="Nom du signataire"
                    ),
                ),
                (
                    "role_signataire",
                    models.CharField(
                        choices=[
                            ("client", "Client"),
                            ("prestataire", "Prestataire"),
                            ("temoin", "Témoin"),
                        ],
                        default="client",
                        max_length=20,
                        verbose_name="Rôle du signataire",
                    ),
                ),
                (
                    "date_signature",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Signé le"
                    ),
                ),
                (
                    "ip_adresse",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=45,
                        verbose_name="Adresse IP",
                    ),
                ),
                (
                    "user_agent",
                    models.TextField(
                        blank=True, default="", verbose_name="User agent"
                    ),
                ),
                (
                    "methode",
                    models.CharField(
                        choices=[
                            ("typed", "Nom dactylographié"),
                            ("draw", "Signature dessinée"),
                        ],
                        default="typed",
                        max_length=20,
                        verbose_name="Méthode de signature",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contrats_signatures",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "contrat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="signatures",
                        to="contrats.contrat",
                        verbose_name="Contrat",
                    ),
                ),
                (
                    "signataire",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="contrats_signatures",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Utilisateur signataire",
                    ),
                ),
            ],
            options={
                "verbose_name": "Signature de contrat",
                "verbose_name_plural": "Signatures de contrat",
                "ordering": ["contrat_id", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="signaturecontrat",
            constraint=models.UniqueConstraint(
                fields=["contrat", "role_signataire"],
                name="contrats_signature_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="signaturecontrat",
            index=models.Index(
                fields=["contrat", "role_signataire"],
                name="contrats_sig_ct_role",
            ),
        ),
    ]
