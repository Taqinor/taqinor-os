# flake8: noqa  (sonde de vérification ADVS25, contre-visite fraîche, rejouable par scripts/sonde.py)
"""ADVS25 contre-visite — devis AGRICOLE envoyé. Trois gestes : (1) PATCH etude-params avec la MÊME HMT (aucune
correction réelle : empreinte inchangée, 0 activité ajoutée, pas de marqueur resync) ; (2) PATCH d'une autre entrée
d'écran (`distance_champ_m` 0 → 35) : empreinte change + 1 activité « corrigé après envoi » + marqueur ; (3) signature
portant l'empreinte COURANTE (relue après le geste 2) : acceptée (pas de faux verrou), et l'ancienne empreinte relue
avant le geste 2 : 409 `empreinte_perimee`. `repro: true` = un des trois comportements manque. Société neuve,
transaction annulée."""
SONDE = {"constat": "C-ADVS-044", "sha": "06ced8b1a",
         "attendu": "même valeur : rien ; autre entrée d'écran : empreinte change + trace ; signature à l'empreinte courante OK, à l'ancienne 409",
         "modeles": ["ventes.Devis", "ventes.DevisActivity", "ventes.DevisSignature", "ventes.ShareLink"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.parametres.models import CompanyProfile
    from apps.stock.models import FicheTechnique, Produit
    from apps.ventes.domain import pompage
    from apps.ventes.models import Devis, DevisActivity, DevisSignature, LigneDevis, ShareLink
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS VER1 201', slug='sonde-advs-ver1-201')
    u = U.objects.create_user(username='sonde-advs-ver1-201', password='x', role_legacy='admin', company=c)
    prof, _ = CompanyProfile.objects.get_or_create(company=c)
    CompanyProfile.objects.filter(pk=prof.pk).update(agricole_pump_hours=Decimal('7'))
    cl = Client.objects.create(company=c, nom='Fellah', prenom='V1', email='sonde-advs-ver1-201@example.invalid',
                               telephone='+212600004403', adresse='Douar, Taroudant')
    courbe = {'debits_m3h': [0, 10, 20, 28, 34, 38], 'hmt_m': [100, 94, 80, 68, 50, 38]}

    def mk(nom, **kw):
        kw.setdefault('prix_vente', Decimal('1500'))
        kw.setdefault('prix_achat', Decimal('900'))
        return Produit.objects.create(company=c, nom=nom, **kw)
    pompe = mk('Pompe immergée OSP 30/9 7,5 CV 380V', role_pompage='pompe', type_pompe='immergee',
               alimentation='tri', pompe_kw=Decimal('5.5'), pompe_cv=Decimal('7.5'), tension_v=380,
               courbe_pompe=courbe)
    var = mk('VARIATEUR VEICHI SI23 5.5KW 380V', role_pompage='variateur_pompage', alimentation='tri',
             pompe_kw=Decimal('5.5'), tension_v=380)
    FicheTechnique.objects.create(company=c, produit=var, type_fiche='variateur_pompage',
                                  ond_mppt_v_min=Decimal('250'), ond_mppt_v_max=Decimal('750'),
                                  ond_v_max_abs=Decimal('800'), ond_i_max_mppt_a=Decimal('20'), ond_phases=3,
                                  var_v_sortie_v=Decimal('380'))
    pan = mk('Panneau 710W')
    FicheTechnique.objects.create(company=c, produit=pan, type_fiche='module', pmax_wc=Decimal('710'),
                                  vmp_v=Decimal('40'), voc_v=Decimal('48'), isc_a=Decimal('18'), imp_a=Decimal('17'))
    jour = [0] * 6 + [100, 300, 500, 700, 850, 950, 1000, 950, 850, 700, 500, 300, 100] + [0] * 5
    profils = [[g * (0.7 + 0.05 * i) for g in jour] for i in range(12)]
    entrees = {'mode_pompe': 'neuve', 'type_pompe': 'immergee', 'alim': 'tri',
               'besoin': {'mode': 'volume_declare', 'volume_m3_jour': 120},
               'hmt_entrees': {'saisie_m': 60}, 'distance_champ_m': 0,
               'localisation': {'ville': 'Taroudant', 'lat': 30.47, 'lon': -8.88}}
    api, pub = APIClient(), APIClient()
    api.force_authenticate(u)
    etapes = []

    def appel(nom, cli, meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(cli, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
        except Exception as e:
            etapes.append((nom, 599, repr(e)[:300]))
            return 599, {}
        brut = r.content if hasattr(r, 'content') else b''.join(r.streaming_content)
        txt = brut.decode('utf-8', 'replace')
        etapes.append((nom, r.status_code, '' if r.status_code < 400 else txt[:300]))
        try:
            return r.status_code, json.loads(txt)
        except Exception:
            return r.status_code, {}

    obs = {'etapes': etapes}
    with mock.patch.object(pompage, 'profils_horaires_site', return_value=profils), \
            mock.patch.object(pompage, 'temperatures_du_site', return_value=None), \
            mock.patch('apps.ventes.public_views._notify_open'), \
            mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
        dv = Devis.objects.create(company=c, reference='DEV-ADVSV1201-0001', client=cl, statut='brouillon',
                                  taux_tva=Decimal('20.00'), remise_globale=Decimal('0'), created_by=u,
                                  mode_installation='agricole', etude_params=dict(entrees))
        for o, (p, q) in enumerate(((pompe, 1), (var, 1), (pan, 10))):
            LigneDevis.objects.create(devis=dv, produit=p, designation=p.nom, quantite=Decimal(q),
                                      prix_unitaire=p.prix_vente, remise=Decimal('0'), ordre=o)
        from apps.ventes.services import rafraichir_etudes_du_devis
        try:
            rafraichir_etudes_du_devis(dv)
        except Exception as e:
            obs['rafraichir_err'] = repr(e)[:300]
        appel('share-link envoi', api, 'post', f'/api/django/ventes/devis/{dv.id}/share-link/', {'envoi': True})
        dv.refresh_from_db()
        obs['statut_envoi'] = dv.statut
        link = ShareLink.objects.filter(devis=dv, revoque_le__isnull=True).order_by('-id').first()
        if link is None or dv.statut != 'envoye':
            return {'repro': False, 'observe': dict(obs, impossible='devis non envoyé / lien absent')}
        url_data = f'/api/django/public/proposal/{link.token}/data/'
        _, lu1 = appel('lecture 1', pub, 'get', url_data)
        e1 = lu1.get('empreinte_contenu')
        a0 = DevisActivity.objects.filter(devis=dv).count()
        # (1) même valeur
        appel('PATCH hmt identique', api, 'patch', f'/api/django/ventes/devis/{dv.id}/etude-params/',
              {'hmt_entrees': {'saisie_m': 60}})
        _, lu1b = appel('lecture 1b', pub, 'get', url_data)
        e1b = lu1b.get('empreinte_contenu')
        dv.refresh_from_db()
        obs['noop'] = {'empreinte_stable': e1 == e1b, 'activites_ajoutees': DevisActivity.objects.filter(devis=dv).count() - a0,
                       'resync': (dv.etude_params or {}).get('resync_apres_envoi')}
        a1 = DevisActivity.objects.filter(devis=dv).count()
        # (2) autre entrée d'écran
        s2, _ = appel('PATCH distance_champ_m', api, 'patch', f'/api/django/ventes/devis/{dv.id}/etude-params/',
                      {'distance_champ_m': 35})
        _, lu2 = appel('lecture 2', pub, 'get', url_data)
        e2 = lu2.get('empreinte_contenu')
        dv.refresh_from_db()
        obs['autre_entree'] = {'http': s2, 'empreinte_change': e1b != e2,
                               'activites_ajoutees': DevisActivity.objects.filter(devis=dv).count() - a1,
                               'resync': bool((dv.etude_params or {}).get('resync_apres_envoi')),
                               'distance_en_base': (dv.etude_params or {}).get('distance_champ_m')}
        # (3) ancienne empreinte refusée, puis courante acceptée
        sa, ra = appel('signature ancienne', pub, 'post', f'/api/django/public/proposal/{link.token}/accept/',
                       {'nom': 'M. Fellah', 'consent_esign': True, 'empreinte_contenu': e1b})
        obs['signature_ancienne'] = {'http': sa, 'code': ra.get('code')}
        sc, rc = appel('signature courante', pub, 'post', f'/api/django/public/proposal/{link.token}/accept/',
                       {'nom': 'M. Fellah', 'consent_esign': True, 'empreinte_contenu': e2})
        dv.refresh_from_db()
        obs['signature_courante'] = {'http': sc, 'code': rc.get('code'), 'statut': dv.statut,
                                     'signatures': DevisSignature.objects.filter(devis=dv).count()}
    n, a, sa_, sc_ = obs['noop'], obs['autre_entree'], obs['signature_ancienne'], obs['signature_courante']
    ecarts = []
    if not n['empreinte_stable'] or n['activites_ajoutees'] != 0 or n['resync']:
        ecarts.append('faux positif sur correction identique')
    if not a['empreinte_change'] or a['activites_ajoutees'] < 1 or not a['resync']:
        ecarts.append("autre entrée d'écran non scellée / non tracée")
    if not (sa_['http'] == 409 and sa_['code'] == 'empreinte_perimee'):
        ecarts.append('ancienne empreinte non refusée')
    if not (sc_['http'] == 200 and sc_['statut'] == 'accepte'):
        ecarts.append('empreinte courante refusée (faux verrou)')
    obs['ecarts'] = ecarts
    return {'repro': bool(ecarts), 'observe': obs}
