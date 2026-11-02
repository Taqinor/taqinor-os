# flake8: noqa  (sonde de vérification F1 (lane 7), rejouable par scripts/sonde.py)
"""F1 — correction d'ÉTUDE seule d'un devis AGRICOLE ENVOYÉ par PATCH /devis/<id>/etude-params/ (geste ETUDE,
permis sur un envoyé) : les chiffres imprimés (m³/jour, HMT) changent, mais `empreinte_contenu` servie par la page
publique ne bouge pas (ADEV96 borné au C&I), aucune trace « Corrigé après envoi » ni `resync_apres_envoi`
(`fin_de_geste_devis` ne compare que lignes/entete/note/option/conception) et la signature avec l'ANCIENNE empreinte
passe. PVGIS/TMY simulés (patron AGR123). Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-044", "sha": "1dfa7986c",
         "attendu": "étude agricole corrigée après envoi → empreinte change, trace posée, signature à l'ancienne empreinte 409 (défaut : rien)",
         "modeles": ["ventes.Devis", "ventes.DevisActivity", "ventes.ShareLink", "ventes.DevisSignature"]}


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
    from apps.ventes.domain.etudes import rafraichir_etudes_du_devis
    from apps.ventes.models import Devis, DevisActivity, DevisSignature, LigneDevis, ShareLink
    U = get_user_model()
    co = Company.objects.create(nom='Sonde ADVS 044', slug='sonde-advs-044')
    prof, _ = CompanyProfile.objects.get_or_create(company=co)
    CompanyProfile.objects.filter(pk=prof.pk).update(agricole_pump_hours=Decimal('7'))
    u = U.objects.create_user(username='sonde-advs-044', password='x', role_legacy='admin', company=co)
    cl = Client.objects.create(company=co, nom='Agri', prenom='Etude', email='sonde-advs-044@example.invalid')
    jour = [0] * 6 + [100, 300, 500, 700, 850, 950, 1000, 950, 850, 700, 500, 300, 100] + [0] * 5
    profils = [[g * (0.7 + 0.05 * i) for g in jour] for i in range(12)]
    courbe = {'debits_m3h': [0, 12, 24, 30, 36, 39], 'hmt_m': [91, 85, 70, 60, 43, 34]}

    def prod(nom, **kw):
        kw.setdefault('prix_vente', Decimal('1000'))
        kw.setdefault('prix_achat', Decimal('600'))
        return Produit.objects.create(company=co, nom=nom, **kw)
    pompe = prod('Pompe immergée OSP 30/8 7,5 CV 380V', role_pompage='pompe', type_pompe='immergee',
                 alimentation='tri', pompe_kw=Decimal('5.5'), pompe_cv=Decimal('7.5'), tension_v=380,
                 courbe_pompe=courbe)
    var = prod('VARIATEUR VEICHI SI23 5.5KW 380V', role_pompage='variateur_pompage', alimentation='tri',
               pompe_kw=Decimal('5.5'), tension_v=380)
    FicheTechnique.objects.create(company=co, produit=var, type_fiche='variateur_pompage',
                                  ond_mppt_v_min=Decimal('250'), ond_mppt_v_max=Decimal('750'),
                                  ond_v_max_abs=Decimal('800'), ond_i_max_mppt_a=Decimal('20'), ond_phases=3,
                                  var_v_sortie_v=Decimal('380'))
    pan = prod('Panneau 710W')
    FicheTechnique.objects.create(company=co, produit=pan, type_fiche='module', pmax_wc=Decimal('710'),
                                  vmp_v=Decimal('40'), voc_v=Decimal('48'), isc_a=Decimal('18'), imp_a=Decimal('17'))
    entrees = {'mode_pompe': 'neuve', 'type_pompe': 'immergee', 'alim': 'tri',
               'besoin': {'mode': 'volume_declare', 'volume_m3_jour': 135},
               'hmt_entrees': {'saisie_m': 60},
               'localisation': {'ville': 'Taroudant', 'lat': 30.47, 'lon': -8.88}}
    obs = {}

    def appel(api, meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(api, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace')
            try:
                return r.status_code, json.loads(txt)
            except Exception:
                return r.status_code, {'_brut': txt[:200]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}

    def eau(lu):
        sa = (lu.get('synthese_agricole') or {}) if isinstance(lu, dict) else {}
        e = sa.get('eau') or {}
        return {k: e.get(k) for k in ('m3_jour', 'hmt_m', 'debit_hmt_m3h', 'heures_pompage')}

    with mock.patch.object(pompage, 'profils_horaires_site', return_value=profils), \
            mock.patch.object(pompage, 'temperatures_du_site', return_value=None), \
            mock.patch('apps.ventes.public_views._notify_open'), \
            mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
        dv = Devis.objects.create(company=co, reference='DEV-ADVS044-0001', client=cl, statut='brouillon',
                                  taux_tva=Decimal('20.00'), remise_globale=Decimal('0'), created_by=u,
                                  mode_installation='agricole', etude_params=dict(entrees))
        for ordre, (p, q) in enumerate(((pompe, 1), (var, 1), (pan, 10))):
            LigneDevis.objects.create(devis=dv, produit=p, designation=p.nom, quantite=Decimal(q),
                                      prix_unitaire=Decimal('1000'), remise=Decimal('0'), ordre=ordre)
        try:
            with transaction.atomic():
                rafraichir_etudes_du_devis(dv)
        except Exception as e:
            obs['rafraichir_err'] = repr(e)[:200]
        dv.refresh_from_db()
        obs['etude_avant'] = {k: (dv.etude_params or {}).get(k) for k in ('m3_jour', 'hmt_m', 'debit_hmt_m3h', 'pompe_cv')}
        Devis.objects.filter(pk=dv.pk).update(statut='envoye')
        link = ShareLink.for_devis(dv)
        pub, api = APIClient(), APIClient()
        api.force_authenticate(u)
        s, lu1 = appel(pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
        e1 = lu1.get('empreinte_contenu') if isinstance(lu1, dict) else None
        obs['lecture_1'] = [s, (e1 or '')[:12], eau(lu1)]
        act0 = DevisActivity.objects.filter(devis=dv).count()
        s, rp = appel(api, 'patch', f'/api/django/ventes/devis/{dv.id}/etude-params/', {'hmt_entrees': {'saisie_m': 80}})
        obs['patch_etude'] = [s, '' if s < 400 else str(rp)[:200]]
        dv.refresh_from_db()
        obs['etude_apres'] = {k: (dv.etude_params or {}).get(k) for k in ('m3_jour', 'hmt_m', 'debit_hmt_m3h', 'pompe_cv')}
        obs['resync_apres_envoi'] = (dv.etude_params or {}).get('resync_apres_envoi')
        obs['activites_creees'] = DevisActivity.objects.filter(devis=dv).count() - act0
        s, lu2 = appel(pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
        e2 = lu2.get('empreinte_contenu') if isinstance(lu2, dict) else None
        obs['lecture_2'] = [s, (e2 or '')[:12], eau(lu2)]
        obs['empreinte_identique'] = bool(e1) and e1 == e2
        obs['chiffres_imprimes_changes'] = eau(lu1) != eau(lu2)
        s, ra = appel(pub, 'post', f'/api/django/public/proposal/{link.token}/accept/',
                      {'nom': 'M. Agri', 'consent_esign': True, 'empreinte_contenu': e1})
        obs['signature_ancienne_empreinte'] = [s, {k: ra.get(k) for k in ('statut', 'code', 'detail')} if isinstance(ra, dict) else '']
    dv.refresh_from_db()
    obs['statut_final'] = dv.statut
    obs['signatures'] = DevisSignature.objects.filter(devis=dv).count()
    repro = bool(obs['chiffres_imprimes_changes'] and obs['empreinte_identique'])
    return {'repro': repro, 'observe': obs}
