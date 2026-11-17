"""17/11/2026 (fondateur) — les barreaux déjà seedés reçoivent les textes que le
code livre désormais par défaut (`seed_cadence` ne retouche jamais une ligne
existante, seule une migration de données change la production).

Chaque rattrapage vise UNIQUEMENT une ligne qui porte encore exactement le
défaut d'avant ; une `template_cle` changée par la société reste intacte :
  * `apres_devis` ordre 9 (J28, appel) `appel_suivi_j11` -> `appel_validite` ;
  * `apres_devis` ordre 11 (J90, appel) `appel_suivi_j11` -> `appel_dernier_suivi` ;
  * `deuxieme_affaire` ordre 2 (appel) `appel_ouverture` ->
    `appel_ouverture_deuxieme_affaire` ;
  * `apres_contact`, par clé moteur et clé de message VIDE :
    `message_creneau` (WhatsApp) -> `message_creneau`,
    `dernier_appel` (appel) -> `appel_relance`,
    `rappel_convenu` (appel) -> `appel_rappel_convenu` ;
  * `visite`, clé moteur `planifier` (appel) et clé vide ->
    `appel_planifier_visite`.

Idempotent : la 2e application ne retrouve plus aucune ligne au défaut d'avant.
Les touches déjà posées (`RelanceEtape`) ne bougent pas (le rendu retrouve le
texte d'une étape du moteur sans gabarit par sa clé). Marche arrière : rien (une
ligne rattrapée ne se distingue plus d'une ligne que la société a réglée elle-même).
"""
from django.db import migrations

# (cadence, ordre, canal, delai_jours, ancienne clé, nouvelle clé)
_PAR_ORDRE = (
    ('apres_devis', 9, 'appel', 28, 'appel_suivi_j11', 'appel_validite'),
    ('apres_devis', 11, 'appel', 90, 'appel_suivi_j11', 'appel_dernier_suivi'),
)
# (cadence, clé moteur, canal, nouvelle clé) — l'ancienne clé de message est vide.
_PAR_CLE_MOTEUR = (
    ('apres_contact', 'message_creneau', 'whatsapp', 'message_creneau'),
    ('apres_contact', 'dernier_appel', 'appel', 'appel_relance'),
    ('apres_contact', 'rappel_convenu', 'appel', 'appel_rappel_convenu'),
    ('visite', 'planifier', 'appel', 'appel_planifier_visite'),
)


def _poser(lignes, nouvelle):
    for ligne in lignes.iterator():
        ligne.template_cle = nouvelle
        ligne.save(update_fields=['template_cle'])


def poser_les_textes(apps, schema_editor):
    Etape = apps.get_model('parametres', 'CadenceRelanceEtape')
    for cadence, ordre, canal, jours, ancienne, nouvelle in _PAR_ORDRE:
        _poser(Etape.objects.filter(
            cadence=cadence, ordre=ordre, canal=canal, delai_jours=jours,
            template_cle=ancienne), nouvelle)
    _poser(Etape.objects.filter(
        cadence='deuxieme_affaire', ordre=2, canal='appel',
        template_cle='appel_ouverture'), 'appel_ouverture_deuxieme_affaire')
    for cadence, cle, canal, nouvelle in _PAR_CLE_MOTEUR:
        _poser(Etape.objects.filter(
            cadence=cadence, cle=cle, canal=canal, template_cle=''), nouvelle)


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0141_messagetemplate_cles_textes_1711'),
    ]

    operations = [
        migrations.RunPython(poser_les_textes, migrations.RunPython.noop),
    ]
