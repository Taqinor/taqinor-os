# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K80 — échantillon par OBJET : deux sociétés A et B, dans chacune un chantier (adresse/GPS/téléphone du contact de
site), un fournisseur (RIB/ICE/IF), une ligne de devis (P.U.), une remise d'encaissement (+ son PDF), une demande de
garantie, un contrat de maintenance (prix), une alarme onduleur. Rejeu par la VRAIE route (cookie JWT réel) en
Admin RH et Commercial terrain de A (rôles système, aucun code stock/installations/sav/ventes), témoin Directeur de A.
Contrôles : `list` + `retrieve` (+ `pdf`) ouverts ? clés sensibles servies ? jamais un id de B ? Témoins de patron
correct : crm/leads, ventes/factures, sav/tickets → 403 au même rôle. Transaction annulée."""
SONDE = {"constat": "C-APFS-081", "sha": "57d3fd371d",
         "attendu": "repro si Admin RH / Commercial terrain de A obtiennent 200 sur list+retrieve des 7 objets avec les "
                    "clés sensibles (site_adresse, gps, contact_site_telephone, rib, ice, prix_unitaire, montant_declare, "
                    "prix…) alors que crm/leads, ventes/factures, sav/tickets leur répondent 403 ; aucun id de B",
         "modeles": ["authentication.Company", "authentication.CustomUser", "roles.Role", "installations.Installation",
                     "stock.Fournisseur", "ventes.LigneDevis", "ventes.RemiseEncaissement", "sav.WarrantyClaim",
                     "sav.ContratMaintenance", "sav.AlarmeOnduleur"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import AccessToken
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.stock.models import Fournisseur, Produit
    from apps.ventes.models import Devis, LigneDevis, RemiseEncaissement
    from apps.sav.models import Equipement, WarrantyClaim, ContratMaintenance, AlarmeOnduleur
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(reg.CANONICAL_SYSTEM_ROLES)
    PERIM = getattr(reg, 'SYSTEM_ROLE_PERIMETRES', {})
    today = timezone.now().date()
    coA = Company.objects.create(nom='Sonde APFS 081 A', slug='sonde-apfs-081-a')
    coB = Company.objects.create(nom='Sonde APFS 081 B', slug='sonde-apfs-081-b')

    def compte(co, nom, suffixe):
        perms = list(R[nom])
        role, _ = Role.objects.get_or_create(company=co, nom=nom, defaults={'permissions': perms, 'est_systeme': True})
        if PERIM.get(nom) and getattr(role, 'perimetre', None) != PERIM.get(nom):
            role.perimetre = PERIM[nom]
            role.save(update_fields=['perimetre'])
        return U.objects.create_user(username='apfs081-' + suffixe, password='x', company=co, role=role,
                                     role_legacy=tier_for_role_fields(nom, True, perms))

    erreurs = {}

    def creer(cle, fn):
        try:
            with transaction.atomic():
                return fn()
        except Exception as exc:  # noqa
            erreurs[cle] = repr(exc)[:160]
            return None

    def jeu(co, s):
        dirc = compte(co, 'Directeur', 'dir-' + s)
        cl = Client.objects.create(company=co, nom='Client', prenom='K80' + s, email=f'k80{s}@example.invalid')
        o = {}
        o['chantier'] = creer('chantier' + s, lambda: Installation.objects.create(
            company=co, reference='CH-APFS081-' + s, client=cl, site_adresse='12 rue du Site ' + s,
            gps_lat=Decimal('33.570000'), gps_lng=Decimal('-7.590000'), contact_site_nom='Contact ' + s,
            contact_site_telephone='0600000081'))
        o['fournisseur'] = creer('fournisseur' + s, lambda: Fournisseur.objects.create(
            company=co, nom='Fournisseur ' + s, rib='011780000012345678901234', ice='001234567000081',
            identifiant_fiscal='81818181', telephone='0522000081'))
        p = creer('produit' + s, lambda: Produit.objects.create(company=co, nom='Panneau ' + s, sku='APFS081-' + s,
                                                               prix_vente=Decimal('1500')))
        dv = creer('devis' + s, lambda: Devis.objects.create(company=co, reference='DEV-APFS081-' + s, client=cl,
                                                            created_by=dirc))
        o['ligne_devis'] = creer('ligne' + s, lambda: LigneDevis.objects.create(
            devis=dv, produit=p, designation='Panneau', quantite=Decimal('10'), prix_unitaire=Decimal('1234.56')))
        o['remise'] = creer('remise' + s, lambda: RemiseEncaissement.objects.create(
            company=co, technicien=dirc, reference='REM-APFS081-' + s, date_collecte=today,
            montant_declare=Decimal('8100'), created_by=dirc))
        eq = creer('equipement' + s, lambda: Equipement.objects.create(
            company=co, produit=p, numero_serie='SN-APFS081-' + s, installation=o['chantier'], client_vente=cl))
        o['garantie'] = creer('garantie' + s, lambda: WarrantyClaim.objects.create(
            company=co, equipement=eq, fournisseur_nom_cache='Fournisseur ' + s, cout_recupere=Decimal('810'),
            created_by=dirc))
        o['contrat'] = creer('contrat' + s, lambda: ContratMaintenance.objects.create(
            company=co, client=cl, installation=o['chantier'], date_debut=today, prix=Decimal('2400')))
        o['alarme'] = creer('alarme' + s, lambda: AlarmeOnduleur.objects.create(
            company=co, equipement=eq, code='F81', gravite='critique', libelle='Alarme ' + s, created_by=dirc))
        return dirc, o

    dirA, A = jeu(coA, 'A')
    _, B = jeu(coB, 'B')
    rh = compte(coA, 'Admin RH', 'rh')
    ct = compte(coA, 'Commercial terrain', 'ct')

    def client(u):
        c = APIClient()
        c.cookies['access_token'] = str(AccessToken.for_user(u))
        return c

    def j(r):
        try:
            return r.json()
        except Exception:  # noqa
            return None

    def rows(r):
        d = j(r)
        d = d.get('results', d) if isinstance(d, dict) else d
        return d if isinstance(d, list) else []

    CIBLES = {
        'chantier': ('/api/django/installations/chantiers/', ['site_adresse', 'gps_lat', 'contact_site_telephone', 'client']),
        'fournisseur': ('/api/django/stock/fournisseurs/', ['rib', 'ice', 'identifiant_fiscal', 'telephone']),
        'ligne_devis': ('/api/django/ventes/devis-lignes/', ['prix_unitaire']),
        'remise': ('/api/django/ventes/remises-encaissement/', ['montant_declare']),
        'garantie': ('/api/django/sav/warranty-claims/', ['cout_recupere']),
        'contrat': ('/api/django/sav/contrats-maintenance/', ['prix']),
        'alarme': ('/api/django/sav/alarmes-onduleur/', ['code', 'gravite']),
    }
    TEMOINS = ['/api/django/crm/leads/', '/api/django/ventes/factures/', '/api/django/sav/tickets/']

    def rejouer(u):
        c = client(u)
        out = {}
        for cle, (url, cles) in CIBLES.items():
            oa, ob = A.get(cle), B.get(cle)
            if oa is None:
                out[cle] = 'non créé'
                continue
            rl = c.get(url + '?page_size=500', **H)
            ids = [x.get('id') for x in rows(rl) if isinstance(x, dict)]
            rr = c.get(f'{url}{oa.pk}/', **H)
            d = j(rr) if rr.status_code == 200 else {}
            d = d if isinstance(d, dict) else {}
            ligne = f"list={rl.status_code} retrieve={rr.status_code} A_listé={oa.pk in ids} " \
                    f"B_listé={(ob.pk in ids) if ob else None} clés={[k for k in cles if d.get(k) not in (None, '')]}"
            if cle == 'remise':
                rp = c.get(f'{url}{oa.pk}/pdf/', **H)
                ligne += f" pdf={rp.status_code} {rp.get('Content-Type', '')[:15]}"
            if cle == 'chantier' and d:
                ligne += f" adresse={d.get('site_adresse')!r} tel={d.get('contact_site_telephone')!r}"
            if cle == 'fournisseur' and d:
                ligne += f" rib={d.get('rib')!r}"
            out[cle] = ligne
        out['témoins'] = ' '.join(f"{t.split('/')[-2]}={c.get(t, **H).status_code}" for t in TEMOINS)
        return out

    obs = {'erreurs_creation': erreurs, 'Admin RH': rejouer(rh), 'Commercial terrain': rejouer(ct),
           'Directeur (témoin)': rejouer(dirA)}

    def fuite(role):
        return [k for k, v in obs[role].items() if k != 'témoins' and 'list=200' in v and 'retrieve=200' in v
                and 'clés=[]' not in v]

    obs['ouverts_RH'] = fuite('Admin RH')
    obs['ouverts_CT'] = fuite('Commercial terrain')
    obs['B_jamais_listé'] = all('B_listé=True' not in v for r in ('Admin RH', 'Commercial terrain', 'Directeur (témoin)')
                                for v in obs[r].values())
    obs['repro'] = bool(len(obs['ouverts_RH']) >= 5 and len(obs['ouverts_CT']) >= 5
                        and '403' in obs['Admin RH']['témoins'])
    return obs
