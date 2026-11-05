# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K06 — `DemandeAchatViewSet.get_permissions` ne pose `PeutApprouverDemandeAchat` que sur `approuver` /
`approuver_etape` : `rejeter-etape`, `refuser` et `marquer_commandee` tombent dans `IsResponsableOrAdmin`
(franchi par `installation_gerer` du Technicien). Trois gestes terminaux par un Technicien (rôle système) :
(1) DA sous plan 2 étapes → rejeter-etape ; (2) DA soumise → refuser ; (3) DA approuvée → marquer_commandee
puis l'Admin ne peut plus générer le BCF. Témoin : approuver-etape par le même Technicien = 403."""
SONDE = {"constat": "C-AAPV-101", "sha": "c6bd9b5d52",
         "attendu": "repro si témoin approuver-etape 403 ET rejeter-etape/refuser/marquer_commandee 200 par le technicien",
         "modeles": ["installations.DemandeAchat", "installations.EtapeApprobationAchat",
                     "installations.RegleApprobationAchat", "roles.Role", "authentication.Company"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.installations.models import DemandeAchat, DemandeAchatLigne, RegleApprobationAchat
    from apps.stock.models import Fournisseur
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(CANONICAL_SYSTEM_ROLES)
    co = Company.objects.create(nom='Sonde AAPV 101', slug='sonde-aapv-101')

    def compte(nom):
        perms = list(R[nom])
        role, _ = Role.objects.get_or_create(company=co, nom=nom,
                                             defaults={'permissions': perms, 'est_systeme': True})
        u = U.objects.create_user(username='s101-' + nom.lower().replace(' ', '-'), password='x', company=co,
                                  role=role, role_legacy=tier_for_role_fields(nom, True, perms))
        c = APIClient()
        c.force_authenticate(u)
        return u, c

    adm, ca = compte('Administrateur')
    tech, ct = compte('Technicien')
    four = Fournisseur.objects.create(company=co, nom='F-S101')
    base = '/api/django/installations/demandes-achat/'

    def da(ref, statut=DemandeAchat.Statut.BROUILLON):
        d = DemandeAchat.objects.create(company=co, reference=ref, objet='Onduleurs', statut=statut,
                                        created_by=adm, fournisseur_suggere=four)
        DemandeAchatLigne.objects.create(demande=d, designation='Onduleur 5 kW', quantite=Decimal('2'),
                                         prix_estime=Decimal('9000'))
        return d

    RegleApprobationAchat.objects.create(company=co, libelle='Tout achat : 2 approbateurs', montant_min=Decimal('0'),
                                         nombre_approbateurs=2, actif=True)
    obs = {}
    # (1) plan 2 étapes : soumission par l'admin (vraie route), puis le technicien rejette l'étape
    d1 = da('DA-S101-1')
    s = ca.post(f'{base}{d1.id}/soumettre/', {}, format='json', **H)
    temoin = ct.post(f'{base}{d1.id}/approuver-etape/', {}, format='json', **H)
    rj = ct.post(f'{base}{d1.id}/rejeter-etape/', {}, format='json', **H)
    d1.refresh_from_db()
    obs['rejeter_etape'] = {'soumettre_http': s.status_code, 'etapes_creees': d1.etapes_approbation.count(),
                            'temoin_approuver_etape_http': temoin.status_code, 'rejeter_http': rj.status_code,
                            'statut': d1.statut,
                            'etapes': list(d1.etapes_approbation.order_by('niveau').values_list('statut', flat=True)),
                            'decideur_est_tech': d1.approuvee_par_id == tech.id}
    # (2) refus direct d'une DA soumise (sans plan : étapes créées à la main absentes)
    d2 = da('DA-S101-2', DemandeAchat.Statut.SOUMISE)
    rf = ct.post(f'{base}{d2.id}/refuser/', {'motif_refus': 'non'}, format='json', **H)
    d2.refresh_from_db()
    obs['refuser'] = {'http': rf.status_code, 'statut': d2.statut, 'decideur_est_tech': d2.approuvee_par_id == tech.id}
    # (3) DA approuvée → marquer commandée sans BCF, puis l'admin ne peut plus générer le BCF
    d3 = da('DA-S101-3', DemandeAchat.Statut.APPROUVEE)
    mc = ct.post(f'{base}{d3.id}/marquer_commandee/', {}, format='json', **H)
    d3.refresh_from_db()
    gb = ca.post(f'{base}{d3.id}/generer-bcf/', {'fournisseur': four.id}, format='json', **H)
    obs['marquer_commandee'] = {'http': mc.status_code, 'url_ok': mc.status_code != 404, 'statut': d3.statut,
                                'bcf_lie': d3.bon_commande_id, 'admin_generer_bcf_http': gb.status_code,
                                'admin_generer_bcf_detail': str(getattr(gb, 'data', ''))[:100]}
    print(obs)
    temoin_ok = temoin.status_code == 403 and s.status_code == 200 and obs['rejeter_etape']['etapes_creees'] == 2
    defaut = (rj.status_code == 200 and d1.statut == 'refusee'
              and rf.status_code == 200 and d2.statut == 'refusee'
              and mc.status_code == 200 and d3.statut == 'commandee')
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
