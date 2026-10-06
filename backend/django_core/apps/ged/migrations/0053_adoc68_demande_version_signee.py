"""ADOC68 — PDF signé figé référencé par la demande de signature.

Additive et revertable : FK nullable `version_signee` (RESTRICT) de
`DemandeSignatureDocument` vers `DocumentVersion`, posée une seule fois à la
complétion par `services.figer_pdf_signe`.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ged', '0052_adoc65_signataire_preuves'),
    ]

    operations = [
        migrations.AddField(
            model_name='demandesignaturedocument',
            name='version_signee',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name='demandes_signature_figees',
                to='ged.documentversion',
                verbose_name='version signée figée'),
        ),
    ]
