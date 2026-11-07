# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K62 — le « déjà sorti » du chantier compte deux fois une pose F11 qu'ASTK258 a nettée de la vente.
Code exécuté = celui du worktree : les fichiers sondés de la pile (`field_capture.py`, `services.py`,
`selectors_sorties_vente.py`…) ont le même md5 que 6ffa876688 (ASTK257/ASTK258 présents) ; la sonde le vérifie.
(R) devis accepté de 10 panneaux (stock 30), chantier, acompte par `generer-facture` + `emettre` (SORTIE 10
sous la référence du devis, réservation soldée), puis F11 de 10 par `valider-consommation` (ASTK258 : 0 sortie).
On lit les quatre « déjà sorti », la réservation d'écart d'une V2 à 15 (`_poser_reservation_ecart`), et un retour
chantier de 15 par la vraie route. (T) témoin : même chantier sans acompte, F11 de 10 ⇒ 10 sortis, lus 10."""
SONDE = {"constat": "C-AAPV-082", "sha": "6ffa876688",
         "attendu": "repro si R : Σ SORTIE 10 (ASTK258 tient) mais déjà-sorti lu 20 / 20 / 20 et besoin deja_sorti 20 ; écart V2 15 réservé 0 (attendu 5) ; retour 15 accepté (attendu 409) ; T : 10 partout",
         "modeles": ["stock.MouvementStock", "stock.Produit", "ventes.Facture", "installations.Intervention",
                     "installations.MaterielConsommation", "installations.StockReservation",
                     "installations.RetourMateriel"]}


def sonde(ctx):
    from apps.crm import stages
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db.models import Sum
    from django.test import TestCase
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    import apps.ventes.selectors as vsel
    import apps.installations.field_capture as fc
    import apps.installations.services as isvc
    from apps.installations import selectors as isel
    from apps.installations.models import Intervention, StockReservation
    from apps.stock.models import MouvementStock, Produit
    from apps.stock.services import mouvement_type_sortie, compute_besoin_materiel
    from apps.ventes.models import Devis, LigneDevis
    deja_la = {'sorties_de_la_vente': hasattr(vsel, 'sorties_de_la_vente'),
               '_deja_sorti_vente': hasattr(fc, '_deja_sorti_vente')}
    assert all(deja_la.values()), ('pile antérieure à ASTK257/258', deja_la)
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 082', slug='sonde-aapv-082')
    u = get_user_model().objects.create_user(username='sonde_aapv_082', password='x', company=co,
                                             role_legacy='admin')
    api = APIClient()
    api.force_authenticate(u)

    def cas(tag, acompte):
        p = Produit.objects.create(company=co, nom=f'Panneau AAPV82 {tag}', sku=f'AAPV-082-{tag}',
                                   prix_vente=Decimal('100'), quantite_stock=30, tva=Decimal('20.00'))
        cl = Client.objects.create(company=co, nom=f'Site {tag}', prenom='Client', email=f'aapv82{tag}@example.invalid')
        lead = Lead.objects.create(company=co, nom=f'Site {tag}', prenom='Client', stage=stages.SIGNED,
                                   type_installation='residentiel')
        d = Devis.objects.create(company=co, reference=f'DEV-AAPV82-{tag}', client=cl, lead=lead,
                                 statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'), mode_installation='residentiel')
        LigneDevis.objects.create(devis=d, produit=p, designation='Panneau', quantite=Decimal('10'),
                                  prix_unitaire=Decimal('100'), taux_tva=Decimal('20.00'))
        inst, _ = isvc.create_installation_from_devis(d, u, co)

        def sorties():
            return MouvementStock.objects.filter(produit=p, type_mouvement=mouvement_type_sortie()).aggregate(
                t=Sum('quantite'))['t'] or 0
        o = {}
        if acompte:
            with TestCase.captureOnCommitCallbacks(execute=True):
                r1 = api.post(f'/api/django/ventes/devis/{d.id}/generer-facture/', {}, format='json', **H)
            fac = d.factures.order_by('id').first()
            if fac is not None and fac.statut == 'brouillon':
                with TestCase.captureOnCommitCallbacks(execute=True):
                    api.post(f'/api/django/ventes/factures/{fac.id}/emettre/', {}, format='json', **H)
                fac.refresh_from_db()
            o['facture'] = (r1.status_code, getattr(fac, 'type_facture', None), getattr(fac, 'statut', None))
        o['sorties_avant_f11'] = str(sorties())
        o['resa_avant_f11'] = list(StockReservation.objects.filter(installation=inst, produit=p).values_list(
            'quantite', 'active', 'consomme'))
        itv = Intervention.objects.create(company=co, installation=inst)
        api.get(f'/api/django/installations/interventions/{itv.id}/consommation/', **H)
        with TestCase.captureOnCommitCallbacks(execute=True):
            r2 = api.post(f'/api/django/installations/interventions/{itv.id}/valider-consommation/', {},
                          format='json', **H)
        p.refresh_from_db()
        besoin = next((e for e in compute_besoin_materiel(inst) if e['produit_id'] == p.id), {})
        o.update({'valider_f11': r2.status_code, 'sorties_apres_f11': str(sorties()), 'stock': str(p.quantite_stock),
                  'sorties_de_la_vente': str(vsel.sorties_de_la_vente(d.id, co).get(p.id)),
                  'quantite_deja_sortie_chantier': isvc.quantite_deja_sortie_chantier(inst, p.id),
                  'quantites_deja_sorties_chantier': isel.quantites_deja_sorties_chantier(inst, [p.id]).get(p.id),
                  'quantite_retournable': str(isvc.quantite_retournable(inst, p.id)),
                  'besoin_deja_sorti': besoin.get('deja_sorti'), 'besoin_manque_brut': besoin.get('manque_brut')})
        isvc._poser_reservation_ecart(inst, p.id, 15)
        o['resa_apres_v2_15'] = list(StockReservation.objects.filter(installation=inst, produit=p).values_list(
            'quantite', 'active', 'consomme'))
        B = '/api/django/installations'
        rr = api.post(f'{B}/retours-materiel/', {'installation': inst.id}, format='json', **H)
        api.post(f'{B}/retour-materiel-lignes/', {'retour': rr.data['id'], 'produit': p.id, 'quantite': '15'},
                 format='json', **H)
        rv = api.post(f'{B}/retours-materiel/{rr.data["id"]}/valider/', {}, format='json', **H)
        p.refresh_from_db()
        o.update({'retour_15': rv.status_code, 'stock_apres_retour': str(p.quantite_stock)})
        return o

    obs = {'astk257_258_presents': deja_la, 'R': cas('R', True), 'T': cas('T', False)}
    print(obs)
    r, t = obs['R'], obs['T']
    temoin_ok = t['valider_f11'] == 200 and Decimal(t['sorties_apres_f11']) == 10 \
        and t['quantite_deja_sortie_chantier'] == 10
    astk258_tient = r['valider_f11'] == 200 and Decimal(r['sorties_apres_f11']) == 10
    defaut = r['quantite_deja_sortie_chantier'] == 20 or r['quantites_deja_sorties_chantier'] == 20
    obs['temoin_ok'], obs['astk258_tient'] = temoin_ok, astk258_tient
    obs['repro'] = bool(temoin_ok and astk258_tient and defaut)
    return obs
