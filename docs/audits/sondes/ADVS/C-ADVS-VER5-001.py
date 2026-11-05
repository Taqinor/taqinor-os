# flake8: noqa  (sonde de verification VER5, rejouable par scripts/sonde.py)
"""VER5-001 (ADVS26, hors perimetre « share-link ne rejuge pas la garde, tache a numeroter ») — un brouillon ne
coherent (lead 650 kWh / facture 1 200), puis la fiche du lead corrigee en 46 kWh/mois pour 10 000 MAD de facture
d'hiver (ce que la regle fondateur du 30/09 refuse de chiffrer) : replace-lines du brouillon repond 409, mais
POST share-link {envoi: true} l'envoie quand meme (devis envoye, chiffre sur le kWh contredit).
repro=True = l'ecart existe. Societe neuve, transaction annulee."""
SONDE = {"constat": "C-ADVS-003", "sha": "2781a2049",
         "attendu": "share-link envoi d'un brouillon devenu incoherent : 409 kwh_incoherent_factures, reste brouillon "
                    "(defaut : 200/201 + statut envoye)",
         "modeles": ["ventes.Devis", "ventes.LigneDevis", "ventes.ShareLink", "crm.Lead"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis
    from apps.ventes.etude_horaire import controle_kwh_declare_du_devis
    obs = {}
    try:
        from apps.ventes.selectors_calepinage import refus_kwh_declare_du_devis  # ADVS26 present ?
        obs['code_advs26_present'] = True
    except Exception as e:
        obs['code_advs26_present'] = repr(e)[:120]
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS VER5 001', slug='sonde-advs-ver5-001')
    u = U.objects.create_user(username='sonde-advs-ver5-001', password='x', role_legacy='admin', company=c,
                              email='vendeur-ver5-001@example.invalid')
    lead = Lead.objects.create(company=c, nom='Kwh', prenom='Corrige', email='client-ver5-001@example.invalid',
                               telephone='+212600005001', ville='Casablanca', type_installation='residentiel',
                               conso_mensuelle_kwh=650, facture_hiver=Decimal('1200'))
    pan = Produit.objects.create(company=c, nom='Panneau Jinko 550W', sku='VER5001-PAN', prix_vente=Decimal('1100'),
                                 prix_achat=Decimal('1'), tva=Decimal('20'), quantite_stock=100)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 5kW Monophasé', sku='VER5001-OND',
                                 prix_vente=Decimal('14000'), prix_achat=Decimal('1'), tva=Decimal('20'),
                                 quantite_stock=100)
    api = APIClient()
    api.force_authenticate(u)

    def appel(url, corps, methode='post'):
        try:
            with transaction.atomic():
                r = getattr(api, methode)(url, corps, format='json', HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace')
            try:
                return r.status_code, json.loads(txt)
            except Exception:
                return r.status_code, {'_brut': txt[:200]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}

    lignes = [{'produit': pan.id, 'designation': pan.nom, 'quantite': '8', 'prix_unitaire': '1100.00',
               'taux_tva': '20'},
              {'produit': ond.id, 'designation': ond.nom, 'quantite': '1', 'prix_unitaire': '14000.00',
               'taux_tva': '20'}]
    s0, r0 = appel('/api/django/ventes/devis/atomic/', {'lead': lead.id, 'taux_tva': '20.00', 'lignes': lignes})
    obs['atomic_coherent'] = {'http': s0, 'detail': str(r0.get('detail'))[:120] if isinstance(r0, dict) else None}
    dv = Devis.objects.filter(company=c, lead=lead).first()
    if dv is None:
        obs['_arret'] = 'aucun brouillon cree'
        return {'repro': False, 'observe': obs}
    obs['controle_avant'] = (controle_kwh_declare_du_devis(dv) or {}).get('coherent')
    # Fiche du lead corrigee (PATCH, chemin reel), puis a defaut ecriture directe.
    sp, rp = appel(f'/api/django/crm/leads/{lead.id}/',
                   {'conso_mensuelle_kwh': 46, 'facture_hiver': '10000'}, methode='patch')
    obs['patch_lead'] = {'http': sp, 'extrait': {k: rp.get(k) for k in ('detail', 'conso_mensuelle_kwh', 'code')}
                         if isinstance(rp, dict) else None}
    lead.refresh_from_db()
    if int(lead.conso_mensuelle_kwh or 0) != 46:
        Lead.objects.filter(pk=lead.pk).update(conso_mensuelle_kwh=46, facture_hiver=Decimal('10000'))
        obs['lead_ecrit_directement'] = True
    dv = Devis.objects.get(pk=dv.pk)
    ctl = controle_kwh_declare_du_devis(dv) or {}
    obs['controle_apres'] = {k: ctl.get(k) for k in ('coherent', 'ratio', 'kwh_declare', 'kwh_factures')}
    s1, r1 = appel(f'/api/django/ventes/devis/{dv.id}/replace-lines/', {'lignes': lignes})
    obs['replace_lines'] = {'http': s1, 'code': r1.get('code') if isinstance(r1, dict) else None}
    dv = Devis.objects.get(pk=dv.pk)
    s2, r2 = appel(f'/api/django/ventes/devis/{dv.id}/share-link/', {'envoi': True})
    dv = Devis.objects.get(pk=dv.pk)
    obs['share_link_envoi'] = {'http': s2, 'code': r2.get('code') if isinstance(r2, dict) else None,
                               'detail': str(r2.get('detail'))[:160] if isinstance(r2, dict) else None,
                               'statut_apres': dv.statut}
    try:
        from apps.crm.devis_selectors import conso_mensuelle_kwh_pour_devis
        obs['kwh_lu_par_le_rendu'] = str(conso_mensuelle_kwh_pour_devis(dv))
    except Exception as e:
        obs['kwh_lu_par_le_rendu'] = repr(e)[:120]
    try:
        from apps.ventes.quote_engine.builder import build_quote_data
        with transaction.atomic():
            d = build_quote_data(dv)
        obs['pdf_conso_economie'] = {k: d.get(k) for k in d
                                     if any(m in k.lower() for m in ('conso', 'econom', 'saving', 'roi', 'facture'))
                                     and not isinstance(d.get(k), (dict, list))}
    except Exception as e:
        obs['pdf_conso_economie'] = repr(e)[:200]
    repro = (ctl.get('coherent') is False and s2 in (200, 201) and dv.statut == 'envoye')
    return {'repro': repro, 'observe': obs}
