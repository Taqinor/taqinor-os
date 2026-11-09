# flake8: noqa  (sonde d'audit de parcours PA2 « Conception », rejouable par scripts/sonde.py — METHODE §C.4)
"""K41 — abandon de la révision V2 (suppression du brouillon, ou archivage) : `abandonner_revision` réactive la V1
sans aucun événement ; le seul abonné calepinage (`receivers.relier_calepinage_au_devis_revise`, ACAL92) n'écoute
que `devis_revise`. (a) DELETE V2 → `Calepinage.devis` SET_NULL : C sans devis, V1 sans calepinage, et l'ouverture
de la 3D de V1 ADOPTE C (avec la retouche faite pour la V2 abandonnée). (b) PATCH V2 is_active=false → C reste lié à
V2 archivée (verrouillé), V1 n'a plus de calepinage et sa 3D en CRÉE un second.
Vraies routes : generer-devis, reviser, DELETE devis, PATCH devis ; on_commit exécutés (captureOnCommitCallbacks).
Raccourci : l'acceptation de V1 est posée par update() (le geste d'acceptation n'est pas sous audit)."""
SONDE = {"constat": "C-ACON-041", "sha": "33cba7f5d",
         "attendu": "repro si (a) après DELETE V2 : C.devis_id None, calepinage_du_devis(V1) None, adoption de C "
                    "(empreinte retouchée != V1) ; (b) après archivage V2 : C lié à V2, verrouillé, V1 sans "
                    "calepinage et sa 3D crée un 2e calepinage ; témoin : après reviser, C lié à V2",
         "modeles": ["ventes.Devis", "calepinage.Calepinage", "calepinage.CalepinageVersion"]}


def sonde(ctx):
    from io import StringIO
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.test import TestCase
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import AccessToken
    from apps.calepinage.models import Calepinage
    from apps.calepinage.selectors import calepinage_du_devis
    from apps.calepinage.services.creation import adopter_ou_creer_pour_devis
    from apps.calepinage.services.verrou import est_verrouille
    from apps.crm.models import Lead
    from apps.roles.models import Role
    from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
    from apps.ventes.models import Devis
    from apps.ventes.domain.geometrie import layout_hash
    from authentication.models import Company
    User = get_user_model()
    co = Company.objects.create(nom='SONDE ACON 041', slug='sonde-acon-041')
    call_command('seed_catalogue', company_slug=co.slug, stdout=StringIO())
    role = Role.objects.create(company=co, nom='Directeur', permissions=list(DIRECTEUR_PERMISSIONS))
    u = User.objects.create_user(username='sonde_acon_041', password='x', company=co,
                                 role=role, role_legacy='responsable')
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(u))
    B = '/api/django/ventes/devis/'

    def chaine(tag):
        lead = Lead.objects.create(company=co, nom='Villa', prenom=tag, email='acon041-%s@example.test' % tag)
        lay = {'scenario': 'reseau', 'panelWatt': 550, 'nonce': tag,
               'result': {'panels': 12, 'kwc': 6.6, 'annualKwh': 10000, 'savings': 8000}}
        cal = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='Toit ' + tag, roof_layout=lay,
                                        layout_hash=layout_hash(lay))
        r = api.post('/api/django/calepinage/calepinages/%s/generer-devis/' % cal.pk, {}, format='json')
        assert r.status_code in (200, 201), (r.status_code, r.data)
        v1 = r.data['devis']
        Devis.objects.filter(pk=v1).update(statut='accepte')   # raccourci : V1 acceptée
        with TestCase.captureOnCommitCallbacks(execute=True):
            rv = api.post(B + '%s/reviser/' % v1, {}, format='json')
        assert rv.status_code in (200, 201), (rv.status_code, rv.data)
        v2 = rv.data['id']
        cal.refresh_from_db()
        temoin = {'C.devis==V2': cal.devis_id == v2, 'versions': list(cal.versions.values_list('libelle', flat=True))
                  if hasattr(cal, 'versions') else None}
        # retouche de 2 panneaux pour la V2 (écriture directe : l'atelier n'est pas sous audit)
        lay2 = dict(lay, result=dict(lay['result'], panels=14, kwc=7.7), retouche='V2')
        Calepinage.objects.filter(pk=cal.pk).update(roof_layout=lay2, layout_hash=layout_hash(lay2))
        return lead, cal, v1, v2, temoin

    obs = {}
    # (a) suppression du brouillon V2
    lead, cal, v1, v2, t = chaine('a')
    with TestCase.captureOnCommitCallbacks(execute=True):
        rd = api.delete(B + '%s/' % v2)
    cal.refresh_from_db()
    V1 = Devis.objects.get(pk=v1)
    cal_v1 = calepinage_du_devis(v1, co)
    adopte, origine = adopter_ou_creer_pour_devis(v1, co, user=u)
    obs['a'] = {'temoin': t, 'delete_http': rd.status_code, 'V1_active': V1.is_active, 'V1_statut': V1.statut,
                'C.devis_id_apres': cal.devis_id, 'calepinage_du_devis(V1)': getattr(cal_v1, 'pk', None),
                'ouverture_3D_V1': origine, 'adopte_est_C': adopte.pk == cal.pk,
                'empreinte_C_retouchee_vs_V1': [adopte.layout_hash[:10], (V1.layout_hash or '')[:10]]}
    # (b) archivage de V2
    lead, cal, v1, v2, t = chaine('b')
    with TestCase.captureOnCommitCallbacks(execute=True):
        rp = api.patch(B + '%s/' % v2, {'is_active': False}, format='json')
    cal.refresh_from_db()
    V1 = Devis.objects.get(pk=v1)
    cal_v1 = calepinage_du_devis(v1, co)
    verrou = est_verrouille(cal)
    nouveau, origine_b = adopter_ou_creer_pour_devis(v1, co, user=u)
    obs['b'] = {'temoin': t, 'patch_http': rp.status_code, 'patch_detail': None if rp.status_code < 400 else str(rp.data)[:160],
                'V1_active': V1.is_active, 'C.devis_id==V2': cal.devis_id == v2, 'C_verrouille': verrou,
                'calepinage_du_devis(V1)': getattr(cal_v1, 'pk', None), 'ouverture_3D_V1': origine_b,
                'calepinages_du_lead': Calepinage.objects.filter(company=co, lead_id=lead.pk).count()}
    print(obs)
    a, b = obs['a'], obs['b']
    temoin_ok = a['temoin']['C.devis==V2'] and b['temoin']['C.devis==V2']
    rep_a = (a['delete_http'] == 204 and a['V1_active'] and a['C.devis_id_apres'] is None
             and a['calepinage_du_devis(V1)'] is None and a['ouverture_3D_V1'] == 'adopte' and a['adopte_est_C'])
    rep_b = (b['patch_http'] == 200 and b['V1_active'] and b['C.devis_id==V2'] and b['C_verrouille']
             and b['calepinage_du_devis(V1)'] is None and b['ouverture_3D_V1'] == 'cree'
             and b['calepinages_du_lead'] == 2)
    obs.update(temoin_ok=temoin_ok, repro_a=rep_a, repro_b=rep_b, repro=bool(temoin_ok and (rep_a or rep_b)))
    return obs
