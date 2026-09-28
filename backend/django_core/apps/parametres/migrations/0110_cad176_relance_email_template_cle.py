# CAD176 (24/09/2026, audit CAD86) — backfill de `template_cle` sur le
# barreau E-MAIL déjà seedé de la cadence `generique`.
#
# `template_cle` existe déjà sur `CadenceRelanceEtape` (migration 0081) :
# AUCUN changement de schéma ici, seulement une donnée. Les sociétés créées
# APRÈS ce commit reçoivent la clé directement par `CADENCE_RELANCE_DEFAUT`
# (`seed_cadence`) ; celles créées AVANT ont déjà leur barreau (ordre 3,
# cadence generique, canal email) avec `template_cle=''` — `seed_cadence` ne
# le retouche jamais (`get_or_create`, jamais un `update`). Sans ce backfill,
# ces sociétés resteraient sur un barreau muet pour toujours.
#
# Filtre étroit (cadence + ordre + canal + template_cle vide) : ne touche
# JAMAIS un barreau déjà personnalisé par une société (un `template_cle` non
# vide n'est jamais écrasé). Peu de lignes concernées (au plus une par
# société) — pas de découpage par lots nécessaire (contrairement au backfill
# de masse de 0081).
from django.db import migrations


def poser_la_cle(apps, schema_editor):
    Etape = apps.get_model('parametres', 'CadenceRelanceEtape')
    Etape.objects.filter(
        cadence='generique', ordre=3, canal='email', template_cle='',
    ).update(template_cle='relance_email_j10')


def noop(apps, schema_editor):
    """Rollback : remettre `template_cle` à vide referait perdre le rendu
    pour les sociétés déjà seedées — laissé tel quel, sans effet."""


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0109_param_cadence_apres_contact_visite_cle'),
    ]

    operations = [
        migrations.RunPython(poser_la_cle, noop),
    ]
