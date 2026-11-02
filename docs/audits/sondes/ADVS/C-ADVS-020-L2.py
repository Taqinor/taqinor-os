# flake8: noqa  (sonde seconde lentille, rejouable par scripts/sonde.py — AMET93)
"""C-ADVS-020 — LENTILLE 2 (reproduction indépendante). Autre porte : l'acceptation INTERNE
``POST /ventes/devis/<id>/accepter/`` (devis papier signé C&I, CIQ323 — bloc entreprise facultatif, sans ICE)
au lieu du lien public. Client RÉSOLU PAR LE SERVEUR depuis un lead industriel sans société (POST atomic avec
``lead`` seul → ``resolve_client_for_lead`` : client entreprise « raison sociale à confirmer »). Après
l'acceptation : nom du client, verdict du vérificateur de sceau, et sort de l'exemplaire signé
(``pdf_signe._rendre_si_scelle``, ``_store_signed_pdf`` bouchonné pour ne rien rendre).
FRÈRE (même cause : le sceau couvre ``client.nom|email``, données VIVANTES d'une autre app) : un devis
résidentiel accepté, puis le nom du client corrigé par ``PATCH /crm/clients/<id>/`` → sceau ?
Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-020", "sha": "1dfa7986c",
         "attendu": "après acceptation interne C&I avec raison sociale : sceau intact, exemplaire signé rendu (pas REFUSE)",
         "modeles": ["ventes.Devis", "ventes.DevisSignature", "crm.Client", "crm.Lead"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, DevisSignature
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 020 L2', slug='sonde-advs-020-l2')
    u = U.objects.create_user(username='sonde-advs-020-l2', password='x', role_legacy='admin', company=c)
    lead = Lead.objects.create(company=c, nom='Benali', prenom='Karim', telephone='+212600020200',
                               ville='Fès', email='sonde-advs-020-l2@example.invalid',
                               type_installation='industriel')
    pan = Produit.objects.create(company=c, nom='Panneau Longi 580W', sku='ADVS020L2-P',
                                 prix_vente=Decimal('1200'), prix_achat=Decimal('700'), quantite_stock=500)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 50kW Triphasé', sku='ADVS020L2-O',
                                 prix_vente=Decimal('60000'), prix_achat=Decimal('40000'), quantite_stock=10)
    api = APIClient()
    api.force_authenticate(u)
    etapes = []

    def appel(nom, meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(api, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
        except Exception as e:
            etapes.append((nom, 599, repr(e)[:300]))
            return 599, {}
        brut = r.content if hasattr(r, 'content') else b''.join(r.streaming_content)
        etapes.append((nom, r.status_code, '' if r.status_code < 400 else brut[:300].decode('utf-8', 'replace')))
        try:
            return r.status_code, json.loads(brut.decode('utf-8'))
        except Exception:
            return r.status_code, {}

    def lignes(n):
        return [{'produit': pan.id, 'designation': 'Panneau Longi 580W', 'quantite': str(n),
                 'prix_unitaire': '1200', 'taux_tva': '20'},
                {'produit': ond.id, 'designation': 'Onduleur réseau Huawei 50kW Triphasé', 'quantite': '1',
                 'prix_unitaire': '60000', 'taux_tva': '20'}]

    appel('atomic C&I (lead seul)', 'post', '/api/django/ventes/devis/atomic/', {
        'lead': lead.id, 'statut': 'brouillon', 'taux_tva': '20.00', 'mode_installation': 'industriel',
        'lignes': lignes(86)})
    dv = Devis.objects.filter(company=c).order_by('id').first()
    obs = {'etapes': etapes}
    if dv is None:
        return {'repro': False, 'observe': obs}
    cl = Client.objects.get(pk=dv.client_id)
    obs['client_avant'] = {'nom': cl.nom, 'type': cl.type_client, 'a_confirmer': cl.raison_sociale_a_confirmer}
    from apps.ventes.domain import pdf_signe
    from apps.ventes.domain.identite_entreprise import verifier_empreinte_signature
    with mock.patch('apps.ventes.public_views._notify_open'), \
            mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf') as rendu:
        appel('share-link envoi', 'post', f'/api/django/ventes/devis/{dv.id}/share-link/', {'envoi': True})
        s, rep = appel('accepter interne + entreprise', 'post', f'/api/django/ventes/devis/{dv.id}/accepter/', {
            'nom': 'Karim Benali',
            'entreprise': {'raison_sociale': 'Atlas Métal SARL', 'signataire_qualite': 'Gérant'}})
        dv.refresh_from_db()
        cl.refresh_from_db()
        sig = DevisSignature.objects.filter(devis=dv).first()
        verdict = verifier_empreinte_signature(Devis.objects.get(pk=dv.pk))
        etat = pdf_signe._rendre_si_scelle(Devis.objects.get(pk=dv.pk), sig) if sig else 'pas de signature'
        obs.update(statut=dv.statut, client_apres={'nom': cl.nom, 'type': cl.type_client,
                                                    'a_confirmer': cl.raison_sociale_a_confirmer},
                   signataire=getattr(sig, 'signataire_nom', None), raison_sociale_sig=getattr(sig, 'raison_sociale', None),
                   sceau=verdict, etat_exemplaire_signe=etat, rendu_appele=rendu.called)
        # Contre-épreuve : le hash recalculé avec l'ANCIEN nom reproduit-il le sceau ?
        if sig is not None:
            ancien = cl.nom
            Client.objects.filter(pk=cl.pk).update(nom=obs['client_avant']['nom'])
            obs['sceau_avec_ancien_nom'] = verifier_empreinte_signature(Devis.objects.get(pk=dv.pk)).get('intacte')
            Client.objects.filter(pk=cl.pk).update(nom=ancien)

        # ── FRÈRE : résidentiel accepté, puis nom du client corrigé dans le CRM ──
        cl2 = Client.objects.create(company=c, nom='Idrissi', prenom='Sara', email='sonde-advs-020-l2b@example.invalid')
        appel('atomic résidentiel', 'post', '/api/django/ventes/devis/atomic/', {
            'client': cl2.id, 'statut': 'brouillon', 'taux_tva': '20.00', 'lignes': lignes(8)})
        dv2 = Devis.objects.filter(company=c, client=cl2).first()
        frere = {}
        if dv2 is not None:
            appel('share-link envoi 2', 'post', f'/api/django/ventes/devis/{dv2.id}/share-link/', {'envoi': True})
            appel('accepter interne 2', 'post', f'/api/django/ventes/devis/{dv2.id}/accepter/', {'nom': 'Sara Idrissi'})
            frere['sceau_juste_apres'] = verifier_empreinte_signature(Devis.objects.get(pk=dv2.pk)).get('intacte')
            appel('PATCH client nom', 'patch', f'/api/django/crm/clients/{cl2.id}/', {'nom': 'Idrissi-Alaoui'})
            frere['sceau_apres_patch_client'] = verifier_empreinte_signature(Devis.objects.get(pk=dv2.pk))
            frere['statut'] = Devis.objects.get(pk=dv2.pk).statut
        obs['frere_residentiel'] = frere
    repro = bool(dv.statut == 'accepte' and verdict.get('intacte') is False and etat == pdf_signe.REFUSE)
    return {'repro': repro, 'observe': obs}
