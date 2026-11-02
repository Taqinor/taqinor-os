"""CADV23 — le gabarit `contact` passe du protocole v3 (11 barreaux, 14 jours)
au protocole v4 (5 appels, 3 WhatsApp, 7 jours), D-CADV-1.

`seed_cadence` ne retouche jamais un barreau existant : seule une migration de
données change la production. Pour chaque société, les barreaux 5 à 8 passent
aux valeurs v4 et 9 à 11 sont désactivés (jamais supprimés) — SEULEMENT si la
ligne porte encore exactement les valeurs v3 : un barreau modifié par la
société reste intact. Les ordres 1-4 ne bougent pas, les touches déjà posées
(`RelanceEtape`) non plus. Idempotent : la 2e application ne retrouve plus
aucune ligne aux valeurs v3 (le critère inclut `actif=True`).
"""
import datetime

from django.db import migrations, models

T = datetime.time

# ordre -> (valeurs v3, valeurs v4). `cles` : clés v3 tolérées (une ligne
# seedée avant CAD67 pouvait porter une clé vide).
_V3 = {
    5: dict(canal='whatsapp', delai_jours=1, delai_minutes=0,
            heure_cible=T(9, 30), dimanche_ok=False, actif=True,
            libelle='WhatsApp de valeur', template_cle='valeur_j1'),
    6: dict(canal='appel', delai_jours=2, delai_minutes=0,
            heure_cible=T(18, 0), dimanche_ok=False, actif=True,
            libelle='Appel 4 (répondeur)', template_cle='repondeur'),
    7: dict(canal='whatsapp', delai_jours=3, delai_minutes=0,
            heure_cible=T(9, 30), dimanche_ok=False, actif=True,
            libelle='Vocal', template_cle='vocal_j3'),
    8: dict(canal='appel', delai_jours=5, delai_minutes=0,
            heure_cible=T(10, 30), dimanche_ok=True, actif=True,
            libelle='Appel 5 (dimanche)', template_cle='appel_dimanche'),
    9: dict(canal='whatsapp', delai_jours=7, delai_minutes=0,
            heure_cible=T(9, 30), dimanche_ok=False, actif=True,
            libelle='« Je classe ? »', template_cle='je_classe_j7'),
    10: dict(canal='appel', delai_jours=10, delai_minutes=0,
             heure_cible=T(15, 0), dimanche_ok=False, actif=True,
             libelle='Appel 6 (dernier)', template_cle='appel_dernier'),
    11: dict(canal='whatsapp', delai_jours=14, delai_minutes=0,
             heure_cible=T(9, 30), dimanche_ok=False, actif=True,
             libelle='Clôture', template_cle='cloture_j14'),
}
_V4 = {
    5: dict(canal='appel', delai_jours=2, delai_minutes=0,
            heure_cible=T(16, 0), dimanche_ok=False, actif=True,
            libelle='Appel 4 (répondeur)', template_cle='repondeur'),
    6: dict(canal='whatsapp', delai_jours=2, delai_minutes=0,
            heure_cible=T(17, 45), dimanche_ok=False, actif=True,
            libelle='WhatsApp de valeur', template_cle='valeur_j1'),
    7: dict(canal='appel', delai_jours=4, delai_minutes=0,
            heure_cible=T(11, 0), dimanche_ok=False, actif=True,
            libelle='Appel 5 (dernier)', template_cle='appel_dernier'),
    8: dict(canal='whatsapp', delai_jours=7, delai_minutes=0,
            heure_cible=T(12, 0), dimanche_ok=False, actif=True,
            libelle='« Je classe ? »', template_cle='je_classe_j7'),
    9: dict(_V3[9], actif=False),
    10: dict(_V3[10], actif=False),
    11: dict(_V3[11], actif=False),
}


def _lignes(Etape, ordre, valeurs):
    """Lignes `contact` de cet ordre portant exactement `valeurs`. Deux
    tolérances : la clé de message peut être vide (seed d'avant CAD67) et
    l'heure cible peut être nulle (seed d'avant CAD25, 21/09) — une valeur
    jamais saisie n'est pas une personnalisation."""
    filtre = {k: v for k, v in valeurs.items()
              if k not in ('template_cle', 'heure_cible')}
    qs = Etape.objects.filter(cadence='contact', ordre=ordre, **filtre)
    heures = [valeurs['heure_cible']]
    qs = qs.filter(template_cle__in=[valeurs['template_cle'], ''])
    if valeurs['heure_cible'] is None:
        return qs.filter(heure_cible__isnull=True)
    return qs.filter(models.Q(heure_cible__in=heures)
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


def vers_v3(apps, schema_editor):
    """Marche arrière : valeurs v3 des SEULS barreaux restés à v4 (un barreau
    modifié depuis reste intact)."""
    _bascule(apps, _V4, _V3)


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0132_messagetemplate_cles_reactivation'),
    ]

    operations = [
        migrations.RunPython(vers_v4, vers_v3),
    ]
