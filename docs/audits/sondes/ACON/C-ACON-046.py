# flake8: noqa  (sonde d'audit de parcours PA2 « Conception », rejouable par scripts/sonde.py — METHODE §C.4)
"""K46 — deux « Générer le devis » chevauchés sur le MÊME calepinage créent deux devis ; le lien du calepinage
est écrasé par le dernier à finir, l'autre devis reste orphelin. `services/devis.py::_generer` ne prend aucun
verrou (ni select_for_update du calepinage, ni `_verrou_creation`) entre la lecture du lien / de la dédup et la
création ; `liens.lier_devis` lit `calepinage.devis_id` EN MÉMOIRE.
Rejeu mono-connexion (pas de thread) : la requête 1 passe par la vraie route POST generer-devis ; un crochet
sur `apps.ventes.services.build_devis_from_layout` fait arriver la requête 2 (le service `generer_devis` que la
vue appelle, sur sa propre instance relue en base) PENDANT la composition de la 1."""
SONDE = {"constat": "C-ACON-046", "sha": "33cba7f5d",
         "attendu": "repro si 2 devis créés pour le même lead + même layout_hash, un seul lié au calepinage, "
                    "l'autre brouillon orphelin ; témoin : un 2e clic NON chevauché rend le même devis (deduplique)",
         "modeles": ["ventes.Devis", "calepinage.Calepinage"]}


def sonde(ctx):
    from io import StringIO
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import AccessToken
    from apps.calepinage.models import Calepinage
    from apps.calepinage.services.devis import generer_devis
    from apps.crm.models import Lead
    from apps.roles.models import Role
    from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
    from apps.ventes import services as vs
    from apps.ventes.models import Devis
    from apps.ventes.domain.geometrie import layout_hash
    from authentication.models import Company
    User = get_user_model()
    co = Company.objects.create(nom='SONDE ACON 046', slug='sonde-acon-046')
    call_command('seed_catalogue', company_slug=co.slug, stdout=StringIO())
    role = Role.objects.create(company=co, nom='Directeur', permissions=list(DIRECTEUR_PERMISSIONS))
    u = User.objects.create_user(username='sonde_acon_046', password='x', company=co, role=role,
                                 role_legacy='responsable')
    api = APIClient(); api.credentials(HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(u))
    C = '/api/django/calepinage/calepinages/%s/generer-devis/'

    def nouveau(tag):
        lead = Lead.objects.create(company=co, nom='Villa', prenom=tag, email='acon046-%s@example.test' % tag)
        L = {'scenario': 'reseau', 'panelWatt': 550, 'nonce': tag,
             'result': {'panels': 12, 'kwc': 6.6, 'annualKwh': 10000, 'savings': 8000}}
        return lead, Calepinage.objects.create(company=co, lead_id=lead.pk, titre='Toit ' + tag, roof_layout=L,
                                               layout_hash=layout_hash(L))

    # Témoin : deux clics successifs (non chevauchés) → un seul devis, dédupliqué
    leadT, calT = nouveau('T')
    t1 = api.post(C % calT.pk, {}, format='json'); t2 = api.post(C % calT.pk, {}, format='json')
    temoin = {'http': [t1.status_code, t2.status_code], 'meme_devis': t1.data.get('devis') == t2.data.get('devis'),
              'deduplique_2e': t2.data.get('deduplique'),
              'devis_du_lead': Devis.objects.filter(company=co, lead_id=leadT.pk).count()}

    # R : la requête 2 arrive pendant la composition de la requête 1
    leadR, calR = nouveau('R')
    reel = vs.build_devis_from_layout
    etat = {'n': 0}

    def crochet(*a, **k):
        etat['n'] += 1
        if etat['n'] == 1:
            instance_requete_2 = Calepinage.objects.get(pk=calR.pk)    # relue en base, devis_id encore vide
            d2, cree2 = generer_devis(instance_requete_2, user=u)
            etat['requete_2'] = {'devis': d2.pk, 'cree': cree2}
        return reel(*a, **k)

    with mock.patch.object(vs, 'build_devis_from_layout', side_effect=crochet):
        r1 = api.post(C % calR.pk, {}, format='json')
    calR.refresh_from_db()
    devis_lead = list(Devis.objects.filter(company=co, lead_id=leadR.pk).values('pk', 'reference', 'statut', 'layout_hash'))
    lies = {d['pk']: Calepinage.objects.filter(devis_id=d['pk']).count() for d in devis_lead}
    obs = {'temoin': temoin, 'requete_1': [r1.status_code, getattr(r1, 'data', None) and r1.data.get('devis')],
           'requete_2': etat.get('requete_2'), 'calepinage.devis_id': calR.devis_id,
           'devis_du_lead': [(d['reference'], d['statut'], (d['layout_hash'] or '')[:10]) for d in devis_lead],
           'calepinages_lies_par_devis': lies}
    print(obs)
    temoin_ok = temoin['meme_devis'] and temoin['deduplique_2e'] is True and temoin['devis_du_lead'] == 1
    orphelins = [pk for pk, n in lies.items() if n == 0]
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and r1.status_code in (200, 201) and len(devis_lead) == 2 and len(orphelins) == 1
                        and len({d['layout_hash'] for d in devis_lead}) == 1)
    return obs
