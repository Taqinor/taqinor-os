from django.db import migrations, models


class Migration(migrations.Migration):
    """PVORD (fondateur 19/08/2026) — ordre PAR DÉFAUT des lignes de devis.

    Additive only : ajoute ``ParametresGammes.ordre_lignes`` (liste de rôles
    ``ROLES_AUTO_COMPOSITION``, défaut liste vide = ordre canonique du
    simulateur). Aucune table ni colonne existante n'est modifiée. Entièrement
    révertable.
    """

    dependencies = [
        ('ventes', '0098_pvfresh_pdf_render_meta'),
    ]

    operations = [
        migrations.AddField(
            model_name='parametresgammes',
            name='ordre_lignes',
            field=models.JSONField(
                blank=True, default=list,
                verbose_name='Ordre par défaut des lignes de devis',
                help_text="Liste de rôles ROLES_AUTO_COMPOSITION dans "
                          "l'ordre voulu (ex. ['panneau', 'onduleur_reseau', "
                          "...]). Liste vide = ordre canonique du "
                          "simulateur."),
        ),
    ]
