"""RPT2 (copilote vague 2) — ``marge_brute`` et ``dso`` ne se résolvent pas.

Leurs adaptateurs ``compta.marge_brute`` / ``compta.dso`` n'existent plus (l'app
``compta`` est parquée, aucun ``register_adapter('compta.…')`` dans le dépôt) :
la métrique était listée à l'assistant, qui la demandait et recevait une
erreur. Aucune formule de remplacement n'est inventée ; la ligne est
DÉSACTIVÉE (``actif=False``) — jamais supprimée : ses versions, alertes et
widgets la référencent encore, et la réactiver quand un calcul canonique existera
suffit (le retour arrière ne réactive rien : une désactivation du fondateur
ne doit pas être défaite). Données seules : seule une définition dont la mesure est EXACTEMENT
l'ancien défaut (``{'adapter': 'compta.<clé>'}``) est touchée ; une définition
que le fondateur a réécrite ne l'est jamais ; un second passage n'écrit rien.
"""
from django.db import migrations

CLES = ('marge_brute', 'dso')


def desactiver(apps, schema_editor):
    Definition = apps.get_model('semantic', 'MetricDefinition')
    # Lecture par lots (`.iterator`) ; écriture ligne à ligne par pk (YOPSB4).
    for cle in CLES:
        for definition in Definition.objects.filter(
                cle=cle, actif=True, mesure={'adapter': 'compta.%s' % cle}
        ).iterator(chunk_size=500):
            Definition.objects.filter(pk=definition.pk).update(actif=False)


class Migration(migrations.Migration):

    dependencies = [
        ('semantic', '0007_rpt_trois_ca'),
    ]

    operations = [
        migrations.RunPython(desactiver, migrations.RunPython.noop),
    ]
