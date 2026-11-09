# flake8: noqa  (sonde d'audit PA2 « Conception », seconde lentille — METHODE §B.5)
"""C-ACON-020 « à élucider » — pourquoi ``rafraichir_etudes_du_devis`` sur un devis BROUILLON lié
rend-il la simulation du calepinage périmée (ombrage 8,0 % → None) ?

Angle : on capture la CHARGE de ``empreinte_simulation`` (espion sur ``services.simulation._canonique``,
seul point où la charge est sérialisée) à chaque lecture servie, et on joue les six rafraîchisseurs
de ``rafraichir_etudes_du_devis`` UN PAR UN, dans son ordre, en relisant après chacun : perte servie,
clés de la charge qui diffèrent de l'état frais, ``Calepinage.resultat`` / ``roof_layout`` / réglages
société modifiés. Puis on rejoue le geste ÉCRAN réel (PATCH du devis brouillon après simulation) et on
lit le bloc horaire RANGÉ (celui que lit le PDF) : porte-t-il l'ombrage ?
D/E — même chaîne sur une société dont le PROFIL (CompanyProfile, fuseau Africa/Casablanca) existe AVANT la
simulation (état de toute société de prod créée par init_tenant / console) : geste écran réel = PATCH d'une
ligne (``devis-lignes``, mode RAFRAICHIR du pipeline, sans force), dans les deux ordres (simuler puis
enregistrer ; enregistrer, simuler, ré-enregistrer), puis GET /proposal (espion build_quote_data : la
production du bloc rangé avec ombrage est-elle celle passée au rendu ?).
F — chemin écran « Générer le devis » (POST calepinage/calepinages/<id>/generer-devis/, seed_catalogue, rôle
Directeur) sur un calepinage DÉJÀ simulé avec ombrage : ``build_devis_from_layout`` rafraîchit les études AVANT
``_lier`` ⇒ le bloc rangé (PDF) a-t-il l'ombrage ? Puis envoi (statut seul) : PDF vs page publique.
Même montage que C-ACON-020 (météo rejouée, fiches module/onduleur injectées). Transaction annulée."""
SONDE = {"constat": "C-ACON-020-L2", "sha": "819fe0f8c",
         "attendu": "repro si un rafraichisseur du devis perime la simulation du calepinage (cle d'empreinte nommee) ; D/E disent si, profil societe present, le bloc range et le PDF portent l'ombrage",
         "modeles": ["ventes.Devis", "calepinage.Calepinage", "calepinage.ParametresCalepinage"]}


