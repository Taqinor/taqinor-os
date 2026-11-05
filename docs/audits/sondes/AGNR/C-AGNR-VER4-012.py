# flake8: noqa  (sonde de contre-visite vérifie AGNR du 04/11, rejouable par scripts/sonde.py — AMET93)
"""C-AGNR-VER4-010, jumeaux : l'échéancier mixte stocké (8 000 MAD + 40 % + reste) n'est re-contrôlé par la règle
d'AGNR49 que quand le corps porte `echeancier` (sérialiseur) ou à la copie (`creation_clone.echeancier_pour_copie`).
(1) `domain/negociation.py::appliquer_prix_negocie` : `reviser_devis` recopie l'échéancier AU TTC D'AVANT la remise,
puis pose `remise_globale` sans re-contrôle → V2 acceptée à 9 000 ; `jalons_paiement_devis(V2)` ?
(2) lecteurs PDF agricole / résidentiel sur l'état négatif (PATCH remise de VER4-010) :
`quote_engine/conditions_commerciales.py::repartition_paiement` (`builder.py` `montants_tranches`) et
`quote_engine/agricole/pages.py::_echeancier` — négatif ou borné ?
(3) autre écrivain : DELETE d'une ligne via `LigneDevisViewSet` (TTC baissé). Vraie route, transaction annulée."""
SONDE = {"constat": "C-AGNR-VER4-012", "sha": "4cd568403",
         "attendu": "(1) prix-negocie 201, jalons V2 : dernière tranche < 0 ; (2) jalons < 0 mais repartition_paiement "
                    "bornée (aucune case < 0, tranche matériel tronquée) ; (3) DELETE 204, jalons : dernière < 0",
         "modeles": ["authentication.Company", "authentication.User", "crm.Client", "stock.Produit",
                     "ventes.Devis", "ventes.LigneDevis", "facturation.Facture"]}


