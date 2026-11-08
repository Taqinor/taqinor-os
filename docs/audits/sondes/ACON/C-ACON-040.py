# flake8: noqa  (sonde d'audit de parcours PA2 « Conception », rejouable par scripts/sonde.py — METHODE §C.4)
"""K40 — « Générer le devis » (calepinage) et « from-layout » (ventes) sur un lead INDUSTRIEL / COMMERCIAL :
le devis naît `mode_installation='residentiel'` (codé en dur, creation_calepinage.py::build_devis_from_layout) et
l'étude reçoit `economies_annuelles` / `production_annuelle` du bloc `result` du layout — alors que
`etude_schema.cles_etude_du_layout` (CIQ117) n'écrit RIEN pour un marché C&I. Seul l'agricole est refusé (ACAL89).
Témoin : lead agricole → refus nommé `type_installation` (422 service, 409 à la vue — ENF11) ; `cles_etude_du_layout('industriel', result) == {}`.
Vraies routes : POST calepinage/calepinages/<id>/generer-devis/ et POST ventes/devis/from-layout/."""
SONDE = {"constat": "C-ACON-040", "sha": "33cba7f5d",
         "attendu": "repro si un lead industriel/commercial obtient 201 sur generer-devis ET from-layout avec "
                    "mode_installation='residentiel' et etude_params.economies_annuelles == result.savings ; "
                    "témoin agricole refusé nommé type_installation (409 vue) ; from-layout agricole observé en plus",
         "modeles": ["ventes.Devis", "calepinage.Calepinage", "crm.Lead"]}


def sonde(ctx):
    from io import StringIO
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import AccessToken
    from apps.calepinage.models import Calepinage
    from apps.crm.models import Lead
    from apps.roles.models import Role
    from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
    from apps.ventes.models import Devis
    from apps.ventes.domain.geometrie import layout_hash
    from apps.ventes.domain.etude_schema import cles_etude_du_layout
    from authentication.models import Company
    User = get_user_model()
    co = Company.objects.create(nom='SONDE ACON 040', slug='sonde-acon-040')
    call_command('seed_catalogue', company_slug=co.slug, stdout=StringIO())
    role = Role.objects.create(company=co, nom='Directeur', permissions=list(DIRECTEUR_PERMISSIONS))
    u = User.objects.create_user(username='sonde_acon_040', password='x', company=co,
                                 role=role, role_legacy='responsable')
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(u))
    SAVINGS, KWH = 41234, 98765

    def layout(n):
        # 60 modules 710 W ≈ 42,6 kWc (toit d'usine), économies de l'outil de toiture dans `result`
        return {'scenario': 'reseau', 'panelWatt': 710, 'nonce': n,
                'result': {'panels': 60, 'kwc': 42.6, 'annualKwh': KWH, 'savings': SAVINGS}}

    obs = {'temoin_cles_ci': cles_etude_du_layout('industriel', {'annualKwh': KWH, 'savings': SAVINGS}),
           'temoin_cles_resid': cles_etude_du_layout('residentiel', {'annualKwh': KWH, 'savings': SAVINGS})}

    def lu(did):
        d = Devis.objects.get(pk=did)
        ep = d.etude_params or {}
        return {'mode': d.mode_installation, 'lead_type': d.lead.type_installation if d.lead_id else None,
                'economies_annuelles': ep.get('economies_annuelles'),
                'production_annuelle': ep.get('production_annuelle'),
                'production_source': ep.get('production_source'), 'ttc': str(d.total_ttc)}

    for marche in ('industriel', 'commercial', 'agricole'):
        l_cal = Lead.objects.create(company=co, nom='Usine', prenom=marche + '-cal',
                                    email='acon040-%s-c@example.test' % marche, type_installation=marche)
        l_fl = Lead.objects.create(company=co, nom='Usine', prenom=marche + '-fl',
                                   email='acon040-%s-f@example.test' % marche, type_installation=marche)
        lay = layout(marche)
        cal = Calepinage.objects.create(company=co, lead_id=l_cal.pk, titre='Toit ' + marche,
                                        roof_layout=lay, layout_hash=layout_hash(lay))
        r1 = api.post('/api/django/calepinage/calepinages/%s/generer-devis/' % cal.pk, {}, format='json')
        r2 = api.post('/api/django/ventes/devis/from-layout/', {'layout': layout(marche + '2'), 'lead': l_fl.pk},
                      format='json')
        ent = {}
        for nom, r in (('generer_devis', r1), ('from_layout', r2)):
            d = getattr(r, 'data', None) or {}
            did = None
            if isinstance(d, dict):
                did = d.get('id') or (d.get('devis') if isinstance(d.get('devis'), int) else None)
            ent[nom] = {'http': r.status_code,
                        'devis': lu(did) if (r.status_code < 300 and did) else str(d)[:200]}
        obs[marche] = ent
    print(obs)

    def defaut(ent):
        x = ent.get('devis')
        return (ent['http'] in (200, 201) and isinstance(x, dict) and x['mode'] == 'residentiel'
                and x['economies_annuelles'] == SAVINGS)

    ag = obs['agricole']['generer_devis']
    temoin_ok = obs['temoin_cles_ci'] == {} and ag['http'] in (409, 422) and 'type_installation' in str(ag['devis'])
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and all(defaut(obs[m][p]) for m in ('industriel', 'commercial')
                                          for p in ('generer_devis', 'from_layout')))
    return obs
