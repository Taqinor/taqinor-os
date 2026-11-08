# flake8: noqa  (sonde d'audit de parcours PA2 « Conception », rejouable par scripts/sonde.py — METHODE §C.4)
"""K04 — L'onglet « Projet » de l'atelier réimporte un fichier de projet en le rattachant au lead du calepinage
OUVERT (`POST calepinages/import-projet/ {projet, lead}`). `export_projet.importer_projet` appelle
`creation.creer_pour_lead` directement (ni verrou, ni relecture de l'ouvert) : un SECOND calepinage ouvert naît
sur le lead (D-ACAL-12 contourné). Effets aval : `depuis-lead` rend alors le plus récent (la copie importée).
Témoin : `POST calepinages/ {lead}` sur ce lead (porte CRUD) => 409."""
SONDE = {"constat": "C-ACON-004", "sha": "33cba7f5d",
         "attendu": "repro si import-projet (lead L qui a déjà C1 ouvert) = 201 et calepinages_ouverts_du_lead(L) = 2, "
                    "depuis-lead L rend alors la copie importée ; témoin : POST calepinages/ {lead: L} = 409",
         "modeles": ["calepinage.Calepinage", "calepinage.CalepinageVersion"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.calepinage.models import Calepinage
    from apps.calepinage.selectors import calepinage_ouvert_du_lead, calepinages_ouverts_du_lead
    from apps.calepinage.services.creation import ouvrir_ou_creer_pour_lead
    from apps.calepinage.services.export_projet import document_de_projet
    from apps.crm.models import Lead
    from apps.roles.models import Role
    from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ACON 004', slug='sonde-acon-004')
    role = Role.objects.create(company=co, nom='Directeur', permissions=list(DIRECTEUR_PERMISSIONS))
    u = get_user_model().objects.create_user(username='sonde_acon_004', password='x', company=co, role=role)
    api = APIClient()
    api.force_authenticate(u)
    L = Lead.objects.create(company=co, nom='Toiture', prenom='K04-L')
    L2 = Lead.objects.create(company=co, nom='Autre dossier', prenom='K04-L2')
    c1, cree1 = ouvrir_ou_creer_pour_lead(L.pk, co, user=u, titre='C1')
    source = Calepinage.objects.create(company=co, lead_id=L2.pk, titre='Source',
                                       roof_layout={'version': 2, 'zones': []})
    projet = document_de_projet(source)
    base = '/api/django/calepinage/calepinages/'
    ouverts_avant = [c.pk for c in calepinages_ouverts_du_lead(co, L.pk)]
    temoin = api.post(base, {'lead': L.pk, 'titre': 'doublon'}, format='json', **H)
    ap = api.post(f'{base}import-projet/', {'projet': projet, 'lead': L.pk, 'apercu': True}, format='json', **H)
    im = api.post(f'{base}import-projet/', {'projet': projet, 'lead': L.pk, 'apercu': False}, format='json', **H)
    ouverts_apres = [c.pk for c in calepinages_ouverts_du_lead(co, L.pk)]
    ouvert_servi = getattr(calepinage_ouvert_du_lead(co, L.pk), 'pk', None)
    dl = api.post(f'{base}depuis-lead/', {'lead': L.pk}, format='json', **H)
    obs = {'c1': c1.pk, 'c1_cree': cree1, 'ouverts_avant': ouverts_avant,
           'temoin_create_http': temoin.status_code, 'apercu_http': ap.status_code,
           'import_http': im.status_code, 'import_corps': str(im.data)[:200],
           'ouverts_apres': ouverts_apres, 'calepinage_ouvert_du_lead': ouvert_servi,
           'depuis_lead_http': dl.status_code, 'depuis_lead_calepinage': (dl.data or {}).get('calepinage')}
    temoin_ok = temoin.status_code == 409 and ouverts_avant == [c1.pk]
    defaut = im.status_code == 201 and len(ouverts_apres) == 2
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    print(obs)
    return obs
