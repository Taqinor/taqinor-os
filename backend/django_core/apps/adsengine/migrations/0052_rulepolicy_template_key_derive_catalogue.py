# Correctif de divergence de registres — ``RulePolicy.template_key``.
#
# Avant : les ``choices`` étaient une liste FIGÉE recopiée à la main dans
# ``rules.py`` (5 gabarits ADSENG4), alors que le catalogue réellement affiché
# par ``GET /regles/catalogue/`` vit dans ``rule_templates.py`` (15 gabarits,
# ADSENG14 + ADSDEEP38). Conséquence en production : armer ``stop_loss_cpl`` —
# le PREMIER gabarit du catalogue — repartait en 400 « n'est pas un choix
# valide ».
#
# Après : ``choices`` est le CALLABLE ``rules.rule_template_choices``, qui dérive
# la liste des deux registres vivants (catalogue réel d'abord, clés historiques
# ADSENG4 ensuite pour ne jamais invalider une ligne déjà en base). Django ≥ 5.0
# sérialise un ``choices`` callable par RÉFÉRENCE : cette migration est donc la
# DERNIÈRE que le catalogue provoque — ajouter un gabarit ne fera plus bouger
# l'état des migrations.
#
# Aucun DDL : ``choices`` est une contrainte de VALIDATION Django (formulaires,
# admin, ChoiceField DRF), jamais une contrainte SQL — cette migration ne touche
# pas la table.
import apps.adsengine.rules
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0051_pub104_insight_rollup'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rulepolicy',
            name='template_key',
            field=models.CharField(
                choices=apps.adsengine.rules.rule_template_choices,
                max_length=48, verbose_name='Template de règle'),
        ),
    ]
