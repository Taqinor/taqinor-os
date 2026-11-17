"""Rattrapage des barreaux seedés le 06/09/2026 (MRY4), que 0133/0134 n'ont pas
reconnus — constat prod du 16/11/2026 : 6 appels + 2 WhatsApp au lieu des
5 appels + 3 WhatsApp de D-CADV-1, et deux « Appel de suivi » sans script.

Le seed MRY4 du 06/09 posait `contact` ordre 4 « Appel 3 (répondeur) »
(`repondeur`) et ordre 6 « Appel 4 » (clé vide). CAD67 (21/09) a corrigé le
DÉFAUT, mais `seed_cadence` ne retouche jamais une ligne existante ; 0133
comparait ensuite l'ordre 6 au libellé d'après CAD67 (« Appel 4 (répondeur) »)
et a donc laissé la ligne du 06/09 : le « WhatsApp de valeur » n'existe plus
(l'ordre 5 est devenu un appel) et le protocole compte un appel de trop.

Trois rattrapages, chacun SEULEMENT sur une ligne qui porte encore exactement
les valeurs du seed du 06/09 (une valeur jamais saisie n'est pas une
personnalisation ; un barreau modifié par la société reste intact) :
  * `contact` ordre 6 « Appel 4 » sans clé -> « WhatsApp de valeur » v4, sauf
    si la société porte déjà un barreau actif `valeur_j1` (jamais deux) ;
  * `contact` ordre 4 « Appel 3 (répondeur) » -> « Appel 3 » / `appel_relance`
    (CAD67 : `repondeur` sur les appels 2 et 4 seulement) ;
  * `apres_devis` ordres 2 (J2) et 6 (J7), appels SANS clé de message ->
    `appel_suivi_j2` / `appel_suivi_j7` (CAD98) ; le libellé n'est pas touché.

Idempotent : la 2e application ne retrouve plus aucune ligne à ces valeurs.
Les touches déjà posées (`RelanceEtape`) ne bougent pas. Marche arrière : rien
(les lignes rattrapées ne se distinguent plus de celles que 0133 a écrites).
"""
import datetime

from django.db import migrations, models

T = datetime.time

_CONTACT_6_SEED = dict(canal='appel', delai_jours=2, delai_minutes=0,
                       dimanche_ok=False, actif=True, libelle='Appel 4',
                       template_cle='')
_CONTACT_6_V4 = dict(canal='whatsapp', delai_jours=2, delai_minutes=0,
                     heure_cible=T(17, 45), dimanche_ok=False, actif=True,
                     libelle='WhatsApp de valeur', template_cle='valeur_j1')
_CONTACT_4_SEED = dict(canal='appel', delai_jours=1, delai_minutes=0,
                       dimanche_ok=False, actif=True,
                       libelle='Appel 3 (répondeur)')
_CONTACT_4_CAD67 = dict(libelle='Appel 3', template_cle='appel_relance')
# ordre -> (délai en jours, clé du script)
_SCRIPTS_SUIVI = {2: (2, 'appel_suivi_j2'), 6: (7, 'appel_suivi_j7')}


def _heure(qs, heure):
    """L'heure du seed, ou nulle (seed d'avant CAD25)."""
    return qs.filter(models.Q(heure_cible=heure)
                     | models.Q(heure_cible__isnull=True))


def rattraper(apps, schema_editor):
    Etape = apps.get_model('parametres', 'CadenceRelanceEtape')
    contact = Etape.objects.filter(cadence='contact')

    for ligne in _heure(contact.filter(ordre=6, **_CONTACT_6_SEED),
                        T(18, 0)).iterator():
        if contact.filter(company_id=ligne.company_id, actif=True,
                          template_cle='valeur_j1').exists():
            continue
        for champ, valeur in _CONTACT_6_V4.items():
            setattr(ligne, champ, valeur)
        ligne.save()

    _heure(contact.filter(ordre=4, template_cle__in=['repondeur', ''],
                          **_CONTACT_4_SEED),
           T(10, 30)).update(**_CONTACT_4_CAD67)

    for ordre, (jours, cle) in _SCRIPTS_SUIVI.items():
        Etape.objects.filter(
            cadence='apres_devis', ordre=ordre, canal='appel',
            delai_jours=jours, actif=True, template_cle='',
        ).update(template_cle=cle)


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0138_amsg66_emailtemplate_rappel_rdv'),
    ]

    operations = [
        migrations.RunPython(rattraper, migrations.RunPython.noop),
    ]