def sonde(ctx):
    import copy
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    from apps.calepinage.models import Calepinage
    from apps.calepinage.services.liens import lier_devis
    from apps.calepinage.services.simulation import simuler_calepinage
    import apps.calepinage.services.simulation as simmod
    from apps.calepinage.selectors import resultat_servi
    from apps.calepinage.tests.test_acal_multi_pans import _ClientParOrientation, _layout, _zone
    from apps.calepinage.tests.test_calx5_simulation import MATERIEL, REGLAGES
    from apps.ventes.horaire.ombrage import perte_ombrage_du_devis
    from apps.ventes.domain import etudes as E
    from apps.ventes.profils_comparatifs import rafraichir_profils_comparatifs_devis
    from apps.ventes.electrical_service import rafraichir_conception_electrique_devis

    H = {'HTTP_HOST': 'localhost'}
    patch_mat = mock.patch('apps.calepinage.services.electrique.resoudre_materiel', return_value=MATERIEL)
    patch_mat.start()
    charges = []
    vrai_can = simmod._canonique

    def espion_can(valeur):
        if isinstance(valeur, dict) and 'version_simulation' in valeur:
            charges.append(json.loads(json.dumps(valeur, default=str)))
        return vrai_can(valeur)

    patch_can = mock.patch.object(simmod, '_canonique', side_effect=espion_can)
    patch_can.start()
    obs = {}
    try:
        co = Company.objects.create(nom='Sonde ACON 020 L2', slug='sonde-acon-020-l2')
        u = get_user_model().objects.create_user(username='sonde_acon_020_l2', password='x',
                                                 role_legacy='admin', company=co)
        api = APIClient()
        api.force_authenticate(u)
        sim0 = copy.deepcopy(REGLAGES['simulation'])
        for _v in sim0.values():
            _v['source'] = 'societe'
        r = api.put('/api/django/calepinage/parametres/', {'simulation': sim0}, format='json', **H)
        obs['put_reglages'] = r.status_code

        def montage(suffixe, co=co, u=u, simuler=True):
            cl = Client.objects.create(company=co, nom='Client L2 ' + suffixe)
            lead_kw = dict(company=co, nom='Lead L2 ' + suffixe, facture_hiver=Decimal('900'))
            if any(f.name == 'ville' for f in Lead._meta.fields):
                lead_kw['ville'] = 'Casablanca'
            lead = Lead.objects.create(**lead_kw)
            d = Devis.objects.create(company=co, reference='DEV-L2-' + suffixe, client=cl, lead=lead,
                                     taux_tva=Decimal('20'), statut='brouillon', created_by=u,
                                     mode_installation='residentiel',
                                     etude_params={'factures_mensuelles_reelles': [900] * 12,
                                                   'distributeur': 'onee', 'ville': 'casablanca'})
            for i, (nom, qte, pu) in enumerate((('Panneau Canadien Solar 710W', '8', '1166.67'),
                                                ('Onduleur réseau Huawei 5kW Monophasé', '1', '9000.00'))):
                p = Produit.objects.create(company=co, nom=nom, sku=f'l2{suffixe}-{i}', prix_vente=Decimal(pu),
                                           quantite_stock=50)
                LigneDevis.objects.create(devis=d, produit=p, designation=nom, quantite=Decimal(qte),
                                          prix_unitaire=Decimal(pu), remise=Decimal('0'), ordre=i)
            layout = _layout(_zone(1, 16, 90.0), _zone(2, 8, 270.0))
            for zone in layout['zones']:
                zone['geometry']['solarAccess'] = {
                    'values': [0.9] * zone['geometry']['count'],
                    'method': {'horizon': False, 'rangees': False, 'resolution': 'annuelle',
                               'description': 'Accès solaire annuel'},
                    'assumptions': {'periode': 'annee'}, 'computedAt': '2026-10-01T10:00:00Z'}
            c = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='L2 ' + suffixe, roof_layout=layout)
            lier_devis(c, d.pk)
            if simuler:
                simuler_calepinage(c, client=_ClientParOrientation(), materiel=MATERIEL, enregistrer=True)
            c.refresh_from_db()
            d.refresh_from_db()
            return d, c

        def charge_servie(c):
            charges.clear()
            servi = resultat_servi(Calepinage.objects.get(pk=c.pk))
            return (charges[-1] if charges else None), servi

        def ecarts(a, b):
            """Clés (et sous-clés de 1er niveau) de la charge qui diffèrent."""
            out = []
            a, b = a or {}, b or {}
            for k in sorted(set(a) | set(b)):
                if a.get(k) != b.get(k):
                    va, vb = a.get(k), b.get(k)
                    if isinstance(va, dict) and isinstance(vb, dict):
                        for sk in sorted(set(va) | set(vb)):
                            if va.get(sk) != vb.get(sk):
                                out.append([f'{k}.{sk}', str(va.get(sk))[:160], str(vb.get(sk))[:160]])
                    else:
                        out.append([k, str(va)[:160], str(vb)[:160]])
            return out

        # ── A. rafraîchisseurs un par un ─────────────────────────────────────
        d, c = montage('A')
        ref, servi0 = charge_servie(c)
        obs['A0_perte_fraiche'] = perte_ombrage_du_devis(Devis.objects.get(pk=d.pk))
        obs['A0_hash_stocke_egal_empreinte_live'] = ((c.resultat or {}).get('simulation') or {}).get('hash_entree') is not None
        resultat0 = json.dumps(c.resultat, sort_keys=True, default=str)
        layout0 = json.dumps(c.roof_layout, sort_keys=True, default=str)
        etapes = [
            ('etude_horaire', lambda dd: E.rafraichir_etude_horaire_devis(dd)),
            ('dimensionnement', lambda dd: E.rafraichir_dimensionnement_devis(dd)),
            ('profils_comparatifs', lambda dd: rafraichir_profils_comparatifs_devis(dd)),
            ('conception_electrique', lambda dd: rafraichir_conception_electrique_devis(dd)),
            ('etude_ci', lambda dd: E._rafraichir_etude_ci(dd)),
            ('etude_pompage', lambda dd: E._rafraichir_etude_pompage(dd)),
        ]
        A = []
        for nom, f in etapes:
            dd = Devis.objects.get(pk=d.pk)
            charges.clear()
            try:
                f(dd)
                err = None
            except Exception as exc:  # noqa
                err = repr(exc)[:200]
            nb_lectures_pendant = len(charges)
            cc = Calepinage.objects.get(pk=c.pk)
            ch, servi = charge_servie(cc)
            dd = Devis.objects.get(pk=d.pk)
            bloc = (dd.etude_params or {}).get('etude_horaire') or {}
            A.append({
                'etape': nom, 'erreur': err,
                'lectures_empreinte_pendant_etape': nb_lectures_pendant,
                'perte_apres': perte_ombrage_du_devis(dd),
                'simulation_perimee': servi.get('simulation_perimee'), 'motif': servi.get('motif'),
                'ecarts_charge_vs_frais': ecarts(ref, ch)[:8],
                'resultat_calepinage_modifie': json.dumps(cc.resultat, sort_keys=True, default=str) != resultat0,
                'roof_layout_modifie': json.dumps(cc.roof_layout, sort_keys=True, default=str) != layout0,
                'bloc_range_production_kwh': (bloc.get('annuel') or {}).get('production_kwh'),
                'bloc_range_ombrage': bloc.get('ombrage'),
            })
        obs['A_etapes'] = A[:1] + [[e['etape'], e['perte_apres']] for e in A[1:]]

        # ── B. le geste écran : PATCH du devis brouillon après simulation ────
        d2, c2 = montage('B')
        obs['B0_perte_fraiche'] = perte_ombrage_du_devis(Devis.objects.get(pk=d2.pk))
        ref2, _ = charge_servie(c2)
        rp = api.patch(f'/api/django/ventes/devis/{d2.pk}/', {'notes': 'retouche'}, format='json', **H)
        obs['B_patch_http'] = rp.status_code
        if rp.status_code >= 400:
            obs['B_patch_corps'] = str(rp.content[:300])
        dd2 = Devis.objects.get(pk=d2.pk)
        ch2, servi2 = charge_servie(c2)
        bloc2 = (dd2.etude_params or {}).get('etude_horaire') or {}
        obs['B_perte_apres_patch'] = perte_ombrage_du_devis(dd2)
        obs['B_simulation_perimee'] = servi2.get('simulation_perimee')
        obs['B_ecarts_charge'] = ecarts(ref2, ch2)[:8]
        obs['B_bloc_range_production_kwh'] = (bloc2.get('annuel') or {}).get('production_kwh')
        obs['B_bloc_range_ombrage'] = bloc2.get('ombrage')
        obs['B_regles_calcul'] = dd2.regles_calcul

        # ── C. re-simulation APRÈS enregistrement, puis ré-enregistrement ────
        cc2 = Calepinage.objects.get(pk=c2.pk)
        simuler_calepinage(cc2, forcer=True, client=_ClientParOrientation(), materiel=MATERIEL, enregistrer=True)
        obs['C_perte_apres_resimulation'] = perte_ombrage_du_devis(Devis.objects.get(pk=d2.pk))
        rp2 = api.patch(f'/api/django/ventes/devis/{d2.pk}/', {'notes': 'retouche 2'}, format='json', **H)
        obs['C_patch_http'] = rp2.status_code
        dd2 = Devis.objects.get(pk=d2.pk)
        bloc3 = (dd2.etude_params or {}).get('etude_horaire') or {}
        obs['C_perte_apres_patch2'] = perte_ombrage_du_devis(dd2)
        obs['C_bloc_range_production_kwh'] = (bloc3.get('annuel') or {}).get('production_kwh')
        obs['C_bloc_range_ombrage'] = bloc3.get('ombrage')

        # ── D/E. société AVEC profil avant simulation (état prod) ───────────
        import apps.ventes.quote_engine.builder as builder
        from apps.parametres.models import CompanyProfile
        co2 = Company.objects.create(nom='Sonde ACON 020 L2 bis', slug='sonde-acon-020-l2-bis')
        CompanyProfile.get(company=co2)
        obs['D_profil_fuseau'] = CompanyProfile.objects.filter(company=co2).values_list('fuseau_horaire', flat=True).first()
        u2 = get_user_model().objects.create_user(username='sonde_acon_020_l2b', password='x',
                                                  role_legacy='admin', company=co2)
        api2 = APIClient()
        api2.force_authenticate(u2)
        r = api2.put('/api/django/calepinage/parametres/', {'simulation': sim0}, format='json', **H)
        obs['D_put_reglages'] = r.status_code

        def aplatir(x, pref=''):
            out = {}
            if isinstance(x, dict):
                for k, v in x.items():
                    out.update(aplatir(v, f'{pref}.{k}' if pref else str(k)))
            elif isinstance(x, (list, tuple)):
                for i, v in enumerate(x[:60]):
                    out.update(aplatir(v, f'{pref}[{i}]'))
            elif isinstance(x, (int, float)) and not isinstance(x, bool):
                out[pref] = x
            return out

        def pdf(dd, prod_range):
            captures = []
            vrai_build = builder.build_quote_data

            def espion(*a, **k):
                data = vrai_build(*a, **k)
                captures.append(data)
                return data
            with mock.patch.object(builder, 'build_quote_data', side_effect=espion):
                rp = api2.get(f'/api/django/ventes/devis/{dd.pk}/proposal/', **H)
            plat = aplatir(captures[0]) if captures else {}
            prod_cles = sorted(k for k, v in plat.items() if 'production' in k.lower() or 'prod' in k.lower())
            egal = [k for k, v in plat.items() if prod_range and abs(float(v) - float(prod_range)) < 1.0]
            return {'http': rp.status_code, 'nb_chiffres': len(plat),
                    'egales_bloc_range': egal[:4], 'prod_kwh': plat.get('prod_kwh')}

        def etat(dd, cc, prefixe):
            dd = Devis.objects.get(pk=dd.pk)
            servi = resultat_servi(Calepinage.objects.get(pk=cc.pk))
            bloc = (dd.etude_params or {}).get('etude_horaire') or {}
            prod = (bloc.get('annuel') or {}).get('production_kwh')
            obs[prefixe + '_perte'] = perte_ombrage_du_devis(dd)
            obs[prefixe + '_simulation_perimee'] = servi.get('simulation_perimee')
            obs[prefixe + '_bloc_production_kwh'] = prod
            obs[prefixe + '_bloc_ombrage'] = bloc.get('ombrage')
            return dd, prod

        def patch_ligne(dd, client_api):
            ligne = LigneDevis.objects.filter(devis=dd).order_by('ordre').last()  # onduleur
            rr = client_api.patch(f'/api/django/ventes/devis-lignes/{ligne.pk}/',
                                  {'remise': '0', 'devis': dd.pk}, format='json', **H)
            return rr.status_code, (str(rr.content[:200]) if rr.status_code >= 400 else '')

        # D : simuler PUIS enregistrer (geste écran : PATCH ligne)
        d4, c4 = montage('D', co=co2, u=u2)
        obs['D0_perte_fraiche'] = perte_ombrage_du_devis(Devis.objects.get(pk=d4.pk))
        obs['D_patch_ligne'] = patch_ligne(d4, api2)
        d4, prod4 = etat(d4, c4, 'D1')
        obs['D_pdf'] = pdf(d4, prod4)
        # E : enregistrer (bloc sans ombrage), simuler, ré-enregistrer sans force
        d5, c5 = montage('E', co=co2, u=u2, simuler=False)
        obs['E_patch_ligne_1'] = patch_ligne(d5, api2)
        d5, prod5a = etat(d5, c5, 'E1_avant_simulation')
        cc5 = Calepinage.objects.get(pk=c5.pk)
        simuler_calepinage(cc5, client=_ClientParOrientation(), materiel=MATERIEL, enregistrer=True)
        d5, _ = etat(d5, c5, 'E2_apres_simulation_sans_enregistrer')
        obs['E2_pdf'] = pdf(d5, prod5a)
        obs['E_patch_ligne_2'] = patch_ligne(d5, api2)
        d5, prod5b = etat(d5, c5, 'E3_apres_reenregistrement')
        obs['E3_pdf'] = pdf(d5, prod5b)

        # F : « Générer le devis » sur un calepinage simulé (profil présent)
        from io import StringIO
        from django.core.management import call_command
        from rest_framework_simplejwt.tokens import AccessToken
        from apps.roles.models import Role
        from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
        from apps.ventes.domain.geometrie import layout_hash
        from apps.ventes.models import ShareLink
        co3 = Company.objects.create(nom='Sonde ACON 020 L2 ter', slug='sonde-acon-020-l2-ter')
        CompanyProfile.get(company=co3)
        call_command('seed_catalogue', company_slug=co3.slug, stdout=StringIO())
        role = Role.objects.create(company=co3, nom='Directeur', permissions=list(DIRECTEUR_PERMISSIONS))
        u3 = get_user_model().objects.create_user(username='sonde_acon_020_l2t', password='x', company=co3,
                                                  role=role, role_legacy='responsable')
        api3 = APIClient()
        api3.credentials(HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(u3))
        r = api3.put('/api/django/calepinage/parametres/', {'simulation': sim0}, format='json', **H)
        obs['F_put_reglages'] = r.status_code
        lead_kw = dict(company=co3, nom='Lead F', facture_hiver=Decimal('900'))
        if any(f.name == 'ville' for f in Lead._meta.fields):
            lead_kw['ville'] = 'Casablanca'
        if any(f.name == 'type_installation' for f in Lead._meta.fields):
            lead_kw['type_installation'] = 'residentiel'
        lead3 = Lead.objects.create(**lead_kw)
        lay = _layout(_zone(1, 16, 90.0), _zone(2, 8, 270.0))
        for zone in lay['zones']:
            zone['geometry']['solarAccess'] = {
                'values': [0.9] * zone['geometry']['count'],
                'method': {'horizon': False, 'rangees': False, 'resolution': 'annuelle',
                           'description': 'Accès solaire annuel'},
                'assumptions': {'periode': 'annee'}, 'computedAt': '2026-10-01T10:00:00Z'}
        lay.update({'scenario': 'reseau', 'panelWatt': 710, 'result': {'panels': 24, 'kwc': 17.04}})
        c6 = Calepinage.objects.create(company=co3, lead_id=lead3.pk, titre='F', roof_layout=lay,
                                       layout_hash=layout_hash(lay))
        simuler_calepinage(c6, client=_ClientParOrientation(), materiel=MATERIEL, enregistrer=True)
        rg = api3.post(f'/api/django/calepinage/calepinages/{c6.pk}/generer-devis/', {}, format='json', **H)
        obs['F_generer_http'] = rg.status_code
        dg = getattr(rg, 'data', None) or {}
        did = dg.get('id') if isinstance(dg, dict) else None
        if did is None and isinstance(dg, dict) and isinstance(dg.get('devis'), (int, str)):
            did = dg.get('devis')
        if did is None and isinstance(dg, dict) and isinstance(dg.get('devis'), dict):
            did = dg['devis'].get('id')
        obs['F_generer_corps'] = str(dg)[:240] if not did else ''
        if did:
            d6 = Devis.objects.get(pk=did)
            obs['F_lien'] = str(Calepinage.objects.get(pk=c6.pk).devis_id) == str(d6.pk)
            obs['F_mode'] = d6.mode_installation
            obs['F_regles'] = d6.regles_calcul
            d6, prod6 = etat(d6, c6, 'F1_ne')
            Devis.objects.filter(pk=d6.pk).update(statut='envoye')
            d6 = Devis.objects.get(pk=d6.pk)
            link6 = ShareLink.objects.create(company=co3, devis=d6)
            api2 = api3
            obs['F2_pdf'] = pdf(d6, prod6)
            with mock.patch('apps.ventes.public_views._notify_open'):
                rpub = APIClient().get(f'/api/django/public/proposal/{link6.token}/data/', **H)
            obs['F2_public_http'] = rpub.status_code
            if rpub.status_code == 200:
                pj = rpub.json()
                dims = (pj.get('dimensionnement_options') or {}) if isinstance(pj, dict) else {}
                obs['F2_public_production_options'] = {k: (v or {}).get('production_annuelle_kwh')
                                                       for k, v in dims.items() if isinstance(v, dict)}
                plat = aplatir(pj)
                obs['F2_public_cles_production'] = dict(list({k: v for k, v in plat.items()
                                                              if 'production' in k.lower()}.items())[:6])
                obs['F2_public_egal_bloc_range'] = [k for k, v in plat.items() if prod6 and abs(float(v) - float(prod6)) < 1.0][:6]

        perimants = [e['etape'] for e in A if e['perte_apres'] is None]
        obs['premiere_etape_qui_perime'] = perimants[0] if perimants else None
        obs['ombrage_atteint_pdf_profil_present'] = bool(obs.get('D1_bloc_ombrage')) and bool(obs['D_pdf']['egales_bloc_range'])
        obs['repro'] = bool(perimants)
    finally:
        patch_can.stop()
        patch_mat.stop()
    print(json.dumps(obs, default=str, ensure_ascii=False)[:14000])
    return {'repro': obs.get('repro', False)}
