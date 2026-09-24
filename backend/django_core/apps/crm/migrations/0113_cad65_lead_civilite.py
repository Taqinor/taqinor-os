# CAD65 (audit L3 du 21/09/2026) — « Bonjour M. » était codé en dur dans les
# textes de relance, et ni le lead ni le client ne portaient de civilité : une
# cliente recevait « M. » sur tous les messages. Un AddField additif et
# nullable (même convention que `langue_preferee`) : aucune donnée existante
# n'est touchée — un lead sans civilité reçoit la salutation NEUTRE.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0112_cad158_facture_hiver_question'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='civilite',
            field=models.CharField(blank=True, choices=[('M.', 'M.'), ('Mme', 'Mme')], help_text='Question au premier appel, seulement en cas de doute : « Je vous note Monsieur ou Madame ? » — facultative : vide, les messages disent « Bonjour [prénom] », jamais un genre supposé.', max_length=4, null=True, verbose_name='Civilité'),
        ),
    ]
