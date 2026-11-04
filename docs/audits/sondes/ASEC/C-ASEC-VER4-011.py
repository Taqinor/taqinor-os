# flake8: noqa  (sonde de contre-visite vérifie ASEC 04/11, rejouable par scripts/sonde.py — AMET93)
"""D-AARG-3 / D-ASEC-VER-1 (tout geste d'argent = `encaisser`) : un AVOIR s'émet-il sans `encaisser` ?
(A) `devis/<id>/prix-negocie/` (PALIER_VENTE) mode appliquer + `confirmer_avoir` → `domain/negociation.
appliquer_prix_negocie` → `domain/revision.rattacher_aval_financier_revision(confirmer_avoir=True)` →
`facturation_vente.crediter_ecart_de_vente` → `facturation_ops.creer_avoir_facture` (statut EMISE).
(B) `devis/<id>/reviser/` (IsResponsableOrAdmin) puis `accepter` (ventes_valider) avec `confirmer_avoir` dans le
corps : `reviser_devis` ne lit aucun drapeau, `accept_devis` appelle le rattachement SANS confirmation.
Utilisateur au rôle Admin Ventes (canonique, sans `encaisser`, palier responsable) ; témoin : 403 sur
`factures/<id>/creer-avoir/`. Vraies routes, transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ASEC-VER4-011", "sha": "8fb8ba32b",
         "attendu": "rôle sans encaisser : creer-avoir 403 (témoin) ; prix-negocie appliquer+confirmer_avoir 201 avec Avoir statut émise (REPRO) ; reviser+accepter : aucun Avoir (avoir à confirmer) ; attendu sain : 403 sur prix-negocie confirmé",
         "modeles": ["authentication.Company", "ventes.Devis", "ventes.LigneDevis", "Facture", "Avoir"]}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.roles.models import Role
    from apps.roles.permissions_registre import ADMIN_VENTES_PERMISSIONS
    from apps.stock.models import Produit
    from apps.facturation.models import Avoir, Facture
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes.domain.cycle_vie import accept_devis
    from apps.ventes.domain.facturation_ops import emettre_facture
    from apps.ventes.utils.echeancier import creer_facture_tranche
    from apps.ventes.utils.references import create_with_reference
    from apps.ventes.utils.options import option_totaux

    p1 = mock.patch('apps.ventes.domain.cycle_vie._send_acceptance_emails')
    p2 = mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf')
    p1.start(); p2.start()
    try:
        co = Company.objects.create(nom='Sonde ASEC VER4-011', slug='sonde-asec-ver4-011')
        setup = get_user_model().objects.create_user(username='sonde-v4-011-setup', password='x', company=co,
                                                     role_legacy='responsable')
        role = Role.objects.create(company=co, nom='Admin Ventes (sonde 011)', permissions=list(ADMIN_VENTES_PERMISSIONS))
        u = get_user_model().objects.create_user(username='sonde-v4-011-av', password='x', company=co, role=role,
                                                 role_legacy='responsable')
        lignes = [('Panneaux 10 %', '1', '9600.00', '10'), ('Installation 20 %', '1', '36643.50', '20')]
        n = [0]

        def vente(nom):
            n[0] += 1
            cl = Client.objects.create(company=co, nom=nom, prenom='V4-011', email=f'v4-011-{n[0]}@example.invalid')
            d = Devis.objects.create(company=co, reference=f'DEV-SONDE-V4-011-{n[0]}', client=cl, statut='envoye',
                                     taux_tva=Decimal('20.00'), created_by=setup)
            for i, (des, q, pu, t) in enumerate(lignes):
                pr = Produit.objects.create(company=co, nom=des, sku=f'V4011-{n[0]}-{i}', prix_vente=Decimal(pu),
                                            prix_achat=Decimal('1'), quantite_stock=100)
                LigneDevis.objects.create(devis=d, produit=pr, designation=des, quantite=Decimal(q),
                                          prix_unitaire=Decimal(pu), taux_tva=Decimal(t))
            d = accept_devis(devis=Devis.objects.get(pk=d.pk), user=setup, nom='Client 011',
                             date_acceptation=date.today(), option='sans_batterie')
            # Vente entièrement facturée (factures ÉMISES), par le compte de mise en place.
            for _ in range(10):
                br = Facture.objects.filter(devis=d, statut=Facture.Statut.BROUILLON).order_by('pk').first()
                try:
                    if br is not None:
                        emettre_facture(br, user=setup)
                    else:
                        creer_facture_tranche(Devis.objects.get(pk=d.pk), setup, co, create_with_reference)
                except ValueError:
                    break
            return Devis.objects.get(pk=d.pk)

        api = APIClient()
        api.force_authenticate(u)
        B = '/api/django/ventes'
        obs = {'role_a_encaisser': 'encaisser' in role.permissions, 'menu_tier': u.menu_tier}

        # ── (A) prix-negocie ──
        va = vente('Vente A')
        fa = list(Facture.objects.filter(devis=va).values_list('id', 'reference', 'statut', 'montant_ttc'))
        obs['A_ttc_v1'] = str(option_totaux(va)['ttc'])
        obs['A_factures'] = [(r, s, str(m)) for _, r, s, m in fa]
        fid = next((i for i, _r, s, _m in fa if s != Facture.Statut.BROUILLON), None)
        r0 = api.post(f'{B}/factures/{fid}/creer-avoir/', {'montant_ttc': '100.00', 'motif': 'témoin'},
                      format='json', HTTP_HOST='localhost')
        obs['temoin_creer_avoir'] = r0.status_code
        avoirs_avant = Avoir.objects.filter(company=co).count()
        ra = api.post(f'{B}/devis/{va.pk}/prix-negocie/', {'mode': 'appliquer', 'prix_ttc': '49000'},
                      format='json', HTTP_HOST='localhost')
        obs['A_sans_confirmation'] = (ra.status_code, ra.data.get('code') if hasattr(ra.data, 'get') else None)
        rb = api.post(f'{B}/devis/{va.pk}/prix-negocie/',
                      {'mode': 'appliquer', 'prix_ttc': '49000', 'confirmer_avoir': True},
                      format='json', HTTP_HOST='localhost')
        obs['A_confirme'] = rb.status_code
        obs['A_confirme_detail'] = (rb.data if rb.status_code >= 400 else
                                    {k: rb.data.get(k) for k in ('devis_v2', 'total_ttc', 'regularisation')})
        av_a = list(Avoir.objects.filter(company=co).values_list('reference', 'statut', 'montant_ttc',
                                                                   'facture__reference', 'created_by__username'))
        obs['A_avoirs'] = [(a, s, str(m), f, c) for a, s, m, f, c in av_a]
        obs['A_avoirs_crees'] = len(av_a) - avoirs_avant

        # ── (B) reviser + accepter (confirmer_avoir ignoré ?) ──
        vb = vente('Vente B')
        nb0 = Avoir.objects.filter(company=co).count()
        r1 = api.post(f'{B}/devis/{vb.pk}/reviser/', {'confirmer_avoir': True}, format='json', HTTP_HOST='localhost')
        obs['B_reviser'] = r1.status_code
        if r1.status_code == 201:
            v2 = Devis.objects.get(pk=r1.data['id'])
            lg = v2.lignes.get(designation='Installation 20 %')
            LigneDevis.objects.filter(pk=lg.pk).update(prix_unitaire=Decimal('30000'))
            Devis.objects.filter(pk=v2.pk).update(statut='envoye')
            r2 = api.post(f'{B}/devis/{v2.pk}/accepter/',
                          {'nom': 'Client 011', 'option': 'sans_batterie', 'confirmer_avoir': True},
                          format='json', HTTP_HOST='localhost')
            obs['B_accepter'] = r2.status_code
            obs['B_accepter_detail'] = r2.data if r2.status_code >= 400 else None
            v2.refresh_from_db()
            obs['B_v2_statut'] = v2.statut
            obs['B_ttc_v2'] = str(option_totaux(v2)['ttc'])
        obs['B_avoirs_crees'] = Avoir.objects.filter(company=co).count() - nb0
        emise = Avoir.Statut.EMISE if hasattr(Avoir, 'Statut') else 'emise'
        repro = (not obs['role_a_encaisser'] and r0.status_code == 403 and rb.status_code == 201
                 and any(s == emise for _a, s, _m, _f, _c in av_a))
        print(f'obs={obs}')
        return {'repro': repro, **obs}
    finally:
        p1.stop(); p2.stop()
