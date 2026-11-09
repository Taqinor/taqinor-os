# flake8: noqa  (sonde d'audit de parcours PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""K69 — l'ajout manuel d'un équipement depuis la fiche chantier (POST /sav/equipements/, corps de
InstallationDetail.addEquipement : date_pose = date_pose_reelle) contourne l'écrivain unique du parc
(`assurer_equipement_chantier`, ACHT46). Chantier : pose réelle à J-65, réception à J-60, nomenclature 1 onduleur ;
réception par `changer_statut_chantier` -> placeholder sans série daté de la réception. Puis POST SN-9.
Témoin : sur un 2e chantier identique, `assurer_equipement_chantier` (chemin terrain ACHT47) remplit le placeholder.
Puis correction de la date de réception (`recaler_garanties_chantier`) : SN-9 suit-il ?"""
SONDE = {"constat": "C-ACSV-069", "sha": "f57951e87",
         "attendu": "repro si 2 onduleurs au parc (placeholder sans série + SN-9) et SN-9 daté de la pose réelle ; "
                    "témoin : 1 équipement « rempli », daté de la réception",
         "modeles": ["sav.Equipement", "installations.Installation"]}


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
    from apps.sav.models import Equipement
    from apps.sav.services import assurer_equipement_chantier, recaler_garanties_chantier
    from apps.stock.models import Produit
    H = {'HTTP_HOST': 'localhost'}
    today = timezone.localdate()
    pose, rec = today - timedelta(days=65), today - timedelta(days=60)
    co = Company.objects.create(nom='Sonde ACSV 069', slug='sonde-acsv-069')
    u = get_user_model().objects.create_user(username='sonde-acsv-069', password='x', company=co,
                                             role_legacy='admin')
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='K69', email='acsv069@example.invalid')
    po = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-ACSV-069', prix_vente=Decimal('5000'),
                                garantie_mois=60)

    def chantier(ref):
        inst = Installation.objects.create(
            company=co, reference=ref, client=cl, statut=Installation.Statut.INSTALLE, created_by=u,
            date_pose_reelle=pose, date_reception=rec,
            bom=[{'produit_id': po.pk, 'designation': 'Onduleur', 'quantite': 1}])
        try:
            isvc.changer_statut_chantier(inst, Installation.Statut.RECEPTIONNE, u)
            g = 'ok'
        except isvc.TransitionRefusee as exc:
            g = 'refus gardes : ' + str(getattr(exc, 'raisons', exc))[:120]
            inst.refresh_from_db()
            isvc.changer_statut_chantier(inst, Installation.Statut.RECEPTIONNE, u, verifier_gates=False)
        inst.refresh_from_db()
        return inst, g

    def parc(inst):
        return list(Equipement.objects.filter(installation=inst, produit=po).order_by('pk')
                    .values_list('numero_serie', 'date_pose', 'statut'))
    iA, gA = chantier('CHT-ACSV-069-A')
    apres_sweep = parc(iA)
    r = api.post('/api/django/sav/equipements/', {'produit': po.pk, 'installation': iA.pk, 'numero_serie': 'SN-9',
                                                 'date_pose': str(pose)}, format='json', **H)
    apres_post = parc(iA)
    nouvelle = rec - timedelta(days=2)
    recales = recaler_garanties_chantier(company=co, installation=iA, ancienne_date=rec, nouvelle_date=nouvelle)
    apres_recalage = parc(iA)
    iB, gB = chantier('CHT-ACSV-069-B')
    statut_b, _ = assurer_equipement_chantier(company=co, installation=iB, produit=po, numero_serie='SN-9B',
                                              quantite_ligne=1, date_pose=pose, created_by=u)
    obs = {'transition_A': gA, 'transition_B': gB, 'pose_reelle': str(pose), 'reception': str(rec),
           'A_apres_sweep': apres_sweep, 'post_http': r.status_code, 'A_apres_post': apres_post,
           'recalage_reception': {'nouvelle': str(nouvelle), 'recales': recales, 'parc': apres_recalage},
           'temoin_B': {'statut': statut_b, 'parc': parc(iB)}}
    print(obs)
    temoin = statut_b == 'rempli' and len(obs['temoin_B']['parc']) == 1
    defaut = r.status_code == 201 and len(apres_post) == 2 and any(s == 'SN-9' and d == pose for s, d, _ in apres_post)
    obs.update({'temoin_ok': temoin, 'repro': bool(temoin and defaut)})
    return obs
