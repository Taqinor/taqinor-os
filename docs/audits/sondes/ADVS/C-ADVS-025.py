# flake8: noqa  (sonde de vérification C-L4-5, rejouable par scripts/sonde.py)
"""C-L4-5 — porte 3 (portail client) : le client lit « Mes devis » (total X, empreinte servie ?), le commercial
corrige une ligne de l'ENVOYÉ par l'API (devis-lignes PATCH), le client confirme → 200 accepté au total Y ?
Témoin : même geste au lien public avec l'empreinte lue avant correction → 409 empreinte_perimee. Société neuve,
transaction annulée."""
SONDE = {"constat": "C-ADVS-025", "sha": "1dfa7986c",
         "attendu": "portail : 409 empreinte_perimee après correction (défaut : 200, accepté au nouveau total)",
         "modeles": ["ventes.Devis", "ventes.DevisSignature", "portail.AcceptationDevisPortail"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from unittest import mock
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company, CustomUser
    from apps.crm.models import Client
    from apps.roles.models import Role
    from apps.roles.permissions_registre import PORTAIL_CLIENT_PERMISSIONS, ROLE_PORTAIL_CLIENT
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis, ShareLink
    c = Company.objects.create(nom='Sonde ADVS 025', slug='sonde-advs-025')
    com = CustomUser.objects.create_user(username='sonde-advs-025-com', password='motdepasse-test-1234', company=c,
                                         role_legacy='responsable')
    pan = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='ADVS025-P',
                                 prix_vente=Decimal('1166.67'), tva=Decimal('20'), quantite_stock=100)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 10kW Monophasé', sku='ADVS025-O',
                                 prix_vente=Decimal('14000'), tva=Decimal('20'), quantite_stock=100)
    role, _ = Role.objects.get_or_create(company=c, nom=ROLE_PORTAIL_CLIENT,
                                         defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS), 'est_systeme': True})
    api_com = APIClient()
    api_com.force_authenticate(com)
    obs = {}

    def appel(client, meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(client, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            try:
                return r.status_code, json.loads(r.content.decode('utf-8', 'replace') or '{}')
            except Exception:
                return r.status_code, {}
        except Exception as e:
            return repr(e)[:200], {}

    def devis(etiquette):
        cl = Client.objects.create(company=c, nom='Portail', prenom=etiquette, email=f'sonde-advs-025-{etiquette}@example.invalid')
        d = Devis.objects.create(company=c, reference=f'DEV-ADVS025-{etiquette}', client=cl, statut='envoye',
                                 taux_tva=Decimal('20'), created_by=com)
        l1 = LigneDevis.objects.create(devis=d, produit=pan, designation=pan.nom, quantite=Decimal('12'),
                                       prix_unitaire=pan.prix_vente, remise=Decimal('0'), ordre=0)
        LigneDevis.objects.create(devis=d, produit=ond, designation=ond.nom, quantite=Decimal('1'),
                                  prix_unitaire=ond.prix_vente, remise=Decimal('0'), ordre=1)
        return cl, d, l1

    # Porte 3 — portail
    cl, d, l1 = devis('P')
    portail = CustomUser.objects.create_user(username='sonde-advs-025-portail', password='motdepasse-test-1234',
                                             company=c, role=role)
    portail.portee = CustomUser.PORTEE_PORTAIL_CLIENT
    portail.portail_client_id = cl.id
    portail.save()
    api_p = APIClient()
    api_p.force_authenticate(portail)
    s, liste = appel(api_p, 'get', '/api/django/portail/mes-devis/')
    lignes = liste if isinstance(liste, list) else (liste.get('results') or [])
    ligne = next((x for x in lignes if str(x.get('id')) == str(d.id)), {})
    obs['portail_liste'] = [s, {k: ligne.get(k) for k in ('total_ttc', 'statut')},
                            sorted(k for k in ligne.keys() if 'empreinte' in k or 'hash' in k)]
    s, rp = appel(api_com, 'patch', f'/api/django/ventes/devis-lignes/{l1.id}/',
                  {'prix_unitaire': str(l1.prix_unitaire * 2)})
    obs['correction_commercial'] = s
    s, ra = appel(api_p, 'post', f'/api/django/portail/mes-devis/{d.id}/accepter/',
                  {'nom': 'Client Portail', 'consent_esign': True, 'accepte_conditions': True})
    d.refresh_from_db()
    obs['portail_accepter'] = [s, ra.get('detail'), ra.get('code')]
    obs['portail_apres'] = {'statut': d.statut, 'total_ttc': str(d.total_ttc)}
    # Témoin — porte 1 (lien public), même geste
    cl2, d2, l2 = devis('L')
    link = ShareLink.objects.create(company=c, devis=d2)
    pub = APIClient()
    with mock.patch('apps.ventes.public_views._notify_open'):
        s, lu = appel(pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
        appel(api_com, 'patch', f'/api/django/ventes/devis-lignes/{l2.id}/', {'prix_unitaire': str(l2.prix_unitaire * 2)})
        s, rl = appel(pub, 'post', f'/api/django/public/proposal/{link.token}/accept/',
                      {'nom': 'Client Lien', 'consent_esign': True, 'empreinte_contenu': lu.get('empreinte_contenu')})
    d2.refresh_from_db()
    obs['temoin_lien'] = [s, rl.get('code'), d2.statut]
    repro = bool(obs['portail_accepter'][0] == 200 and d.statut == 'accepte' and obs['correction_commercial'] == 200)
    return {'repro': repro, 'observe': obs}
