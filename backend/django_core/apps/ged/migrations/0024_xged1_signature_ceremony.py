# XGED1 — Cérémonie de signature in-app sur document GED (lien public
# tokenisé, loi 53-05).
#
# Migration strictement ADDITIVE (réversible) : ajoute des champs à
# `DemandeSignatureDocument` (GED30) — un `token` public unique (pattern
# `PartageGed.token`), une expiration optionnelle, et les preuves IMMUABLES de
# la cérémonie (consentement, IP, user-agent, hash SHA-256, signature
# tapée/tracée, refus + motif). Aucune table existante n'est retirée ni
# renommée ; les demandes GED30 pré-existantes reçoivent un token via le
# défaut du champ au moment de la migration (backfill implicite Django).
import apps.ged.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ged", "0023_journalacces_quotastockage"),
    ]

    operations = [
        migrations.AddField(
            model_name="demandesignaturedocument",
            name="token",
            field=models.CharField(
                default=apps.ged.models._default_partage_token,
                editable=False,
                max_length=64,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="demandesignaturedocument",
            name="expires_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="expire le"
            ),
        ),
        migrations.AddField(
            model_name="demandesignaturedocument",
            name="consentement_explicite",
            field=models.BooleanField(
                default=False, verbose_name="consentement explicite à signer"
            ),
        ),
        migrations.AddField(
            model_name="demandesignaturedocument",
            name="adresse_ip",
            field=models.GenericIPAddressField(
                blank=True, null=True, verbose_name="adresse IP du signataire"
            ),
        ),
        migrations.AddField(
            model_name="demandesignaturedocument",
            name="user_agent",
            field=models.CharField(
                blank=True, default="", max_length=512, verbose_name="user-agent"
            ),
        ),
        migrations.AddField(
            model_name="demandesignaturedocument",
            name="hash_contenu",
            field=models.CharField(
                blank=True,
                default="",
                max_length=64,
                verbose_name="hash du contenu signé (SHA-256)",
            ),
        ),
        migrations.AddField(
            model_name="demandesignaturedocument",
            name="signature_texte",
            field=models.CharField(
                blank=True, default="", max_length=255, verbose_name="signature tapée"
            ),
        ),
        migrations.AddField(
            model_name="demandesignaturedocument",
            name="signature_tracee",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="signature tracée (vecteur/data-URL)",
            ),
        ),
        migrations.AddField(
            model_name="demandesignaturedocument",
            name="motif_refus",
            field=models.TextField(
                blank=True, default="", verbose_name="motif de refus"
            ),
        ),
        migrations.AddField(
            model_name="demandesignaturedocument",
            name="refuse_le",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="refusée le"
            ),
        ),
    ]
