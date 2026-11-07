# flake8: noqa  (sonde d'audit de parcours PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""K68 — portée « équipe » d'un Technicien (SCOPE_TEAM) sur /sav/equipements/ : filtre `created_by` seul.
Un Technicien responsable (superviseur) réceptionne CH-1 (nomenclature : onduleur + panneau) par
`changer_statut_chantier` -> le balayage crée le parc avec created_by = lui. Son Technicien (supervisor = lui) est
le technicien responsable de CH-1 : GET /installations/chantiers/<CH-1>/ et
GET /sav/equipements/?installation=<CH-1>. Témoin : le responsable voit les 2 équipements."""
SONDE = {"constat": "C-ACSV-068", "sha": "f57951e87",
         "attendu": "repro si le Technicien voit le chantier (200) mais 0 équipement au parc, quand son "
                    "responsable en voit 2",
         "modeles": ["sav.Equipement", "installations.Installation"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.installations import services as isvc
    from apps.roles.models import Role
    from apps.roles.permissions_registre import TECHNICIEN_PERMISSIONS, TECHNICIEN_RESP_PERMISSIONS
    from apps.sav.models import Equipement
    from apps.stock.models import Produit
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ACSV 068', slug='sonde-acsv-068')
    U = get_user_model()
    r_resp = Role.objects.create(company=co, nom='Technicien responsable',
                                 permissions=list(TECHNICIEN_RESP_PERMISSIONS), est_systeme=True)
    r_tech = Role.objects.create(company=co, nom='Technicien', permissions=list(TECHNICIEN_PERMISSIONS),
                                 est_systeme=True)
    resp = U.objects.create_user(username='sonde-acsv-068-resp', password='x', company=co, role=r_resp)
    tech = U.objects.create_user(username='sonde-acsv-068-tech', password='x', company=co, role=r_tech,
                                 supervisor=resp)
    cl = Client.objects.create(company=co, nom='Client', prenom='K68', email='acsv068@example.invalid')
    po = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-ACSV-068-O', prix_vente=Decimal('5000'),
                                garantie_mois=60)
    pp = Produit.objects.create(company=co, nom='Panneau', sku='SONDE-ACSV-068-P', prix_vente=Decimal('900'),
                                garantie_mois=120)
    inst = Installation.objects.create(
        company=co, reference='CHT-ACSV-068', client=cl, statut=Installation.Statut.INSTALLE, created_by=resp,
        technicien_responsable=tech,
        bom=[{'produit_id': po.pk, 'designation': 'Onduleur', 'quantite': 1},
             {'produit_id': pp.pk, 'designation': 'Panneau', 'quantite': 1}])
    try:
        isvc.changer_statut_chantier(inst, Installation.Statut.RECEPTIONNE, resp)
        gardes = 'ok'
    except isvc.TransitionRefusee as exc:
        gardes = 'refus gardes : ' + str(getattr(exc, 'raisons', exc))[:160]
        inst.refresh_from_db()
        isvc.changer_statut_chantier(inst, Installation.Statut.RECEPTIONNE, resp, verifier_gates=False)
    parc = list(Equipement.objects.filter(installation=inst).values_list('produit__nom', 'created_by__username'))

    def vue(user):
        api = APIClient()
        api.force_authenticate(user)
        rc = api.get(f'/api/django/installations/chantiers/{inst.pk}/', **H)
        re_ = api.get('/api/django/sav/equipements/', {'installation': inst.pk}, **H)
        corps = re_.data.get('results', re_.data) if re_.status_code == 200 else []
        return {'chantier_http': rc.status_code, 'equipements_http': re_.status_code, 'nb_equipements': len(corps)}
    obs = {'transition': gardes, 'parc_cree': parc, 'responsable': vue(resp), 'technicien': vue(tech)}
    print(obs)
    obs['repro'] = bool(obs['responsable']['nb_equipements'] == 2 and obs['technicien']['chantier_http'] == 200
                        and obs['technicien']['nb_equipements'] == 0)
    return obs
