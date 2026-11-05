"""ASEC29 (C-ASEC-004, D-ASEC-1 ; frère LCOUT-1 = C-ALEA-001) — les gestes
d'argent (`abandonner-solde`, `enregistrer-paiement`, `facturer-complet`,
création d'avoir) sont réservés au code `encaisser` (Administrateur,
Directeur, Commercial et Commercial responsable par défaut), et
`FactureViewSet.get_permissions` respecte la garde déclarée par l'@action.

Rouge sur 51f22174f (V6 : Commercial terrain et Admin RH → `abandonner-solde`
200, facture → `payee`). Rôles système réels (`init_roles`), endpoints réels,
aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_xfac_asec29_gestes_argent"
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

User = get_user_model()

AUTORISES = ('Directeur', 'Commercial')
REFUSES = ('Commercial sans encaisser', 'Commercial terrain', 'Technicien',
           'Admin RH')
GESTES = ('abandonner_solde', 'enregistrer_paiement', 'facturer_complet',
          'creer_avoir')
#: ASEC56 — Admin Ventes et Responsable (sans ``encaisser``) refusés aussi.
REFUSES_JUMELLES = REFUSES + ('Admin Ventes', 'Responsable')
PORTES = ('paiement_avec_retenue', 'attestation_recue', 'rejeter',
          'annuler_saisie', 'reaffecter', 'retour_client',
          'facturer_penalites', 'liberer_retenue', 'lien_paiement',
          'revoquer_lien_paiement', 'releve_dry_run', 'releve_commit')
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class GestesArgentTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.roles.models import Role
        from apps.stock.models import Produit
        from authentication.models import Company
        self.company = Company.objects.create(nom='ASEC29', slug='asec29-co')
        call_command('init_roles', verbosity=0)
        roles = {r.nom: r for r in Role.objects.filter(company=self.company)}
        commercial = roles['Commercial']
        sans = Role.objects.create(
            company=self.company, nom='Commercial sans encaisser',
            permissions=[c for c in commercial.permissions
                         if c != 'encaisser'])
        roles['Commercial sans encaisser'] = sans
        self.users = {}
        for nom in AUTORISES + REFUSES_JUMELLES:
            self.users[nom] = User.objects.create_user(
                username=f'asec29-{_nxt()}', password='x',
                role_legacy='normal', role=roles[nom], company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Argent', prenom='ASEC29',
            email='asec29@example.invalid')
        self.produit = Produit.objects.create(
            company=self.company, nom='Avoir ASEC29', sku='ASEC29-P',
            prix_vente=Decimal('0'), quantite_stock=0)
        # Produit de la ligne du devis : facturer-complet décompte le stock.
        self.kit = Produit.objects.create(
            company=self.company, nom='Kit ASEC29', sku='ASEC29-K',
            prix_vente=Decimal('1000'), quantite_stock=1000)

    def _api(self, user):
        api = APIClient()
        api.force_authenticate(user)
        return api

    def _facture(self, user):
        from apps.ventes.models import Facture, LigneFacture
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-ASEC29-{_nxt()}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), created_by=user)
        LigneFacture.objects.create(
            facture=facture, produit=self.produit, designation='Centrale',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20.00'))
        return facture

    def _devis(self, user):
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ASEC29-{_nxt()}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), created_by=user)
        LigneDevis.objects.create(
            devis=devis, produit=self.kit, designation='Centrale',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20.00'))
        return devis

    def _geste(self, geste, user):
        """Joue le geste ; renvoie (réponse, objet relu pour la persistance)."""
        api = self._api(user)
        if geste == 'facturer_complet':
            devis = self._devis(user)
            r = api.post(
                f'/api/django/ventes/devis/{devis.id}/facturer-complet/',
                {'paiements': []}, format='json')
            return r, devis
        facture = self._facture(user)
        base = f'/api/django/ventes/factures/{facture.id}/'
        if geste == 'abandonner_solde':
            r = api.post(base + 'abandonner-solde/',
                         {'motif': 'geste_commercial'}, format='json')
        elif geste == 'enregistrer_paiement':
            r = api.post(base + 'enregistrer-paiement/', {
                'montant': '100', 'date_paiement': date.today().isoformat(),
                'mode': 'virement'}, format='json')
        else:
            r = api.post(base + 'creer-avoir/', {
                'lignes': [{'designation': 'Geste', 'quantite': '1',
                            'prix_unitaire': '100', 'taux_tva': '20',
                            'produit': self.produit.id}]}, format='json')
        return r, facture

    def test_matrice_role_geste(self):
        from apps.ventes.models import Avoir, Facture, Paiement
        for geste in GESTES:
            for nom in AUTORISES:
                with self.subTest(geste=geste, role=nom):
                    r, _ = self._geste(geste, self.users[nom])
                    self.assertIn(r.status_code, (200, 201), r.data)
            for nom in REFUSES:
                with self.subTest(geste=geste, role=nom):
                    r, objet = self._geste(geste, self.users[nom])
                    self.assertEqual(r.status_code, 403, r.data)
                    if geste == 'facturer_complet':
                        self.assertFalse(
                            Facture.objects.filter(devis=objet).exists())
                        continue
                    objet.refresh_from_db()
                    self.assertEqual(objet.statut, Facture.Statut.EMISE)
                    self.assertFalse(
                        Paiement.objects.filter(facture=objet).exists())
                    self.assertFalse(
                        Avoir.objects.filter(facture=objet).exists())
                    self.assertFalse(objet.abandon_montant)

    def _objets(self, user):
        """ASEC56 — facture émise (paiement 200, RAS sans attestation,
        retenue de garantie non libérée) créée par ``user`` (portée)."""
        from apps.ventes.models import Paiement, RetenueSubie
        facture = self._facture(user)
        facture.retenue_garantie_mad = Decimal('60')
        facture.save(update_fields=['retenue_garantie_mad'])
        paiement = Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal('200'),
            date_paiement=date.today(), mode='virement', created_by=user)
        retenue = RetenueSubie.objects.create(
            company=self.company, facture=facture, taux=Decimal('10'),
            base=Decimal('500'), montant=Decimal('50'), created_by=user)
        return {'facture': facture, 'paiement': paiement, 'retenue': retenue,
                'autre': self._facture(user)}

    def _porte(self, porte, user, o):
        from django.core.files.uploadedfile import SimpleUploadedFile
        api = self._api(user)
        pai = '/api/django/ventes/paiements/'
        fac = f"/api/django/ventes/factures/{o['facture'].id}/"
        if porte == 'releve_dry_run':
            fichier = SimpleUploadedFile(
                'releve.csv', b'date;libelle;montant\n2026-11-01;VIR;200\n',
                content_type='text/csv')
            return api.post(pai + 'import-releve/dry-run/', {'file': fichier},
                            format='multipart')
        url, data = {
            'paiement_avec_retenue': (
                f"{pai}factures/{o['facture'].id}/paiement-avec-retenue/",
                {'montant': '1000', 'date_paiement': date.today().isoformat(),
                 'mode': 'virement', 'type_retenue': 'ras_tva', 'taux': '10'}),
            'attestation_recue': (
                f"{pai}retenues/{o['retenue'].id}/attestation-recue/", {}),
            'rejeter': (f"{pai}{o['paiement'].id}/rejeter/",
                        {'motif': 'Chèque impayé'}),
            'annuler_saisie': (f"{pai}{o['paiement'].id}/annuler-saisie/",
                               {'motif': 'Erreur de saisie'}),
            'reaffecter': (f"{pai}{o['paiement'].id}/reaffecter/",
                           {'facture': o['autre'].id}),
            'retour_client': (fac + 'retour-client/', {
                'motif': 'retour', 'restocker': False,
                'lignes': [{'produit': self.produit.id, 'quantite': '1'}]}),
            'facturer_penalites': (fac + 'facturer-penalites/', {}),
            'liberer_retenue': (fac + 'liberer-retenue/',
                                {'date': date.today().isoformat()}),
            'lien_paiement': (fac + 'lien-paiement/', {}),
            'revoquer_lien_paiement': (fac + 'revoquer-lien-paiement/', {}),
            'releve_commit': (pai + 'import-releve/commit/',
                              {'token': 'jeton-inconnu'}),
        }[porte]
        return api.post(url, data, format='json')

    def _etat(self, o):
        """Photo relue de tout ce qu'une porte d'argent peut écrire."""
        from apps.ventes.models import (
            Avoir, Facture, Paiement, PaymentLink, RetenueSubie)
        f = Facture.objects.get(pk=o['facture'].pk)
        p = Paiement.objects.get(pk=o['paiement'].pk)
        r = RetenueSubie.objects.get(pk=o['retenue'].pk)
        return (f.statut, f.montant_paye, f.abandon_montant,
                f.retenue_liberee_le, p.statut, p.facture_id,
                p.statut_affectation, r.attestation_recue,
                Paiement.objects.filter(company=self.company).count(),
                Avoir.objects.filter(company=self.company).count(),
                RetenueSubie.objects.filter(company=self.company).count(),
                Facture.objects.filter(company=self.company).count(),
                PaymentLink.objects.count())

    def test_matrice_portes_jumelles(self):
        """ASEC56 (C-ASEC-VER-003, D-ASEC-VER-1) — les portes jumelles des
        gestes d'argent exigent ``encaisser`` : 403 sans aucune écriture pour
        les six rôles qui ne le portent pas ; Directeur et Commercial jamais
        403 (réponse métier existante inchangée)."""
        objets = self._objets(self.users['Directeur'])
        avant = self._etat(objets)
        for porte in PORTES:
            for nom in REFUSES_JUMELLES:
                with self.subTest(porte=porte, role=nom):
                    r = self._porte(porte, self.users[nom], objets)
                    self.assertEqual(r.status_code, 403,
                                     getattr(r, 'data', None))
                    self.assertEqual(self._etat(objets), avant)
        for nom in AUTORISES:
            for porte in PORTES:
                with self.subTest(porte=porte, role=nom):
                    o = self._objets(self.users[nom])
                    r = self._porte(porte, self.users[nom], o)
                    self.assertNotEqual(r.status_code, 403,
                                        getattr(r, 'data', None))

    def test_directive_acompte_et_promesse_exigent_encaisser(self):
        """AARG7 (D-ASEC-VER-1) — annuler avec directive d'acompte
        (rembourser / transferer) et créer une promesse : 403 sans
        ``encaisser`` (Admin Ventes), rien d'écrit ; Directeur jamais 403.
        Mutant : retirer le contrôle ⇒ échec."""
        from datetime import timedelta

        from apps.ventes.models import Facture, Paiement, PromessePaiement
        directeur, admin_ventes = (self.users['Directeur'],
                                   self.users['Admin Ventes'])
        acompte = self._facture(directeur)
        Facture.objects.filter(pk=acompte.pk).update(
            type_facture=Facture.TypeFacture.ACOMPTE)
        Paiement.objects.create(
            company=self.company, facture=acompte, montant=Decimal('200'),
            date_paiement=date.today(), mode='virement', created_by=directeur)
        cible = self._facture(directeur)
        url = f'/api/django/ventes/factures/{acompte.id}/annuler/'
        promesse = {'facture': acompte.id, 'montant_promis': '100.00',
                    'date_promise': (date.today() + timedelta(days=15)
                                     ).isoformat()}
        corps = ({'acompte': {'action': 'rembourser'}},
                 {'acompte': {'action': 'transferer',
                              'facture_cible': cible.id}})
        for c in corps:
            with self.subTest(corps=c):
                r = self._api(admin_ventes).post(url, c, format='json')
                self.assertEqual(r.status_code, 403, r.data)
                self.assertIn("droit d'encaissement", str(r.data['detail']))
        r = self._api(admin_ventes).post(
            '/api/django/ventes/promesses-paiement/', promesse, format='json')
        self.assertEqual(r.status_code, 403, r.data)
        acompte.refresh_from_db()
        self.assertEqual(acompte.statut, Facture.Statut.EMISE)
        self.assertEqual(
            list(Paiement.objects.filter(facture__in=[acompte, cible])
                 .values_list('montant', flat=True)), [Decimal('200.00')])
        self.assertFalse(PromessePaiement.objects.exists())
        r = self._api(directeur).post(
            '/api/django/ventes/promesses-paiement/', promesse, format='json')
        self.assertNotEqual(r.status_code, 403, r.data)
        r = self._api(directeur).post(url, corps[0], format='json')
        self.assertNotEqual(r.status_code, 403, r.data)

    def test_emettre_unitaire_et_lot_exigent_encaisser(self):
        """AARG9 (D-AARG-3 = exiger_encaisser) — « Émettre » et le lot
        ``emettre`` : refusés sans ``encaisser`` (Admin Ventes), brouillon
        intact ; ``peut.emettre`` suit la même règle ; Directeur émet.
        Mutant : retirer ``PeutEncaisser`` d'``emettre`` ⇒ échec."""
        from apps.ventes.models import Facture
        from apps.ventes.vente_facturation import peut_encaisser
        motif = "Émettre ou encaisser une facture exige le droit d'encaissement."
        directeur, admin_ventes = (self.users['Directeur'],
                                   self.users['Admin Ventes'])
        brouillon = self._facture(directeur)
        Facture.objects.filter(pk=brouillon.pk).update(
            statut=Facture.Statut.BROUILLON, reference=f'BROUILLON-{_nxt()}')
        api = self._api(admin_ventes)
        r = api.post(f'/api/django/ventes/factures/{brouillon.id}/emettre/')
        self.assertEqual(r.status_code, 403, r.data)
        self.assertEqual(r.data['detail'], motif)
        r = api.post('/api/django/ventes/factures/bulk/',
                     {'action': 'emettre', 'ids': [brouillon.id]},
                     format='json')
        self.assertEqual(r.status_code, 200, r.data)
        resultat = r.data.get(brouillon.id) or r.data.get(str(brouillon.id))
        self.assertEqual(resultat, {'ok': False, 'detail': motif})
        relue = Facture.objects.get(pk=brouillon.pk)
        self.assertEqual(relue.statut, Facture.Statut.BROUILLON)
        self.assertTrue(relue.reference.startswith('BROUILLON-'))
        self.assertFalse(peut_encaisser(admin_ventes))
        self.assertTrue(peut_encaisser(directeur))
        r = self._api(directeur).post(
            f'/api/django/ventes/factures/{brouillon.id}/emettre/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Facture.objects.get(pk=brouillon.pk).statut,
                         Facture.Statut.EMISE)

    def test_generer_facture_et_consolider_exigent_encaisser(self):
        """ASEC67 (C-ASEC-VER4-010, D-AARG-3) — les jumelles d'émission
        ``devis/<id>/generer-facture/`` et ``factures/consolider/`` : 403
        sans ``encaisser``, aucune facture créée ; un Commercial (porte
        ``encaisser``) émet toujours. Mutant : retirer une garde ⇒ échec."""
        from apps.ventes.models import Facture
        motif = "Émettre ou encaisser une facture exige le droit d'encaissement."
        sans, commercial = (self.users['Commercial sans encaisser'],
                            self.users['Commercial'])
        api = self._api(sans)
        avant = Facture.objects.filter(company=self.company).count()
        d1 = self._devis(sans)
        r = api.post(f'/api/django/ventes/devis/{d1.id}/generer-facture/',
                     {}, format='json')
        self.assertEqual(r.status_code, 403, r.data)
        self.assertEqual(r.data['detail'], motif)
        d2, d3 = self._devis(sans), self._devis(sans)
        r = api.post('/api/django/ventes/factures/consolider/',
                     {'devis_ids': [d2.id, d3.id]}, format='json')
        self.assertEqual(r.status_code, 403, r.data)
        self.assertEqual(r.data['detail'], motif)
        self.assertEqual(
            Facture.objects.filter(company=self.company).count(), avant)
        # Le Commercial est borné à SES devis (portée « own ») : son propre devis.
        d4 = self._devis(commercial)
        r = self._api(commercial).post(
            f'/api/django/ventes/devis/{d4.id}/generer-facture/', {},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)

    def test_lecture_argent_bornee_au_module_ventes(self):
        """AARG12 — paiements (+ reçu PDF), avoirs, notes de débit, bons de
        commande et promesses : 403 pour Admin RH (aucun code ventes), comme
        la liste des factures ; Commercial (``ventes_voir``) lit toujours.
        Mutant : remettre ``IsAnyRole`` sur un viewset ⇒ échec."""
        from apps.ventes.models import Paiement
        facture = self._facture(self.users['Directeur'])
        paiement = Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal('300'),
            date_paiement=date.today(), mode='virement',
            created_by=self.users['Directeur'])
        base = '/api/django/ventes/'
        listes = [base + seg for seg in (
            'paiements/', 'avoirs/', 'notes-debit/', 'bons-commande/',
            'promesses-paiement/')]
        rh = self._api(self.users['Admin RH'])
        for url in listes + [f'{base}paiements/{paiement.id}/recu-pdf/']:
            with self.subTest(role='Admin RH', url=url):
                r = rh.get(url)
                self.assertEqual(r.status_code, 403, getattr(r, 'data', None))
                self.assertEqual(
                    str(r.data['detail']),
                    'Accès aux factures réservé aux rôles du module Ventes.')
        commercial = self._api(self.users['Commercial'])
        for url in listes:
            with self.subTest(role='Commercial', url=url):
                r = commercial.get(url)
                self.assertEqual(r.status_code, 200, getattr(r, 'data', None))

    def test_get_permissions_respecte_action(self):
        from apps.ventes.views.facture import FactureViewSet
        from apps.ventes.views.facture_gardes import PeutEncaisser
        fabrique = APIRequestFactory()
        for action in ('enregistrer_paiement', 'abandonner_solde',
                       'creer_avoir', 'encaissement_groupe'):
            with self.subTest(action=action):
                vue = FactureViewSet()
                vue.action = action
                vue.request = Request(fabrique.post('/'))
                gardes = vue.get_permissions()
                self.assertEqual([type(p) for p in gardes], [PeutEncaisser])

    def test_lecture_factures_bornee_au_module_ventes(self):
        """ERR-ASEC11-LISTE-FACTURES (C-ASEC-004, clause ASEC11) — liste,
        fiche et lectures annexes d'une facture : 403 pour un rôle sans aucun
        code du module ventes (Commercial terrain, Technicien, Admin RH) ;
        Directeur, Commercial et Viewer (``ventes_voir``) lisent toujours."""
        from apps.roles.models import Role
        viewer = User.objects.create_user(
            username=f'asec29-{_nxt()}', password='x', role_legacy='normal',
            role=Role.objects.get(company=self.company, nom='Viewer'),
            company=self.company)
        lecteurs = {nom: self.users[nom] for nom in AUTORISES}
        lecteurs['Viewer'] = viewer
        facture = self._facture(self.users['Directeur'])
        base = '/api/django/ventes/factures/'
        urls = (base, base + 'kpis/', f'{base}{facture.id}/',
                f'{base}{facture.id}/paiements/',
                f'{base}{facture.id}/historique/')
        for nom in ('Commercial terrain', 'Technicien', 'Admin RH'):
            api = self._api(self.users[nom])
            for url in urls:
                with self.subTest(role=nom, url=url):
                    r = api.get(url)
                    self.assertEqual(r.status_code, 403,
                                     getattr(r, 'data', None))
        for nom, user in lecteurs.items():
            api = self._api(user)
            r = api.get(base)
            with self.subTest(role=nom, url=base):
                self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
            mienne = self._facture(user)
            r = api.get(f'{base}{mienne.id}/')
            with self.subTest(role=nom, url='fiche'):
                self.assertEqual(r.status_code, 200, getattr(r, 'data', None))

    def _lectures_bornees(self, urls_json, urls_autres):
        """Admin RH : 403 (texte LectureFactures) sur chaque URL ; Commercial et
        Directeur : 200 sur les lectures JSON, jamais 403 sur les autres (PDF
        à rendu dépendant de l'environnement)."""
        rh = self._api(self.users['Admin RH'])
        for url in urls_json + urls_autres:
            with self.subTest(role='Admin RH', url=url):
                r = rh.get(url)
                self.assertEqual(r.status_code, 403, getattr(r, 'data', None))
                self.assertEqual(
                    str(r.data['detail']),
                    'Accès aux factures réservé aux rôles du module Ventes.')
        for nom in AUTORISES:
            api = self._api(self.users[nom])
            for url in urls_json:
                with self.subTest(role=nom, url=url):
                    r = api.get(url)
                    self.assertEqual(r.status_code, 200,
                                     getattr(r, 'data', None))
            for url in urls_autres:
                with self.subTest(role=nom, url=url):
                    self.assertNotEqual(api.get(url).status_code, 403)

    def test_lectures_recouvrement_bornees_au_module_ventes(self):
        """AARG65 (C-AARG-VER5-011) — relances, balance âgée, relevé client
        (JSON, PDF), lettre de relance PDF et score de comportement : 403 pour
        Admin RH, comme la liste des factures ; Commercial/Directeur lisent.
        Mutant : remettre ``IsAnyRole`` sur une vue ⇒ échec."""
        facture = self._facture(self.users['Commercial'])
        base = '/api/django/ventes/'
        client = self.client_obj.id
        self._lectures_bornees(
            [base + 'relances/', base + 'balance-agee/',
             f'{base}clients/{client}/releve/',
             f'{base}clients/{client}/score-comportement/'],
            [f'{base}clients/{client}/releve-pdf/',
             f'{base}factures/{facture.id}/lettre-relance-pdf/'])

    def test_lectures_annexes_bornees_au_module_ventes(self):
        """AARG66 (C-AARG-VER5-003) — lignes de facture, prévision de
        trésorerie, alerte d'encours client, lettre de relance premium : 403
        pour Admin RH ; Commercial/Directeur lisent.
        Mutant : remettre ``IsAnyRole`` sur une vue ⇒ échec."""
        facture = self._facture(self.users['Commercial'])
        base = '/api/django/ventes/'
        self._lectures_bornees(
            [base + 'factures-lignes/', base + 'insights/cash-flow/',
             f'{base}clients/{self.client_obj.id}/credit-warning/'],
            [f'{base}factures/{facture.id}/lettre-relance-premium/'])
