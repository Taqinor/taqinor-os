# flake8: noqa  (sonde d'audit de parcours PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""K65 — garantie de l'appareil posé en remplacement (D-ASAV-1) écrasée par un recalcul ultérieur.
(R) chantier réceptionné il y a 400 j (nomenclature : 1 onduleur 60 mois), onduleur SN-OLD daté de la réception.
Remplacement par la vraie route `pieces-retirees` (serie_neuve) -> neuf daté d'aujourd'hui, fin = aujourd'hui +
60 mois. Puis chantier Réceptionné -> Installé -> Réceptionné par `changer_statut_chantier` (gardes d'abord ;
repli verifier_gates=False noté si refusé). Attendu : neuf inchangé ; repro : neuf recalé sur la date de réception.
(P) plancher D-ASAV-1 : ancien produit 120 mois, neuf produit 12 mois -> fin du neuf = reste de l'ancien. Puis
« Corriger » la date de pose d'un jour (PATCH /sav/equipements/<id>/). Attendu : plancher conservé ; repro :
fin = pose + 12 mois."""
SONDE = {"constat": "C-ACSV-065", "sha": "f57951e87",
         "attendu": "repro si R : date_pose du neuf ramenée à la réception (fin -400 j) ; ou P : fin du neuf < reste "
                    "de l'ancien après PATCH date_pose",
         "modeles": ["sav.Equipement", "sav.PieceRetiree", "installations.Installation"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.installations import services as isvc
    from apps.sav.models import Equipement, Ticket
    from apps.stock.models import Produit
    H = {'HTTP_HOST': 'localhost'}
    today = timezone.localdate()
    rec = today - timedelta(days=400)
    co = Company.objects.create(nom='Sonde ACSV 065', slug='sonde-acsv-065')
    u = get_user_model().objects.create_user(username='sonde-acsv-065', password='x', company=co,
                                             role_legacy='admin')
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='K65', email='acsv065@example.invalid')

    def chantier(ref, prod):
        return Installation.objects.create(
            company=co, reference=ref, client=cl, statut=Installation.Statut.RECEPTIONNE, date_reception=rec,
            date_pose_reelle=rec, bom=[{'produit_id': prod.pk, 'designation': prod.nom, 'quantite': 1}])

    def remplacer(inst, prod_old, serie_old, serie_new, prod_new=None):
        old = Equipement.objects.create(company=co, produit=prod_old, installation=inst, numero_serie=serie_old,
                                        date_pose=rec, created_by=u)
        old.recompute_garanties()
        old.save()
        t = Ticket.objects.create(company=co, reference=f'SAV-{serie_old}', client=cl, installation=inst,
                                  equipement=old, type=Ticket.Type.CORRECTIF, created_by=u)
        corps = {'produit': prod_old.pk, 'numero_serie': serie_old, 'serie_neuve': serie_new,
                 'destination': 'rebut', 'quantite': 1}
        if prod_new is not None:
            corps['produit_neuf'] = prod_new.pk
        r = api.post(f'/api/django/sav/tickets/{t.pk}/pieces-retirees/', corps, format='json', **H)
        neuf = Equipement.objects.filter(company=co, numero_serie=serie_new).first()
        return r.status_code, (str(r.data)[:200] if r.status_code >= 400 else None), old, neuf

    obs = {'reception': str(rec)}
    # (R)
    pR = Produit.objects.create(company=co, nom='Onduleur R', sku='SONDE-ACSV-065-R', prix_vente=Decimal('5000'),
                                garantie_mois=60)
    iR = chantier('CHT-ACSV-065-R', pR)
    http, det, oldR, neufR = remplacer(iR, pR, 'SN-065-OLD', 'SN-065-NEW')
    obs['R_remplacement'] = (http, det)
    if neufR is None:
        return {'repro': False, 'obs': obs}
    avant = (str(neufR.date_pose), str(neufR.date_fin_garantie))
    gardes = []
    for cible in (Installation.Statut.INSTALLE, Installation.Statut.RECEPTIONNE):
        iR.refresh_from_db()
        try:
            isvc.changer_statut_chantier(iR, cible, u)
            gardes.append((cible, 'ok'))
        except isvc.TransitionRefusee as exc:
            gardes.append((cible, 'refus gardes : ' + str(getattr(exc, 'raisons', exc))[:160]))
            isvc.changer_statut_chantier(iR, cible, u, verifier_gates=False)
    neufR.refresh_from_db()
    iR.refresh_from_db()
    obs['R'] = {'neuf_avant': avant, 'neuf_apres': (str(neufR.date_pose), str(neufR.date_fin_garantie)),
                'transitions': gardes, 'statut_final': iR.statut, 'date_reception': str(iR.date_reception),
                'parc': list(Equipement.objects.filter(installation=iR).values_list('numero_serie', 'date_pose'))}
    # (P)
    pOld = Produit.objects.create(company=co, nom='Panneau 120', sku='SONDE-ACSV-065-P1', prix_vente=Decimal('900'),
                                  garantie_mois=120)
    pNew = Produit.objects.create(company=co, nom='Panneau 12', sku='SONDE-ACSV-065-P2', prix_vente=Decimal('900'),
                                  garantie_mois=12)
    iP = chantier('CHT-ACSV-065-P', pOld)
    httpP, detP, oldP, neufP = remplacer(iP, pOld, 'SN-065-P-OLD', 'SN-065-P-NEW', prod_new=pNew)
    obs['P_remplacement'] = (httpP, detP)
    if neufP is not None:
        reste = oldP.date_fin_garantie_effective
        apres_rempl = str(neufP.date_fin_garantie)
        rp = api.patch(f'/api/django/sav/equipements/{neufP.pk}/',
                       {'date_pose': str(neufP.date_pose - timedelta(days=1))}, format='json', **H)
        neufP.refresh_from_db()
        obs['P'] = {'reste_ancien': str(reste), 'fin_neuf_apres_remplacement': apres_rempl, 'patch': rp.status_code,
                    'fin_neuf_apres_patch': str(neufP.date_fin_garantie),
                    'fin_effective_apres_patch': str(neufP.date_fin_garantie_effective)}
    print(obs)
    repro_r = obs['R']['neuf_apres'][0] == str(rec) and avant[0] != str(rec)
    repro_p = 'P' in obs and obs['P']['fin_neuf_apres_remplacement'] == obs['P']['reste_ancien'] \
        and obs['P']['fin_effective_apres_patch'] < obs['P']['reste_ancien']
    obs.update({'repro_R': repro_r, 'repro_P': bool(repro_p), 'repro': bool(repro_r or repro_p)})
    return obs
