# AUD618 — une SEULE enquête NPS par chantier et par société.
#
# `_creer_enquete_nps_a_reception` reposait sur le seul `get_or_create`, sans
# garantie DB : deux réceptions concurrentes du même chantier pouvaient créer
# deux enquêtes et solliciter le client DEUX fois. La contrainte rend le
# `get_or_create` réellement course-safe (Django absorbe l'IntegrityError et
# re-lit la ligne gagnante).
#
# Additive et revertable. Les enquêtes sans chantier (`chantier_id` NULL) ne
# sont pas contraintes — d'où la `condition`.
#
# Écrite à la main (la chaîne d'import WeasyPrint bloque makemigrations sur
# cet hôte — voir 0006_ntmkt16_dernier_numero_version.py).
#
# NOTE : si une base porte déjà des doublons hérités, cette migration échoue à
# la création de l'index — c'est VOULU (un doublon est une double sollicitation
# client, à trancher explicitement, jamais à écraser en silence).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketing', '0009_aud616_webhook_secret'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='enquetenps',
            constraint=models.UniqueConstraint(
                condition=models.Q(('chantier_id__isnull', False)),
                fields=('company', 'chantier_id'),
                name='uniq_enquete_nps_par_chantier_et_societe'),
        ),
    ]
