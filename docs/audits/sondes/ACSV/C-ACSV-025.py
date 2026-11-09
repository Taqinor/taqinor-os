# flake8: noqa  (sonde d'audit de parcours PA5, rejouable par scripts/sonde.py — METHODE §C.4)
"""K25 — « Enregistrer la mise en service » (POST chantiers/<id>/mise-en-service/) écrit le statut HÉRITÉ
`mise_en_service` (canonique = réceptionné) : le chantier sort des lecteurs à valeur brute —
`installations.selectors.chantiers_receptionnes` (KPI taux d'attache, `sav.selectors.taux_attache`) et
`reporting.integrity.chantiers_receptionnes_sans_parc`. (T) témoin : le même chantier passé par PATCH
{statut: receptionne} est compté. Fiche IEC passée créée pour franchir le gate tests."""
SONDE = {"constat": "C-ACSV-025", "sha": "f57951e87",
         "attendu": "repro si R : statut stocké mise_en_service, date_reception posée, absent de "
                    "chantiers_receptionnes et de taux_attache.total ; T (PATCH receptionne) compté",
         "modeles": ["installations.Installation", "installations.CommissioningRecord", "sav.Equipement"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation, CommissioningRecord
    from apps.installations.services import ESSAIS_RECETTE, ensure_commissioning_record
    from apps.installations.selectors import chantiers_receptionnes
    from apps.sav.selectors import taux_attache
    from apps.reporting.integrity import chantiers_receptionnes_sans_parc

    H = {'HTTP_HOST': 'localhost'}
    B = '/api/django/installations'
    co = Company.objects.create(nom='Sonde ACSV 025', slug='sonde-acsv-025')
    u = get_user_model().objects.create_user(username='sonde_acsv_025', password='x',
                                             role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='A025', email='a025@example.invalid')

    def mk(ref):
        inst = Installation.objects.create(company=co, reference=ref, client=cl, statut='installe',
                                           type_installation='residentiel')
        rec = ensure_commissioning_record(inst, u)
        for champ in ESSAIS_RECETTE:
            setattr(rec, champ, True)
        rec.resultat = CommissioningRecord.Resultat.CONFORME
        rec.save()
        return Installation.objects.get(pk=inst.pk)

    obs = {}
    iR = mk('CHT-A025-R')
    rR = api.post(f'{B}/chantiers/{iR.id}/mise-en-service/',
                  {'date_mise_en_service': str(timezone.localdate()), 'mes_tension': 230}, format='json', **H)
    obs['R_http'] = rR.status_code
    obs['R_detail'] = None if rR.status_code < 400 else str(rR.content[:300], 'utf-8', 'replace')
    iR.refresh_from_db()
    obs['R_statut'] = iR.statut
    obs['R_canon'] = Installation.canonical_statut(iR.statut)
    obs['R_date_reception'] = str(iR.date_reception)
    iT = mk('CHT-A025-T')
    rT = api.patch(f'{B}/chantiers/{iT.id}/', {'statut': 'receptionne'}, format='json', **H)
    obs['T_http'] = rT.status_code
    obs['T_detail'] = None if rT.status_code < 400 else str(rT.content[:300], 'utf-8', 'replace')
    iT.refresh_from_db()
    obs['T_statut'] = iT.statut
    ids = [x[0] for x in chantiers_receptionnes(co)]
    obs['receptionnes_ids'] = {'R': iR.id in ids, 'T': iT.id in ids}
    obs['taux_attache_total'] = taux_attache(co)['total']
    sans = chantiers_receptionnes_sans_parc(co)
    obs['integrite_voit'] = {'R': iR.id in sans, 'T': iT.id in sans}
    obs['equipements'] = {'R': iR.equipements.count() if hasattr(iR, 'equipements') else None,
                          'T': iT.equipements.count() if hasattr(iT, 'equipements') else None}
    print(obs)
    obs['repro'] = bool(rR.status_code == 200 and iR.statut == 'mise_en_service' and obs['R_canon'] == 'receptionne'
                        and not obs['receptionnes_ids']['R'] and rT.status_code == 200
                        and obs['receptionnes_ids']['T'] and obs['taux_attache_total'] == 1)
    return obs
