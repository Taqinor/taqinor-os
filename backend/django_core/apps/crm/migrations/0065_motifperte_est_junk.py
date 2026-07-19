# PUB28 — taxonomie junk-lead. Un seul champ additif, défaut False → motifs
# existants (et tout lead perdu déjà en base) strictement inchangés. Purement
# additive et révertable (AddField / RemoveField automatique).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0064_lw28_leadactivity_pinned'),
    ]

    operations = [
        migrations.AddField(
            model_name='motifperte',
            name='est_junk',
            field=models.BooleanField(
                default=False,
                help_text="Numéro invalide, spam/bot, hors zone, jamais "
                          "répondu — distinct d'un motif de perte commercial "
                          "réel.",
                verbose_name='Motif junk (pas un vrai prospect)',
            ),
        ),
    ]
