# flake8: noqa  (sonde d'audit de parcours PA5, rejouable par scripts/sonde.py — METHODE §C.4)
"""K24 — (R) fiche de recette IEC 62446-1 « conforme » d'un chantier réceptionné dont le PV/BL est SIGNÉ
(`signe_le` posé) : PATCH recettes-commissioning/<id>/ {isolement_ok: false} accepté, résultat recalculé
« non conforme », et le résumé injecté au dossier de remise (`documents.builders._recette_summary`)
change. (T) jumeau pompage : PATCH recettes-pompage/<id>/ sur chantier agricole signé → 400 « verrouillee ».
Vraies routes (PATCH, écran « Modifier la fiche de recette »)."""
SONDE = {"constat": "C-ACSV-024", "sha": "f57951e87",
         "attendu": "repro si T = 400 (verrouillee) et R : PATCH 200, resultat conforme -> non_conforme, "
                    "_recette_summary['resultat'] change, chantier toujours réceptionné",
         "modeles": ["installations.CommissioningRecord", "installations.RecettePompage",
                     "installations.Installation"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation, CommissioningRecord, RecettePompage
    from apps.installations.services import ESSAIS_RECETTE, ensure_commissioning_record
    from apps.documents.builders import _recette_summary

    H = {'HTTP_HOST': 'localhost'}
    B = '/api/django/installations'
    co = Company.objects.create(nom='Sonde ACSV 024', slug='sonde-acsv-024')
    u = get_user_model().objects.create_user(username='sonde_acsv_024', password='x',
                                             role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='A024', email='a024@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-A024', client=cl, statut='receptionne',
                                       type_installation='residentiel', signe_le=timezone.now(),
                                       date_reception=timezone.localdate())
    rec = ensure_commissioning_record(inst, u)
    for champ in ESSAIS_RECETTE:
        setattr(rec, champ, True)
    rec.isolement_mohm = 50
    rec.resultat = CommissioningRecord.Resultat.CONFORME
    rec.save()
    inst = Installation.objects.get(pk=inst.pk)
    obs = {'avant': rec.resultat, 'summary_avant': (_recette_summary(inst) or {}).get('resultat')}
    r = api.patch(f'{B}/recettes-commissioning/{rec.id}/', {'isolement_ok': False, 'isolement_mohm': 0.2},
                  format='json', **H)
    obs['R_patch'] = r.status_code
    obs['R_detail'] = None if r.status_code < 400 else str(r.content[:200], 'utf-8', 'replace')
    rec.refresh_from_db()
    obs['apres'] = rec.resultat
    inst = Installation.objects.get(pk=inst.pk)
    obs['summary_apres'] = (_recette_summary(inst) or {}).get('resultat')
    obs['statut_chantier'] = inst.statut
    # T — jumeau pompage
    try:
        instA = Installation.objects.create(company=co, reference='CHT-A024-AG', client=cl,
                                            statut='receptionne', type_installation='agricole',
                                            signe_le=timezone.now())
        rp = RecettePompage.objects.create(company=co, installation=instA)
        rT = api.patch(f'{B}/recettes-pompage/{rp.id}/', {'observations': 'modif après PV'}, format='json', **H)
        obs['T_patch'] = rT.status_code
        obs['T_detail'] = str(rT.content[:160], 'utf-8', 'replace')
    except Exception as exc:  # noqa
        obs['T_patch'] = f'err {exc!r}'[:120]
    print(obs)
    obs['repro'] = bool(obs.get('T_patch') == 400 and r.status_code == 200 and obs['avant'] == 'conforme'
                        and obs['apres'] != 'conforme' and obs['summary_avant'] != obs['summary_apres']
                        and inst.statut == 'receptionne')
    return obs
