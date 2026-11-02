"""CADV24 — le gabarit `apres_devis` passe à la cadence v4 (D-CADV-3) : J1, J2
appel, J3, J7 appel, J10, J14 appel, J28 appel de validité, J60, J90 ; J4 et J6
désactivés.

Même patron que 0133 (CADV23) : `seed_cadence` ne retouche jamais un barreau
existant, seule une migration de données change la production. Un barreau n'est
réécrit QUE s'il porte encore exactement les valeurs v3 (clé vide et heure
nulle d'anciens seeds tolérées) : un barreau modifié par la société reste
intact. Les ordres 1-3 et 6 (appel J7, inchangé) ne bougent pas ; 4 et 5 sont
désactivés ; 7-10 passent aux valeurs v4 ; l'ordre 11 (appel J90) est créé pour
les sociétés qui ont déjà une cadence après-devis. Idempotent : la 2e
application ne retrouve plus aucune ligne aux valeurs v3 (`actif` fait partie du
critère). Marche arrière : valeurs v3 des seuls barreaux restés à v4, ordre 11
désactivé (jamais supprimé) ; les touches déjà posées ne bougent pas.
"""
import datetime

from django.db import migrations, models

T = datetime.time
_MSG = T(9, 30)
_APPEL = T(18, 0)


def _ligne(canal, jours, heure, libelle, cle, actif=True):
    return dict(canal=canal, delai_jours=jours, delai_minutes=0,
                heure_cible=heure, dimanche_ok=False, actif=actif,
                libelle=libelle, template_cle=cle)


_V3 = {
    4: _ligne('whatsapp', 4, _MSG, 'Preuve — chantier comparable', 'j4_preuve'),
    5: _ligne('whatsapp', 6, _MSG, 'Garanties fabricants', 'j6_garanties'),
    7: _ligne('whatsapp', 9, _MSG, 'Validité de la proposition',
              'j9_validite'),
    8: _ligne('appel', 11, _APPEL, 'Appel de suivi', 'appel_suivi_j11'),
    9: _ligne('whatsapp', 13, _MSG, 'Dernier message', 'j13_dernier'),
    10: _ligne('whatsapp', 14, _MSG, 'Mise en pause', 'j14_pause'),
}
_V4 = {
    4: dict(_V3[4], actif=False),
    5: dict(_V3[5], actif=False),
    7: _ligne('whatsapp', 10, _MSG, 'Garanties fabricants', 'j6_garanties'),
    8: _ligne('appel', 14, _APPEL, 'Appel de décision', 'appel_suivi_j11'),
    9: _ligne('appel', 28, _APPEL, 'Appel de validité', 'appel_suivi_j11'),
    10: _ligne('whatsapp', 60, _MSG, 'Dernier message', 'j13_dernier'),
}
_ORDRE_11 = _ligne('appel', 90, _APPEL, 'Dernier appel', 'appel_suivi_j11')


def _lignes(Etape, ordre, valeurs):
    """Lignes `apres_devis` de cet ordre portant exactement `valeurs` (clé de
    message vide et heure nulle tolérées : valeur jamais saisie)."""
    filtre = {k: v for k, v in valeurs.items()
              if k not in ('template_cle', 'heure_cible')}
    qs = Etape.objects.filter(
        cadence='apres_devis', ordre=ordre, **filtre
    ).filter(template_cle__in=[valeurs['template_cle'], ''])
    return qs.filter(models.Q(heure_cible=valeurs['heure_cible'])
                     | models.Q(heure_cible__isnull=True))


def _bascule(apps, de, vers):
    Etape = apps.get_model('parametres', 'CadenceRelanceEtape')
    for ordre in sorted(de):
        for ligne in _lignes(Etape, ordre, de[ordre]).iterator():
            for champ, valeur in vers[ordre].items():
                setattr(ligne, champ, valeur)
            ligne.save()


def vers_v4(apps, schema_editor):
    _bascule(apps, _V3, _V4)
    Etape = apps.get_model('parametres', 'CadenceRelanceEtape')
    societes = (Etape.objects.filter(cadence='apres_devis')
                .values_list('company_id', flat=True).distinct())
    for company_id in list(societes):
        if Etape.objects.filter(company_id=company_id, cadence='apres_devis',
                                ordre=11).exists():
            continue
        Etape.objects.create(company_id=company_id, cadence='apres_devis',
                             ordre=11, cle='', **_ORDRE_11)


def vers_v3(apps, schema_editor):
    _bascule(apps, _V4, _V3)
    Etape = apps.get_model('parametres', 'CadenceRelanceEtape')
    for ligne in _lignes(Etape, 11, _ORDRE_11).iterator():
        ligne.actif = False
        ligne.save()


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0133_gabarit_contact_v4'),
    ]

    operations = [
        migrations.RunPython(vers_v4, vers_v3),
    ]
