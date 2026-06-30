"""Migration additive : modèle ``PieceConformite``
(CONTRAT34 — pièces obligatoires & attestations).

Entièrement additive (``CreateModel`` + index) — réversible via ``DeleteModel``.
Une ``PieceConformite`` recense une pièce justificative attendue sur un
``Contrat`` (assurance, attestation fiscale, RIB, KYC, certificat, PV…), avec un
drapeau ``obligatoire`` et un statut de complétude (manquante → fournie →
validee/expiree/refusee). La pièce déposée peut être reliée LÂCHEMENT à un
document GED par ``ged_document_id`` (id seul, jamais un FK dur ni un import de
``ged.models``). Le statut est propre au suivi de conformité : il ne touche
jamais le ``Contrat.statut`` (CONTRAT12) ni le funnel ``STAGES.py`` (rule #2). La
société est posée côté serveur.

RUNTIME-SAFETY (leçon FG136) : ``libelle`` borné, ``note`` en ``TextField`` ;
les index sont nommés explicitement (≤30 chars).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contrats", "0026_indexationprix"),
    ]

    operations = [
        migrations.CreateModel(
            name="PieceConformite",
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
                    "type_piece",
                    models.CharField(
                        choices=[
                            ("assurance", "Attestation d'assurance"),
                            ("fiscale", "Attestation fiscale"),
                            ("rib", "RIB"),
                            ("kyc", "Pièce KYC / identité"),
                            ("certificat", "Certificat de conformité"),
                            ("pv_reception", "PV de réception"),
                            ("autre", "Autre"),
                        ],
                        default="autre",
                        max_length=20,
                        verbose_name="Type de pièce",
                    ),
                ),
                (
                    "libelle",
                    models.CharField(
                        max_length=200, verbose_name="Libellé"
                    ),
                ),
                (
                    "obligatoire",
                    models.BooleanField(
                        default=True, verbose_name="Obligatoire"
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("manquante", "Manquante"),
                            ("fournie", "Fournie"),
                            ("validee", "Validée"),
                            ("expiree", "Expirée"),
                            ("refusee", "Refusée"),
                        ],
                        default="manquante",
                        max_length=20,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "ged_document_id",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        verbose_name="ID du document GED",
                    ),
                ),
                (
                    "date_fourniture",
                    models.DateField(
                        blank=True, null=True, verbose_name="Fournie le"
                    ),
                ),
                (
                    "date_expiration",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="Date d'expiration",
                    ),
                ),
                (
                    "note",
                    models.TextField(
                        blank=True, default="", verbose_name="Note"
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créée le"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contrats_pieces_conformite",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "contrat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pieces_conformite",
                        to="contrats.contrat",
                        verbose_name="Contrat",
                    ),
                ),
            ],
            options={
                "verbose_name": "Pièce de conformité",
                "verbose_name_plural": "Pièces de conformité",
                "ordering": ["contrat_id", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="piececonformite",
            index=models.Index(
                fields=["company", "statut"],
                name="contrats_piece_co_st",
            ),
        ),
        migrations.AddIndex(
            model_name="piececonformite",
            index=models.Index(
                fields=["contrat", "obligatoire"],
                name="contrats_piece_ct_obl",
            ),
        ),
    ]
