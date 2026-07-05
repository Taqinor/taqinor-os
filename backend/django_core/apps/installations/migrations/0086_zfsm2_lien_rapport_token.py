from django.db import migrations, models


class Migration(migrations.Migration):
    """ZFSM2 — lien public tokenisé du compte-rendu d'intervention signé.

    `lien_rapport_token` est un jeton DISTINCT de `lien_client_token` (XFSM7,
    suivi « en route » uniquement) : ce jeton ouvre la page publique du
    compte-rendu final (F19). Additive — nullable/blank, aucune donnée
    existante affectée."""

    dependencies = [
        ('installations', '0085_zfsm1_fiche_intervention_template'),
    ]

    operations = [
        migrations.AddField(
            model_name='intervention',
            name='lien_rapport_token',
            field=models.CharField(
                blank=True, editable=False,
                help_text='Jeton public du lien compte-rendu signé (ZFSM2).',
                max_length=64, null=True, unique=True),
        ),
    ]
