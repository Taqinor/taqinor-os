"""ATOT2 (C-ATOT-001) — les quatre portes de facturation d'un devis (tranche,
BC, facture complète, consolidée) passent par UN prédicat
(`factures_du_devis`, FactureSource compris) et UNE garde
(`exiger_devis_facturable`) : aucune vente n'est facturée deux fois.

Rejoue la sonde V1 TFAC-1 : aujourd'hui `facturer-complet` puis
`generer-facture` = 201 « Livraison du matériel 60 % » (Σ 240 000 pour un
devis de 150 000) ; une consolidée puis chaque porte = 201. Endpoints réels,
aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_atot_portes_facturation"
"""
import json
from decimal import Decimal
from itertools import permutations
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
PORTES = ('tranche', 'complete', 'bc', 'consolidee')
CONTRAT_SOLDE = (Path(__file__).resolve().parents[2] / 'ventes'
                 / 'contract_samples' / 'devis_solde.json')
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class PortesFacturationTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='ATOT2 Co', slug=f'atot2-co-{_nxt()}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Portes', prenom='ATOT2',
            email=f'atot2-{_nxt()}@example.invalid')
        # Produit de la ligne du devis : `LigneFacture.produit` est NOT NULL
        # et facturer-complet / consolider décomptent le stock (grand stock :
        # chaque sous-test facture un nouveau devis).
        from apps.stock.models import Produit
        self.kit = Produit.objects.create(
            company=self.company, nom='Kit ATOT2', sku=f'ATOT2K-{_nxt()}',
            prix_vente=Decimal('125000'), quantite_stock=100000)
        self.user = User.objects.create_user(
            username=f'atot2_resp_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    # ── fixtures ────────────────────────────────────────────────────────
    def _devis(self):
        """Devis accepté 125 000 HT @20 % (TTC 150 000), échéancier
        résidentiel par défaut 30/60/10."""
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ATOT2-{_nxt()}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=self.kit, designation='Centrale PV',
            quantite=Decimal('1'),
            prix_unitaire=Decimal('125000'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'))
        return devis

    def _porte(self, porte, devis):
        from apps.ventes.models import BonCommande
        if porte == 'tranche':
            return self.api.post(
                f'/api/django/ventes/devis/{devis.id}/generer-facture/',
                {}, format='json')
        if porte == 'complete':
            return self.api.post(
                f'/api/django/ventes/devis/{devis.id}/facturer-complet/',
                {'paiements': []}, format='json')
        if porte == 'bc':
            bc = BonCommande.objects.filter(devis=devis).first()
            if bc is None:
                bc = BonCommande.objects.create(
                    company=self.company, reference=f'BC-ATOT2-{_nxt()}',
                    devis=devis, client=self.client_obj,
                    statut=BonCommande.Statut.CONFIRME)
            return self.api.post(
                f'/api/django/ventes/bons-commande/{bc.id}/creer-facture/',
                {}, format='json')
        partenaire = self._devis()
        return self.api.post(
            '/api/django/ventes/factures/consolider/',
            {'devis_ids': [devis.id, partenaire.id]}, format='json')

    def _actives(self, devis):
        from apps.ventes.selectors_facturation import factures_du_devis
        return list(factures_du_devis(devis).order_by('id'))

    def _refs(self, devis):
        return [f.reference for f in self._actives(devis)]

    # ── les 12 ordres porte A puis porte B ─────────────────────────────
    def test_douze_ordres_seconde_porte_refusee(self):
        for porte_a, porte_b in permutations(PORTES, 2):
            with self.subTest(a=porte_a, b=porte_b):
                devis = self._devis()
                r1 = self._porte(porte_a, devis)
                self.assertEqual(r1.status_code, 201, r1.data)
                avant = self._refs(devis)
                self.assertEqual(len(avant), 1)
                r2 = self._porte(porte_b, devis)
                self.assertEqual(r2.status_code, 400, r2.data)
                self.assertIn(avant[0], str(r2.data))
                self.assertIn('avoir', str(r2.data))
                self.assertEqual(self._refs(devis), avant)

    def test_complete_puis_tranche_refuse(self):
        devis = self._devis()
        r1 = self._porte('complete', devis)
        self.assertEqual(r1.status_code, 201, r1.data)
        r2 = self._porte('tranche', devis)
        self.assertEqual(r2.status_code, 400, r2.data)
        self.assertIn(r1.data['facture_reference'], r2.data['detail'])
        total = sum((Decimal(str(f.total_ttc)) for f in self._actives(devis)),
                    Decimal('0'))
        self.assertLessEqual(total, Decimal('150000.00'))

    def test_consolidee_puis_chaque_porte_refuse(self):
        from apps.ventes.models import Devis, Facture, FactureSource
        d1, d2, d3 = self._devis(), self._devis(), self._devis()
        r = self.api.post(
            '/api/django/ventes/factures/consolider/',
            {'devis_ids': [d1.id, d2.id, d3.id]}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        consolidee = Facture.objects.get(pk=r.data['id'])
        nb = Facture.objects.count()
        for porte, devis in (('tranche', d1), ('complete', d2), ('bc', d3)):
            with self.subTest(porte=porte):
                resp = self._porte(porte, Devis.objects.get(pk=devis.pk))
                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertIn(consolidee.reference, str(resp.data))
        self.assertEqual(Facture.objects.count(), nb)
        self.assertEqual(
            FactureSource.objects.filter(facture=consolidee).count(), 3)

    def test_tranches_successives_restent_ouvertes(self):
        devis = self._devis()
        for _ in range(3):
            r = self._porte('tranche', devis)
            self.assertEqual(r.status_code, 201, r.data)
        total = sum((Decimal(str(f.total_ttc)) for f in self._actives(devis)),
                    Decimal('0'))
        self.assertEqual(total, Decimal('150000.00'))

    def test_solde_porte_facturation(self):
        from apps.ventes.models import Devis
        from apps.ventes.utils.echeancier import solde_devis
        vierge = self._devis()
        self.assertEqual(solde_devis(vierge)['porte_facturation'], 'libre')

        en_tranche = self._devis()
        self._porte('tranche', en_tranche)
        solde = solde_devis(Devis.objects.get(pk=en_tranche.pk))
        self.assertEqual(solde['porte_facturation'], 'tranche')
        self.assertEqual(solde['tranches_facturees'], 1)

        complet = self._devis()
        self._porte('complete', complet)
        solde = solde_devis(Devis.objects.get(pk=complet.pk))
        self.assertEqual(solde['porte_facturation'], 'aucune')
        self.assertEqual(solde['tranches_facturees'], 0)

        consolide = self._devis()
        self._porte('consolidee', consolide)
        solde = solde_devis(Devis.objects.get(pk=consolide.pk))
        self.assertEqual(solde['porte_facturation'], 'aucune')
        self.assertIs(solde['facturation_terminee'], True)  # AMET9

    def test_solde_api_expose_porte_en_texte(self):
        devis = self._devis()
        resp = self.api.get(f'/api/django/ventes/devis/{devis.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['solde']['porte_facturation'], 'libre')
        # AMET9 — clés servies = clés du contrat (get_solde : texte).
        contrat = json.loads(CONTRAT_SOLDE.read_text(encoding='utf-8'))
        self.assertEqual(set(resp.data['solde']),
                         set(contrat['exemple']['solde']))
        self.assertEqual(resp.data['solde']['facturation_terminee'], 'False')


class SoldeFacturationTermineeTests(TestCase):
    """AMET9 (C-AMET-002) — ``solde.facturation_terminee`` : le serveur DIT
    « plus rien à facturer » (facture complète OU toutes les tranches) ;
    ``tranches_facturees`` reste à 0 après une complète."""
    setUp = PortesFacturationTests.setUp
    _devis = PortesFacturationTests._devis
    _porte = PortesFacturationTests._porte

    def _terminee(self, devis):
        from apps.ventes.models import Devis
        from apps.ventes.utils.echeancier import solde_devis
        return solde_devis(
            Devis.objects.get(pk=devis.pk))['facturation_terminee']

    def test_solde_facturation_terminee_apres_facture_complete(self):
        self.assertIs(self._terminee(self._devis()), False)
        complet = self._devis()
        r = self._porte('complete', complet)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIs(self._terminee(complet), True)
        en_tranches = self._devis()
        for attendu in (False, False, True):  # 1/3, 2/3, 3/3
            r = self._porte('tranche', en_tranches)
            self.assertEqual(r.status_code, 201, r.data)
            self.assertIs(self._terminee(en_tranches), attendu)


class NumeroEmissionTests(TestCase):
    """ATOT27 (D-ATOT-5, C-ATOT-018) — le numéro légal d'une facture naît à
    l'ÉMISSION : un brouillon porte « BROUILLON-<id> » hors série, un
    brouillon supprimé ne consomme aucun numéro, la série émise suit l'ordre
    d'émission. Rejoue la sonde V1 TNUM-1 (``-0002`` réutilisé)."""
    setUp = PortesFacturationTests.setUp
    _devis = PortesFacturationTests._devis
    _porte = PortesFacturationTests._porte

    def _emettre(self, facture_id):
        return self.api.post(
            f'/api/django/ventes/factures/{facture_id}/emettre/', {},
            format='json')

    def _mois(self):
        from django.utils import timezone
        return timezone.now().strftime('%Y%m')

    def test_brouillons_hors_serie_numero_a_l_emission(self):
        from apps.ventes.models import Facture
        from apps.ventes.utils.numbering_audit import audit_company
        mois = self._mois()
        premier = self.api.post(
            '/api/django/ventes/factures/',
            {'client': self.client_obj.id, 'taux_tva': '20.00'},
            format='json')
        second = self._porte('bc', self._devis())
        troisieme = self._porte('bc', self._devis())
        for r in (premier, second, troisieme):
            self.assertEqual(r.status_code, 201, r.data)
            f = Facture.objects.get(pk=r.data['id'])
            self.assertEqual(f.statut, Facture.Statut.BROUILLON)
            self.assertEqual(f.reference, f'BROUILLON-{f.pk}')
            self.assertEqual(r.data['reference'], f.reference)
        su = User.objects.create_superuser(
            username=f'atot27_su_{_nxt()}', password='x', email='')
        su.company = self.company
        su.role_legacy = 'admin'
        su.save(update_fields=['company', 'role_legacy'])
        api_su = APIClient()
        api_su.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(su)}')
        resp = api_su.delete(
            f"/api/django/ventes/factures/{premier.data['id']}/")
        self.assertEqual(resp.status_code, 204, getattr(resp, 'data', resp))
        for r, attendu in ((second, f'FAC-{mois}-0001'),
                           (troisieme, f'FAC-{mois}-0002')):
            resp = self._emettre(r.data['id'])
            self.assertEqual(resp.status_code, 200, resp.data)
            self.assertEqual(resp.data['reference'], attendu)
            self.assertEqual(
                Facture.objects.get(pk=r.data['id']).reference, attendu)
        # CLAUSE PERSISTANCE — la série relue est continue, triée par
        # date d'émission ; l'audit de numérotation n'y voit aucun trou.
        serie = list(Facture.objects.filter(company=self.company)
                     .exclude(statut=Facture.Statut.BROUILLON)
                     .order_by('date_emission', 'id')
                     .values_list('reference', flat=True))
        self.assertEqual(serie, [f'FAC-{mois}-0001', f'FAC-{mois}-0002'])
        self.assertTrue(audit_company(self.company)['conforme'])

    def test_portes_emises_numerotees_dans_l_ordre(self):
        mois = self._mois()
        brouillon = self._porte('bc', self._devis())
        self.assertEqual(brouillon.status_code, 201, brouillon.data)
        refs = []
        for porte in ('tranche', 'complete', 'consolidee'):
            r = self._porte(porte, self._devis())
            self.assertEqual(r.status_code, 201, r.data)
            refs.append(r.data.get('facture_reference')
                        or r.data['reference'])
        self.assertEqual(refs, [f'FAC-{mois}-{n:04d}' for n in (1, 2, 3)])
        resp = self._emettre(brouillon.data['id'])
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['reference'], f'FAC-{mois}-0004')

    def test_pdf_brouillon_porte_brouillon(self):
        """CLAUSE CLIENT — le PDF d'un brouillon imprime « BROUILLON-<id> »,
        jamais un numéro de la série."""
        from apps.ventes.models import Facture
        from apps.ventes.utils.pdf import _render_html
        r = self._porte('bc', self._devis())
        self.assertEqual(r.status_code, 201, r.data)
        facture = Facture.objects.get(pk=r.data['id'])
        html = _render_html('facture.html', {
            'facture': facture, 'entreprise_nom': 'ATOT27',
            'entreprise_adresse': '', 'entreprise_email': '',
            'entreprise_telephone': '', 'entreprise_siret': '',
            'entreprise_tva_intra': '', 'couleur_principale': '#059669',
            'logo_uri': None, 'signature_uri': None, 'rib': '',
            'banque': ''})
        self.assertIn(f'BROUILLON-{facture.pk}', html)


class PortesSavInterventionNumeroTests(TestCase):
    """AFAC90 (sonde W5-1, classe C-ATOT-018) — portes 6 (ticket SAV) et 7
    (intervention) : le brouillon qu'elles créent ne porte aucun numéro
    légal ; ``emettre_facture`` lui attribue le suivant de la série. Totaux
    au prix catalogue HT (1 000 HT, TVA 20 %, 1 200 TTC)."""
    setUp = PortesFacturationTests.setUp
    _emettre = NumeroEmissionTests._emettre
    _mois = NumeroEmissionTests._mois

    def _onduleur(self):
        from apps.stock.models import Produit
        return Produit.objects.create(
            company=self.company, nom='Onduleur AFAC90',
            sku=f'AFAC90-OND-{_nxt()}', prix_vente=Decimal('1000'),
            prix_achat=Decimal('600'), tva=Decimal('20'), quantite_stock=10)

    def _ticket(self, produit):
        from apps.sav.models import PieceConsommee, Ticket
        ticket = Ticket.objects.create(
            company=self.company, reference=f'SAV-AFAC90-{_nxt()}',
            client=self.client_obj, type=Ticket.Type.CORRECTIF,
            couverture=Ticket.Couverture.FACTURABLE, created_by=self.user)
        PieceConsommee.objects.create(
            company=self.company, ticket=ticket, produit=produit,
            quantite=Decimal('1'), created_by=self.user)
        return ticket

    def _intervention(self, produit, ticket=None):
        from apps.installations.models import (
            ConsommationLigne, Installation, Intervention,
            MaterielConsommation,
        )
        chantier = Installation.objects.create(
            company=self.company, reference=f'CHT-AFAC90-{_nxt()}',
            client=self.client_obj)
        interv = Intervention.objects.create(
            company=self.company, installation=chantier, ticket=ticket,
            type_intervention='depannage', created_by=self.user)
        conso = MaterielConsommation.objects.create(
            company=self.company, intervention=interv)
        ConsommationLigne.objects.create(
            company=self.company, consommation=conso, produit=produit,
            designation=produit.nom, quantite_prevue=Decimal('1'),
            quantite_utilisee=Decimal('1'))
        return interv

    def _verifier_brouillon_puis_emission(self, facture_id, reference):
        from apps.ventes.models import Facture
        facture = Facture.objects.get(pk=facture_id)
        self.assertEqual(facture.statut, Facture.Statut.BROUILLON)
        self.assertEqual(reference, f'BROUILLON-{facture.pk}')
        self.assertEqual(facture.reference, reference)
        self.assertEqual(
            (facture.total_ht, facture.total_tva, facture.total_ttc),
            (Decimal('1000'), Decimal('200'), Decimal('1200')))
        resp = self._emettre(facture.pk)
        self.assertEqual(resp.status_code, 200, resp.data)
        attendu = f'FAC-{self._mois()}-0001'
        self.assertEqual(resp.data['reference'], attendu)
        self.assertEqual(Facture.objects.get(pk=facture.pk).reference, attendu)

    def test_ticket_sav_brouillon_sans_numero_legal(self):
        ticket = self._ticket(self._onduleur())
        r = self.api.post(
            f'/api/django/sav/tickets/{ticket.id}/facturer/', {},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self._verifier_brouillon_puis_emission(
            r.data['facture_id'], r.data['facture_reference'])

    def test_intervention_brouillon_sans_numero_legal(self):
        interv = self._intervention(self._onduleur())
        r = self.api.post(
            f'/api/django/installations/interventions/{interv.id}/'
            'generer-facture/', {}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self._verifier_brouillon_puis_emission(
            r.data['facture_id'], r.data['facture_reference'])


class PortesSavInterventionConcurrenceTests(TestCase):
    """AFAC91 (sonde W5-1) — « double clic » : le ticket / l'intervention est
    lu DEUX fois avant toute écriture ; le générateur appelé avec la seconde
    instance PÉRIMÉE renvoie la MÊME facture (relecture sous verrou), une
    seule facture non annulée existe et le lien pointe sur elle."""
    setUp = PortesFacturationTests.setUp
    _onduleur = PortesSavInterventionNumeroTests._onduleur
    _ticket = PortesSavInterventionNumeroTests._ticket
    _intervention = PortesSavInterventionNumeroTests._intervention

    def _une_seule_facture(self, f1, f2):
        from apps.ventes.models import Facture
        self.assertEqual(f1.pk, f2.pk)
        self.assertEqual(
            Facture.objects.filter(company=self.company)
            .exclude(statut=Facture.Statut.ANNULEE).count(), 1)

    def test_ticket_deux_instances_une_facture(self):
        from apps.sav.models import Ticket
        from apps.ventes.services import generer_facture_ticket_sav
        ticket = self._ticket(self._onduleur())
        premiere = Ticket.objects.get(pk=ticket.pk)
        seconde = Ticket.objects.get(pk=ticket.pk)
        f1 = generer_facture_ticket_sav(
            ticket=premiere, sous_garantie=False, user=self.user,
            pieces=list(premiere.pieces.select_related('produit')))
        f2 = generer_facture_ticket_sav(
            ticket=seconde, sous_garantie=False, user=self.user,
            pieces=list(seconde.pieces.select_related('produit')))
        self._une_seule_facture(f1, f2)
        self.assertEqual(
            Ticket.objects.get(pk=ticket.pk).facture_id_ext, f1.pk)

    def test_intervention_deux_instances_une_facture(self):
        from apps.installations.models import Intervention
        from apps.ventes.services import generer_facture_intervention
        interv = self._intervention(self._onduleur())
        premiere = Intervention.objects.get(pk=interv.pk)
        seconde = Intervention.objects.get(pk=interv.pk)
        f1 = generer_facture_intervention(intervention=premiere, user=self.user)
        f2 = generer_facture_intervention(intervention=seconde, user=self.user)
        self._une_seule_facture(f1, f2)
        self.assertEqual(Intervention.objects.get(pk=interv.pk).facture_id, f1.pk)


class PorteInterventionTicketTests(TestCase):
    """AFAC92 (sonde W5-2, classe C-ATOT-001) — contrat ZFSM4 « hors
    contrat/ticket » : une intervention rattachée à un ticket SAV déjà
    facturé est REFUSÉE (400 français), aucune seconde facture ; une
    intervention sans ticket reste facturable (201 puis 200)."""
    setUp = PortesFacturationTests.setUp
    _onduleur = PortesSavInterventionNumeroTests._onduleur
    _ticket = PortesSavInterventionNumeroTests._ticket
    _intervention = PortesSavInterventionNumeroTests._intervention

    def _generer(self, interv):
        return self.api.post(
            f'/api/django/installations/interventions/{interv.id}/'
            'generer-facture/', {}, format='json')

    def test_intervention_rattachee_ticket_refusee(self):
        from apps.ventes.models import Facture
        onduleur = self._onduleur()
        ticket = self._ticket(onduleur)
        r = self.api.post(
            f'/api/django/sav/tickets/{ticket.id}/facturer/', {},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(
            Facture.objects.get(pk=r.data['facture_id']).total_ttc,
            Decimal('1200'))
        interv = self._intervention(onduleur, ticket=ticket)
        resp = self._generer(interv)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(
            resp.data['detail'],
            'Intervention rattachée à un ticket SAV : facturez depuis le '
            'ticket.')
        # CLAUSE PERSISTANCE — une seule facture pour la visite (le ticket).
        self.assertEqual(
            Facture.objects.filter(company=self.company)
            .exclude(statut=Facture.Statut.ANNULEE).count(), 1)
        interv.refresh_from_db()
        self.assertIsNone(interv.facture_id)

    def test_intervention_sans_ticket_facturable(self):
        interv = self._intervention(self._onduleur())
        r1 = self._generer(interv)
        self.assertEqual(r1.status_code, 201, r1.data)
        r2 = self._generer(interv)
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertTrue(r2.data['deja_existant'])
        self.assertEqual(r1.data['facture_id'], r2.data['facture_id'])