def sonde(ctx):
    import hashlib, inspect, re
    from datetime import date
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes.utils import echeancier as ech_mod
    from apps.ventes.utils.echeancier import jalons_paiement_devis
    from apps.ventes.utils.options import option_totaux
    from apps.ventes.domain import negociation as nego_mod
    from apps.ventes.domain import revision as rev_mod
    from apps.ventes.quote_engine import conditions_commerciales as cc_mod
    from apps.ventes.quote_engine.conditions_commerciales import repartition_paiement, tranches_echeancier_en_montant
    from apps.ventes.domain.cycle_vie import accept_devis

    # Code servi par le conteneur : empreintes des fichiers lus (à comparer à origin/main 4cd568403).
    empreintes = {m.__name__.rsplit('.', 1)[-1]: hashlib.md5(open(inspect.getfile(m), 'rb').read()).hexdigest()[:10]
                  for m in (ech_mod, nego_mod, rev_mod, cc_mod)}
    print(f'empreintes={empreintes}')

    mois = timezone.now().strftime('%Y%m')
    co = Company.objects.create(nom='Sonde AGNR VER4-012', slug='sonde-agnr-ver4-012')
    u = get_user_model().objects.create_user(username='sonde-agnr-ver4-012', password='x', company=co,
                                             role_legacy='admin')
    cl = Client.objects.create(company=co, nom='Client', prenom='VER4012', email='sonde-agnr-ver4-012@example.invalid')
    api = APIClient()
    api.force_authenticate(u)
    B = '/api/django/ventes'
    seq = [0]

    def devis(mode):
        seq[0] += 1
        d = Devis.objects.create(company=co, reference=f'DEV-{mois}-94{20 + seq[0]}', client=cl,
                                 statut=Devis.Statut.BROUILLON, taux_tva=Decimal('20.00'), mode_installation=mode)
        lignes = {}
        for nom, pu, q, tva in (('Panneau', '1000', '10', '10.00'), ('Onduleur', '5000', '1', '20.00')):
            p = Produit.objects.create(company=co, nom=nom, sku=f'S412-{seq[0]}-{nom}', prix_vente=Decimal(pu),
                                       quantite_stock=100)
            lignes[nom] = LigneDevis.objects.create(devis=d, produit=p, designation=nom, quantite=Decimal(q),
                                                    prix_unitaire=Decimal(pu), remise=Decimal('0'),
                                                    taux_tva=Decimal(tva))
        return d, lignes

    CORPS_CI = [{'libelle': 'Commande', 'type': 'acompte', 'unite': 'montant', 'pct_or_montant': 8000},
                {'libelle': 'Livraison', 'jalon': 'livraison_materiel', 'unite': 'pct', 'pct_or_montant': 40},
                {'libelle': 'Réception', 'jalon': 'reception_definitive', 'unite': 'pct', 'pct_or_montant': 10}]
    CORPS_STD = [{'libelle': 'Acompte', 'type': 'acompte', 'unite': 'montant', 'pct_or_montant': 8000},
                 {'libelle': 'Matériel', 'type': 'materiel', 'unite': 'pct', 'pct_or_montant': 40},
                 {'libelle': 'Solde', 'type': 'solde', 'unite': 'pct', 'pct_or_montant': 10}]

    def patch_ech(d, corps):
        r = api.patch(f'{B}/devis/{d.pk}/', {'echeancier': corps}, format='json', HTTP_HOST='localhost')
        d.refresh_from_db()
        return r.status_code

    def montants(d):
        return [str(j['montant_ttc']) for j in jalons_paiement_devis(d)]

    def neg(liste):
        return any(Decimal(x) < 0 for x in liste)

    out = {}

    # ── (1) prix-negocie ──────────────────────────────────────────────────
    try:
        with transaction.atomic():
            d1, _l = devis('industriel')
            p1 = patch_ech(d1, CORPS_CI)
            Devis.objects.filter(pk=d1.pk).update(statut=Devis.Statut.ENVOYE)
            with mock.patch('apps.ventes.domain.cycle_vie._send_acceptance_emails'), \
                    mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
                v1 = accept_devis(devis=Devis.objects.get(pk=d1.pk), user=u, nom='Client VER4012',
                                  date_acceptation=date.today(), option='sans_batterie')
                v1 = Devis.objects.get(pk=v1.pk)
                ttc_v1 = str(option_totaux(v1)['ttc'])
                m_v1 = montants(v1)
                url = f'{B}/devis/{v1.pk}/prix-negocie/'
                saisie = {'prix_ttc': '9000'}
                ra = api.post(url, {'mode': 'apercu', **saisie}, format='json', HTTP_HOST='localhost')
                if ra.status_code != 200 and isinstance(ra.data, dict) and ra.data.get('prix_atteignables'):
                    saisie = {'prix_ttc': ra.data['prix_atteignables'][0]}
                    ra = api.post(url, {'mode': 'apercu', **saisie}, format='json', HTTP_HOST='localhost')
                rp = api.post(url, {'mode': 'appliquer', 'confirmer_avoir': True, **saisie}, format='json',
                              HTTP_HOST='localhost')
            print(f'(1) patch_ech={p1} statut_v1={v1.statut} ttc_v1={ttc_v1} ech_v1={v1.echeancier} jalons_v1={m_v1} '
                  f'saisie={saisie} apercu={ra.status_code} {dict(ra.data) if hasattr(ra, "data") else ""} '
                  f'appliquer={rp.status_code} {dict(rp.data) if rp.status_code >= 400 else ""}')
            if rp.status_code == 201:
                v2 = Devis.objects.get(pk=rp.data['devis_v2']['id'])
                m_v2 = montants(v2)
                tm = tranches_echeancier_en_montant(v2)
                ttc_v2 = option_totaux(v2)['ttc']
                rep = repartition_paiement(ttc_v2, {'acompte': 30, 'solde': 10}, tm)
                print(f'(1) V2 {v2.reference} statut={v2.statut} regles={v2.regles_calcul} remise={v2.remise_globale} '
                      f'ttc_v2={ttc_v2} ech_v2={v2.echeancier} jalons_v2={m_v2} '
                      f'repartition={ {k: rep[k] for k in ("acompte", "materiel", "solde", "pct_a", "pct_m", "pct_s")} }')
                out['1'] = {'appliquer': 201, 'jalons_v2': m_v2, 'negatif': neg(m_v2)}
            else:
                out['1'] = {'appliquer': rp.status_code}
            transaction.set_rollback(True)
    except Exception as exc:  # noqa
        print(f'(1) ERREUR {type(exc).__name__}: {exc}')
        out['1'] = {'erreur': f'{type(exc).__name__}: {exc}'}

    # ── (2) lecteurs agricole / résidentiel sur l'état négatif ───────────
    for mode in ('agricole', 'residentiel'):
        try:
            with transaction.atomic():
                d2, _l = devis(mode)
                p2 = patch_ech(d2, CORPS_STD)
                r2 = api.patch(f'{B}/devis/{d2.pk}/', {'remise_globale': '50'}, format='json', HTTP_HOST='localhost')
                d2.refresh_from_db()
                ttc2 = option_totaux(d2)['ttc']
                m2 = montants(d2)
                tm = tranches_echeancier_en_montant(d2)
                rep_direct = repartition_paiement(ttc2, {'acompte': 30, 'solde': 10}, tm)
                info = {'patch_ech': p2, 'patch_remise': r2.status_code, 'ttc': str(ttc2), 'ech': d2.echeancier,
                        'jalons': m2,
                        'repartition_direct': {k: rep_direct[k] for k in ('acompte', 'materiel', 'solde', 'pct_a',
                                                                          'pct_m', 'pct_s', 'deux_cases')}}
                try:
                    from apps.ventes.quote_engine.builder import build_quote_data
                    data = build_quote_data(d2)
                    info['builder_montants_tranches'] = {b: {k: (data['montants_tranches'].get(b) or {}).get(k)
                                                             for k in ('total', 'acompte', 'materiel', 'solde',
                                                                       'pct_a', 'pct_m', 'pct_s')}
                                                         for b in ('sans', 'avec')}
                    info['builder_payment_terms'] = data.get('payment_terms')
                    info['regles_echeancier_historique'] = data.get('regles_echeancier_historique')
                    if mode == 'agricole':
                        from apps.ventes.quote_engine.agricole.pages import _echeancier
                        html = _echeancier(data, 'fr')
                        info['agricole_echeancier_texte'] = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' | ', html)).strip()
                except Exception as exc:  # noqa
                    info['builder_erreur'] = f'{type(exc).__name__}: {exc}'
                print(f'(2) {mode} {info}')
                rep_neg = any(Decimal(str(rep_direct[k])) < 0 for k in ('acompte', 'materiel', 'solde'))
                out[f'2_{mode}'] = {'jalons': m2, 'jalons_negatif': neg(m2), 'repartition_negatif': rep_neg,
                                    'repartition': info['repartition_direct'],
                                    'builder': info.get('builder_montants_tranches') or info.get('builder_erreur')}
                transaction.set_rollback(True)
        except Exception as exc:  # noqa
            print(f'(2) {mode} ERREUR {type(exc).__name__}: {exc}')
            out[f'2_{mode}'] = {'erreur': f'{type(exc).__name__}: {exc}'}

    # ── (3) DELETE d'une ligne ───────────────────────────────────────────
    try:
        with transaction.atomic():
            d3, lignes = devis('industriel')
            p3 = patch_ech(d3, CORPS_CI)
            avant = montants(d3)
            r3 = api.delete(f'{B}/devis-lignes/{lignes["Onduleur"].pk}/', HTTP_HOST='localhost')
            d3.refresh_from_db()
            apres = montants(d3)
            print(f'(3) patch_ech={p3} ech={d3.echeancier} jalons_avant={avant} delete={r3.status_code} '
                  f'{getattr(r3, "data", "") if r3.status_code >= 400 else ""} ttc_apres={option_totaux(d3)["ttc"]} '
                  f'jalons_apres={apres}')
            out['3'] = {'delete': r3.status_code, 'jalons_apres': apres, 'negatif': neg(apres)}
            transaction.set_rollback(True)
    except Exception as exc:  # noqa
        print(f'(3) ERREUR {type(exc).__name__}: {exc}')
        out['3'] = {'erreur': f'{type(exc).__name__}: {exc}'}

    out['empreintes'] = empreintes
    out['repro'] = bool((out.get('1') or {}).get('negatif') or (out.get('3') or {}).get('negatif'))
    return out
