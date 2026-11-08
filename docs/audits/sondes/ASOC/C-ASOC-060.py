# flake8: noqa  (sonde d'audit de parcours PF2 « Socle », rejouable par scripts/sonde.py — METHODE §C.4)
"""K60 — un effacement 09-08 (DSR) laisse l'identité dans le miroir ``tiers.Tiers``.

Client C (email, téléphone, adresse, CIN, ICE, RC, IF) créé → le miroir ARC18 crée son Tiers.
DSR « effacement » sur l'email par la VRAIE route (`POST core/dsr-requests/` puis `…/traiter/`),
puis lecture du Tiers lié par la VRAIE route `GET tiers/tiers/<id>/`.
Jumeau : Fournisseur F (contact, email, téléphone) → DSR effacement sur son email → Tiers miroir.
Témoin : le Client lui-même est bien anonymisé (le scrub CRM a tourné)."""
SONDE = {"constat": "C-ASOC-060", "sha": "c514bd8ba",
         "attendu": "repro si client anonymisé MAIS Tiers lié garde nom/email/téléphone/CIN ; idem fournisseur",
         "modeles": ["crm.Client", "tiers.Tiers", "stock.Fournisseur", "core.DataSubjectRequest"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Fournisseur
    from apps.tiers.models import Tiers
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ASOC 060', slug='sonde-asoc-060')
    u = get_user_model().objects.create_user(username='sonde_asoc_060', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)

    cl = Client.objects.create(company=co, nom='Benali', prenom='Ahmed', email='asoc060@example.invalid',
                               telephone='0612345678', adresse='12 rue des Roses, Casablanca',
                               cin='AB123456', ice='001122334455667', rc='RC9988', if_fiscal='IF7766')
    cl.refresh_from_db()
    t_avant = Tiers.objects.filter(pk=cl.tiers_id).values('nom', 'prenom', 'email', 'telephone', 'adresse', 'cin',
                                                          'ice', 'rc', 'identifiant_fiscal').first()

    def dsr(ident):
        r = api.post('/api/django/core/dsr-requests/', {'subject_identifier': ident, 'kind': 'effacement'},
                     format='json', **H)
        if r.status_code >= 400:
            return {'creation_http': r.status_code, 'detail': str(r.data)[:200]}
        rid = r.data['id']
        t = api.post(f'/api/django/core/dsr-requests/{rid}/traiter/', {}, format='json', **H)
        return {'creation_http': r.status_code, 'traiter_http': t.status_code,
                'statut': t.data.get('statut') if t.status_code < 400 else None,
                'resultat': t.data.get('resultat') if t.status_code < 400 else str(t.data)[:200]}

    obs = {'tiers_avant': t_avant, 'dsr_client': dsr('asoc060@example.invalid')}
    cl.refresh_from_db()
    obs['client_apres'] = {'nom': cl.nom, 'email': cl.email, 'telephone': cl.telephone, 'cin': cl.cin,
                           'is_anonymized': cl.is_anonymized, 'tiers_id': cl.tiers_id}
    g = api.get(f'/api/django/tiers/tiers/{cl.tiers_id}/', **H)
    obs['tiers_api_http'] = g.status_code
    obs['tiers_apres'] = {k: g.data.get(k) for k in ('nom', 'prenom', 'email', 'telephone', 'adresse', 'cin', 'ice',
                                                       'rc', 'identifiant_fiscal')} if g.status_code == 200 else str(g.data)[:200]
    s = api.get('/api/django/tiers/tiers/', {'search': '0612345678'}, **H)
    obs['tiers_search_tel_http'] = s.status_code
    try:
        rows = s.data.get('results', s.data) if isinstance(s.data, dict) else s.data
        obs['tiers_search_tel_hits'] = len(rows)
    except Exception as exc:  # noqa
        obs['tiers_search_tel_hits'] = f'err {exc!r}'[:80]

    # Jumeau fournisseur
    f = Fournisseur.objects.create(company=co, nom='Grossiste Solaire SARL', contact_personne='Karim Tazi',
                                   email='asoc060f@example.invalid', telephone='0661223344')
    f.refresh_from_db()
    tf_avant = Tiers.objects.filter(pk=f.tiers_id).values('nom', 'email', 'telephone').first()
    obs['tiers_fournisseur_avant'] = tf_avant
    obs['dsr_fournisseur'] = dsr('asoc060f@example.invalid')
    f.refresh_from_db()
    obs['fournisseur_apres'] = {'contact_personne': f.contact_personne, 'email': f.email, 'telephone': f.telephone}
    obs['tiers_fournisseur_apres'] = Tiers.objects.filter(pk=f.tiers_id).values('nom', 'email', 'telephone').first()
    print(obs)

    ta = obs['tiers_apres'] if isinstance(obs['tiers_apres'], dict) else {}
    temoin_ok = obs['client_apres']['is_anonymized'] and obs['client_apres']['email'] is None
    defaut_client = bool(ta) and (ta.get('email') == 'asoc060@example.invalid' or ta.get('telephone') == '0612345678'
                                  or ta.get('cin') == 'AB123456' or ta.get('nom') == 'Benali')
    tfa = obs['tiers_fournisseur_apres'] or {}
    defaut_fourn = obs['fournisseur_apres']['email'] is None and (
        tfa.get('email') == 'asoc060f@example.invalid' or tfa.get('telephone') == '0661223344')
    obs['temoin_ok'] = bool(temoin_ok)
    obs['defaut_client'] = bool(defaut_client)
    obs['defaut_fournisseur'] = bool(defaut_fourn)
    obs['repro'] = bool(temoin_ok and defaut_client)
    return obs
