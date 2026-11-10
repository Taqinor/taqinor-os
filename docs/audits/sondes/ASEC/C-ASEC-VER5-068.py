# flake8: noqa  (sonde de contre-visite vérifie ASEC, seconde lentille 10/11 — rejouable par scripts/sonde.py, AMET93)
"""D-ASEC-1 / D-ASEC-VER-1 (tout geste d'argent, avoirs compris = `encaisser`) : l'AVOIR DE RÉVISION s'émet-il
sans `encaisser` ? Porte : `devis/<id>/confirmer-avoir-revision/` (ATOT62, 27ec28a89 ; `PALIER_VENTE`, aucune
`PeutEncaisser`) → `domain/revision.rattacher_aval_financier_revision(confirmer_avoir=True)` →
`facturation_vente.crediter_ecart_de_vente` → `facturation_ops.creer_avoir_facture` (statut EMISE, numéroté).
Compte au rôle SYSTÈME « Admin Ventes » semé comme `init_roles` (get_or_create nom + permissions du registre
vivant + périmètre), palier responsable, sans `encaisser`. Parcours par les vraies routes : reviser (V1 acceptée
et facturée) → V2 moins chère → accepter → confirmer-avoir-revision. Témoin : même compte, porte sœur ASEC68
`prix-negocie` appliquer + confirmer_avoir ⇒ 403. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ASEC-VER5-068", "sha": "c1a99568a",
         "attendu": "Admin Ventes sans encaisser : témoin prix-negocie confirmé 403 ; reviser 201, accepter V2 200, "
                    "confirmer-avoir-revision 200 avec un Avoir statut émis numéroté sur la facture de la V1 (REPRO) ; "
                    "attendu sain : 403 droit encaisser, aucun avoir",
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
    from apps.roles.permissions_registre import (
        ADMIN_VENTES_PERMISSIONS, ROLE_ADMIN_VENTES, SYSTEM_ROLE_PERIMETRES)
    from apps.stock.models import Produit
    from apps.facturation.models import Avoir, Facture
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes.domain.cycle_vie import accept_devis
    from apps.ventes.domain.facturation_ops import emettre_facture
    from apps.ventes.utils.echeancier import creer_facture_tranche
    from apps.ventes.utils.references import create_with_reference
    from apps.ventes.utils.options import option_totaux
    from core.numbering import est_reference_provisoire

    p1 = mock.patch('apps.ventes.domain.cycle_vie._send_acceptance_emails')
    p2 = mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf')
    p1.start(); p2.start()
    try:
        co = Company.objects.create(nom='Sonde ASEC VER5-068', slug='sonde-asec-ver5-068')
        U = get_user_model()
        setup = U.objects.create_user(username='sonde-v5-068-setup', password='x', company=co,
                                      role_legacy='responsable')
        # Rôle système RÉEL, semé exactement comme init_roles (Command.handle l.91-138).
        role, _cree = Role.objects.get_or_create(
            company=co, nom=ROLE_ADMIN_VENTES,
            defaults={'permissions': list(ADMIN_VENTES_PERMISSIONS), 'est_systeme': True})
        role.perimetre = SYSTEM_ROLE_PERIMETRES.get(ROLE_ADMIN_VENTES)
        role.save(update_fields=['perimetre'])
        u = U.objects.create_user(username='sonde-v5-068-av', password='x', company=co, role=role,
                                  role_legacy='responsable')
        lignes = [('Panneaux 10 %', '1', '9600.00', '10'), ('Installation 20 %', '1', '36643.50', '20')]
        n = [0]

        def vente(nom):
            n[0] += 1
            cl = Client.objects.create(company=co, nom=nom, prenom='V5-068', email=f'v5-068-{n[0]}@example.invalid')
            d = Devis.objects.create(company=co, reference=f'DEV-SONDE-V5-068-{n[0]}', client=cl,
                                     statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20.00'), created_by=setup)
            for i, (des, q, pu, t) in enumerate(lignes):
                pr = Produit.objects.create(company=co, nom=des, sku=f'V5068-{n[0]}-{i}', prix_vente=Decimal(pu),
                                            prix_achat=Decimal('1'), quantite_stock=100)
                LigneDevis.objects.create(devis=d, produit=pr, designation=des, quantite=Decimal(q),
                                          prix_unitaire=Decimal(pu), taux_tva=Decimal(t))
            d = accept_devis(devis=Devis.objects.get(pk=d.pk), user=setup, nom='Client 068',
                             date_acceptation=date.today(), option='sans_batterie')
            for _ in range(10):  # vente entièrement facturée, factures ÉMISES (compte de mise en place)
                br = Facture.objects.filter(devis=d, statut=Facture.Statut.BROUILLON).order_by('pk').first()
                try:
                    if br is not None:
                        emettre_facture(br, user=setup)
                    else:
                        creer_facture_tranche(Devis.objects.get(pk=d.pk), setup, co, create_with_reference)
                except ValueError:
                    break
            return Devis.objects.get(pk=d.pk)

        def factures(d):
            return [(f.reference, f.statut, str(f.montant_ttc))
                    for f in Facture.objects.filter(company=co, devis__in=[d]).order_by('pk')]

        api = APIClient()
        api.force_authenticate(u)
        B = '/api/django/ventes'
        H = {'format': 'json', 'HTTP_HOST': 'localhost'}
        u.refresh_from_db()
        obs = {'role': (role.nom, role.est_systeme, role.perimetre), 'menu_tier': u.menu_tier,
               'role_a_encaisser': 'encaisser' in (role.permissions or []),
               'codes_ventes_du_role': sorted(c for c in role.permissions if c.startswith('ventes_') or c == 'encaisser')}

        # ── Témoin ASEC68 : prix-negocie confirmé ⇒ 403 attendu ──
        vt = vente('Vente témoin')
        nt0 = Avoir.objects.filter(company=co).count()
        rt = api.post(f'{B}/devis/{vt.pk}/prix-negocie/',
                      {'mode': 'appliquer', 'prix_ttc': '49000', 'confirmer_avoir': True}, **H)
        obs['temoin_prix_negocie'] = (rt.status_code, getattr(rt, 'data', None) if rt.status_code >= 400 else None)
        obs['temoin_avoirs_crees'] = Avoir.objects.filter(company=co).count() - nt0

        # ── Parcours : V1 acceptée + facturée → reviser → V2 moins chère → accepter → confirmer ──
        v1 = vente('Vente révisée')
        obs['v1_ttc'] = str(option_totaux(v1)['ttc'])
        obs['v1_factures'] = factures(v1)
        n0 = Avoir.objects.filter(company=co).count()
        etape, code = None, None
        r1 = api.post(f'{B}/devis/{v1.pk}/reviser/', {}, **H)
        obs['reviser'] = r1.status_code
        rc = None
        if r1.status_code != 201:
            etape, code = 'reviser', r1.status_code
        else:
            v2 = Devis.objects.get(pk=r1.data['id'])
            # Édition de la V2 brouillon (même geste que le test ATOT22 : prix de ligne baissé).
            LigneDevis.objects.filter(devis=v2, designation='Installation 20 %').update(prix_unitaire=Decimal('30000'))
            Devis.objects.filter(pk=v2.pk).update(statut=Devis.Statut.ENVOYE)
            r2 = api.post(f'{B}/devis/{v2.pk}/accepter/', {'nom': 'Client 068', 'option': 'sans_batterie'}, **H)
            obs['accepter_v2'] = (r2.status_code, r2.data if r2.status_code >= 400 else None)
            v2.refresh_from_db()
            obs['v2_statut'], obs['v2_ttc'] = v2.statut, str(option_totaux(v2)['ttc'])
            obs['avoirs_apres_accepter'] = Avoir.objects.filter(company=co).count() - n0
            if r2.status_code != 200 or v2.statut != Devis.Statut.ACCEPTE:
                etape, code = 'accepter_v2', r2.status_code
            else:
                rc = api.post(f'{B}/devis/{v2.pk}/confirmer-avoir-revision/', {}, **H)
                obs['confirmer_avoir_revision'] = (rc.status_code, rc.data)
                if rc.status_code != 200:
                    etape, code = 'confirmer_avoir_revision', rc.status_code
        av = [(a.reference, a.statut, str(a.montant_ttc), a.facture.reference,
               getattr(a.created_by, 'username', None), a.type)
              for a in Avoir.objects.filter(company=co).select_related('facture', 'created_by').order_by('pk')[n0:]]
        obs['avoirs_parcours'] = av
        obs['refus_avant_porte'] = (etape, code) if etape and etape != 'confirmer_avoir_revision' else None
        repro = bool(not obs['role_a_encaisser'] and rt.status_code == 403 and rc is not None
                     and rc.status_code == 200
                     and any(s == Avoir.Statut.EMISE and ref and not est_reference_provisoire(ref)
                             for ref, s, _m, _f, _c, _t in av))
        print(f'obs={obs}')
        return {'repro': repro, **obs}
    finally:
        p1.stop(); p2.stop()
