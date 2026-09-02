from django.db import migrations, models


class Migration(migrations.Migration):
    """CRX22 — ``Lead.score_ajustement`` : le delta de score qui SURVIT.

    Une automatisation (action « mettre à jour un champ ») qui écrivait
    ``Lead.score`` voyait son delta effacé au premier recalcul — édition du
    lead, webhook, ou le nouveau passage nocturne. Le delta a désormais sa
    propre colonne, appliquée PAR ``scoring.compute_score`` : plus rien ne
    l'écrase.

    Strictement additif : colonne NULLABLE, sans défaut — aucune réécriture
    des lignes existantes, aucun backfill. NULL = aucun ajustement, donc
    comportement historique inchangé pour tous les leads déjà en base.
    """

    dependencies = [
        ('crm', '0086_crx24_client_email_unique_ci'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='score_ajustement',
            field=models.SmallIntegerField(
                blank=True,
                help_text='Delta (positif ou négatif) ajouté au score '
                          'calculé. Survit aux recalculs. Vide = aucun '
                          'ajustement.',
                null=True,
                verbose_name='Ajustement du score'),
        ),
    ]
