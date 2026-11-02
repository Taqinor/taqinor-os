# flake8: noqa  (seconde lentille C-ADVS-044, reproduction indépendante — rejouable par scripts/sonde.py)
"""Devis AGRICOLE envoyé (share-link {envoi}) puis correction de la HMT saisie (60 → 88 m) par PATCH
ventes/devis/<id>/etude-params/ {hmt_entrees}. Questions : le m³/jour servi (etude_params + page publique) change-t-il ?
l'empreinte de signature `empreinte_contenu` (modifiabilite.empreinte_contenu_signable) change-t-elle ? une trace
(DevisActivity « Corrigé après envoi », instantané) est-elle posée ? la signature publique portant l'ANCIENNE empreinte
est-elle acceptée (au lieu du 409 empreinte_perimee) ? Fixture propre : pompe OSP à courbe, variateur VEICHI, panneau
710 W, Taroudant ; PVGIS/TMY simulés (pompage.profils_horaires_site / temperatures_du_site patchés). Société neuve,
transaction annulée."""
SONDE = {"constat": "C-ADVS-044", "sha": "1dfa7986c",
         "attendu": "m³/jour change ⇒ empreinte change + trace posée + signature à l'ancienne empreinte refusée 409",
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
    c = Company.objects.create(nom='Sonde ADVS 044 L2', slug='sonde-advs-044-l2')
    u = U.objects.create_user(username='sonde-advs-044-l2', password='x', role_legacy='admin', company=c)
    prof, _ = CompanyProfile.objects.get_or_create(company=c)
    CompanyProfile.objects.filter(pk=prof.pk).update(agricole_pump_hours=Decimal('7'))
    cl = Client.objects.create(company=c, nom='Fellah', prenom='L2', email='sonde-advs-044-l2@example.invalid',
                               telephone='+212600004402', adresse='Douar, Taroudant')
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
               'hmt_entrees': {'saisie_m': 60},
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

    def m3_public(lu):
        trouve = {}

        def fouille(x, chemin):
            if isinstance(x, dict):
                for k, v in x.items():
                    if k in ('m3_jour', 'hmt_m', 'volume_m3_jour') and not isinstance(v, (dict, list)):
                        trouve[chemin + '.' + k] = v
                    fouille(v, chemin + '.' + k)
            elif isinstance(x, list):
                for i, v in enumerate(x[:15]):
                    fouille(v, f'{chemin}[{i}]')
        fouille(lu, '')
        return dict(list(trouve.items())[:12])

    obs = {'etapes': etapes}
    with mock.patch.object(pompage, 'profils_horaires_site', return_value=profils), \
            mock.patch.object(pompage, 'temperatures_du_site', return_value=None), \
            mock.patch('apps.ventes.public_views._notify_open'), \
            mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
        dv = Devis.objects.create(company=c, reference='DEV-ADVS044L2-0001', client=cl, statut='brouillon',
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
        dv.refresh_from_db()
        obs['avant'] = {k: dv.etude_params.get(k) for k in ('hmt_m', 'm3_jour', 'debit_hmt_m3h', 'heures_pompage')}
        appel('share-link envoi', api, 'post', f'/api/django/ventes/devis/{dv.id}/share-link/', {'envoi': True})
        dv.refresh_from_db()
        obs['statut_envoi'] = dv.statut
        link = ShareLink.objects.filter(devis=dv, revoque_le__isnull=True).order_by('-id').first()
        if link is None:
            return {'repro': False, 'observe': obs}
        s, lu1 = appel('public data 1', pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
        emp1 = lu1.get('empreinte_contenu')
        obs['public_avant'] = m3_public(lu1)
        act0 = DevisActivity.objects.filter(devis=dv).count()
        s, rp = appel('PATCH etude-params hmt', api, 'patch', f'/api/django/ventes/devis/{dv.id}/etude-params/',
                      {'hmt_entrees': {'saisie_m': 88}})
        dv.refresh_from_db()
        obs['apres'] = {k: dv.etude_params.get(k) for k in ('hmt_m', 'm3_jour', 'debit_hmt_m3h', 'heures_pompage')}
        obs['statut_apres_patch'] = dv.statut
        acts = list(DevisActivity.objects.filter(devis=dv).order_by('id').values_list('message', flat=True)) \
            if hasattr(DevisActivity, 'message') else []
        obs['activites_ajoutees'] = DevisActivity.objects.filter(devis=dv).count() - act0
        obs['resync_apres_envoi'] = (dv.etude_params or {}).get('resync_apres_envoi')
        s, lu2 = appel('public data 2', pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
        emp2 = lu2.get('empreinte_contenu')
        obs['public_apres'] = m3_public(lu2)
        obs['empreinte_inchangee'] = (emp1 is not None and emp1 == emp2)
        s, ra = appel('signature ancienne empreinte', pub, 'post', f'/api/django/public/proposal/{link.token}/accept/',
                      {'nom': 'M. Fellah', 'consent_esign': True, 'empreinte_contenu': emp1})
        dv.refresh_from_db()
        obs['signature'] = {'http': s, 'code': ra.get('code'), 'detail': str(ra.get('detail'))[:120],
                            'statut_final': dv.statut, 'signatures': DevisSignature.objects.filter(devis=dv).count()}
    change = obs['avant'].get('m3_jour') != obs['apres'].get('m3_jour') or obs['avant'].get('hmt_m') != obs['apres'].get('hmt_m')
    repro = bool(change and obs['empreinte_inchangee'] and obs['activites_ajoutees'] == 0)
    obs['m3_ou_hmt_change'] = change
    return {'repro': repro, 'observe': obs}
