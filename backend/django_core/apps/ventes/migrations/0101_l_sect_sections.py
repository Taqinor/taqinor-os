from django.db import migrations, models


class Migration(migrations.Migration):
    """L-SECT (fondateur 24/08/2026) — ``ShareLink.sections``.

    Le commercial choisit, AVANT d'envoyer la page devis, quelles sections le
    client reçoit. Dict {clé: bool} whitelisté côté vue (roof3d, sld, pdf,
    bankable, economies, jour_type, gammes).

    ADDITIVE ONLY et entièrement révertable : une seule colonne JSON, défaut
    ``dict`` vide, aucune table ni colonne existante modifiée. Un dict vide
    signifie « aucune clé posée » → tous les liens existants gardent EXACTEMENT
    leur comportement d'aujourd'hui (aucune donnée à migrer, donc aucun
    RunPython)."""

    dependencies = [
        ('ventes', '0100_l_niv_niveau_otp_lecture'),
    ]

    operations = [
        migrations.AddField(
            model_name='sharelink',
            name='sections',
            field=models.JSONField(
                blank=True, default=dict,
                verbose_name='Sections servies au client'),
        ),
    ]
