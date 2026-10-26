"""Revue chantier du 26/10/2026 — fin de chantier : réception, pack de remise,
portail client, clôture.

Nouveau fichier car : lanes parallèles file-disjointes de la revue chantier du
26/10/2026.

Couvre :
  * G1 — la pièce « garanties » du pack de remise est PRÉSENTE dès que le parc
    va produire les dates de garantie à la réception (chaque produit qui
    entrera au parc a une durée de garantie), sinon son détail nomme les
    produits sans durée (« Garantie non renseignée : … ») — fin du cercle
    « il faut un équipement garanti pour passer la remise qui crée le parc » ;
  * G5/G6 — le PV de réception et le bon de livraison figés au geste
    « signer-client » sont partagés avec le client (« Mes documents » du
    portail) ; l'e-mail « jalon Réception atteint » le dit ;
  * G14 — `avertissements_cloture` : phrases consultatives (jamais un
    blocage), exposées sur le détail d'un chantier « Réceptionné » seulement ;
  * P29 — la ligne d'historique « Chantier créé » dit l'acceptation client en
    ligne quand il n'y a pas d'utilisateur (plus de « par ? »).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_revue_chantier_reception"
"""
import itertools
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import (
    CommissioningRecord, Installation, InstallationActivity, JalonProjet,
)
from apps.installations.services import (
    _apply_reception_handover, _notifier_client_jalon_atteint,
    assemble_handover_pieces, avertissements_cloture,
    create_installation_from_devis, ensure_checklist_items,
    ensure_commissioning_record, seed_stages, verifier_transition_statut,
)
from apps.sav.models import Equipement
from apps.stock.models import Categorie, Produit
from apps.ventes.models import Devis, Facture, LigneDevis, Paiement
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations/chantiers'
SIG = ('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAf'
       'FcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')
SIG_B = ('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAf'
         'FcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg==')


def make_company():
    n = next(_seq)
    return Company.objects.create(slug=f'rcr-co-{n}', nom=f'RCR Co {n}')


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'rcr-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Alaoui', prenom='RCR',
        email=f'rcr-{n}@example.invalid', telephone=f'+2126000{n:05d}')


def make_installation(company, client=None, **extra):
    n = next(_seq)
    extra.setdefault('statut', Installation.Statut.INSTALLE)
    return Installation.objects.create(
        company=company, reference=f'CHT-RCR-{n}', client=client, **extra)


def make_produit(company, nom, type_equipement=None, garantie_mois=None):
    n = next(_seq)
    categorie = None
    if type_equipement:
        categorie, _ = Categorie.objects.get_or_create(
            company=company, nom=f'Cat {type_equipement}',
            defaults={'type_equipement': type_equipement})
    return Produit.objects.create(
        company=company, nom=nom, sku=f'RCR-{n}', categorie=categorie,
        prix_vente=Decimal('100'), garantie_mois=garantie_mois)


def ligne(produit, designation=None, quantite=1):
    return {'produit_id': produit.id,
            'designation': designation or produit.nom, 'quantite': quantite}


def piece(resume, type_piece):
    return next(p for p in resume['pieces'] if p['type'] == type_piece)


class GarantiesPieceTests(TestCase):
    """G1 — fin du cercle « garantie exigée avant le parc qui la crée »."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)

    def test_presente_quand_chaque_produit_du_parc_a_une_garantie(self):
        onduleur = make_produit(
            self.company, 'Onduleur G1', 'onduleur', garantie_mois=60)
        cable = make_produit(self.company, 'Câble G1', 'cable')  # hors parc
        inst = make_installation(self.company)
        inst.bom = [ligne(onduleur), ligne(cable, quantite=50)]
        inst.save(update_fields=['bom'])
        self.assertFalse(inst.equipements.exists())
        garanties = piece(assemble_handover_pieces(inst), 'garanties')
        self.assertTrue(garanties['present'], garanties)
        self.assertIsNone(garanties['detail'])
        self.assertIn('1 produit(s) garanti(s)', garanties['reference'])

    def test_absente_et_detail_nomme_les_produits_sans_garantie(self):
        garanti = make_produit(
            self.company, 'Panneau G1', 'panneau', garantie_mois=120)
        sans = make_produit(self.company, 'Onduleur X', 'onduleur')
        inst = make_installation(self.company)
        inst.bom = [ligne(garanti), ligne(sans, 'Onduleur X')]
        inst.save(update_fields=['bom'])
        garanties = piece(assemble_handover_pieces(inst), 'garanties')
        self.assertFalse(garanties['present'])
        self.assertEqual(
            garanties['detail'], 'Garantie non renseignée : Onduleur X')

    def test_nomenclature_vide_ou_hors_parc_ne_vaut_pas_garantie(self):
        cable = make_produit(self.company, 'Câble G1', 'cable')
        vide = make_installation(self.company)
        hors_parc = make_installation(self.company)
        hors_parc.bom = [ligne(cable, quantite=20)]
        hors_parc.save(update_fields=['bom'])
        for inst in (vide, hors_parc):
            garanties = piece(assemble_handover_pieces(inst), 'garanties')
            self.assertFalse(garanties['present'])
            self.assertIsNone(garanties['detail'])

    def test_un_equipement_garanti_existant_suffit_toujours(self):
        produit = make_produit(self.company, 'Onduleur G1', 'onduleur')
        inst = make_installation(self.company)
        Equipement.objects.create(
            company=self.company, installation=inst, produit=produit,
            date_fin_garantie=date(2030, 1, 1))
        garanties = piece(assemble_handover_pieces(inst), 'garanties')
        self.assertTrue(garanties['present'])
        self.assertEqual(garanties['reference'], '1 équipement(s) couvert(s)')

    def test_produit_d_une_autre_societe_ignore(self):
        autre = make_company()
        etranger = make_produit(autre, 'Onduleur étranger', 'onduleur', 60)
        inst = make_installation(self.company)
        inst.bom = [ligne(etranger)]
        inst.save(update_fields=['bom'])
        garanties = piece(assemble_handover_pieces(inst), 'garanties')
        self.assertFalse(garanties['present'])

    def test_remise_passe_sans_serie_puis_le_parc_pose_les_dates(self):
        """Étapes semées : « Remise au client » exige le pack ; avant le
        correctif, aucune garantie ne pouvait exister avant la réception."""
        seed_stages(self.company)
        produit = make_produit(
            self.company, 'Onduleur G1', 'onduleur', garantie_mois=60)
        inst = make_installation(
            self.company, bom=[], date_reception=date(2026, 10, 1))
        inst.bom = [ligne(produit)]
        inst.save(update_fields=['bom'])
        rec = ensure_commissioning_record(inst)
        rec.resultat = CommissioningRecord.Resultat.CONFORME
        rec.save(update_fields=['resultat'])
        for item in ensure_checklist_items(inst):
            item.fait = True
            item.save(update_fields=['fait'])
        from apps.installations.models import DocumentProjet
        DocumentProjet.objects.create(
            company=self.company, installation=inst,
            type_doc='schema_unifilaire', titre='Schéma')
        inst.refresh_from_db()
        raisons = verifier_transition_statut(
            inst, Installation.Statut.RECEPTIONNE)
        self.assertFalse(
            any('Pack de remise incomplet' in r for r in raisons), raisons)
        _apply_reception_handover(
            inst, Installation.Statut.INSTALLE,
            Installation.Statut.RECEPTIONNE, self.user)
        equipement = inst.equipements.get()
        self.assertIsNotNone(equipement.date_fin_garantie)

    def test_gate_cite_le_produit_sans_garantie(self):
        seed_stages(self.company)
        sans = make_produit(self.company, 'Onduleur X', 'onduleur')
        inst = make_installation(self.company)
        inst.bom = [ligne(sans, 'Onduleur X')]
        inst.save(update_fields=['bom'])
        raisons = verifier_transition_statut(
            inst, Installation.Statut.RECEPTIONNE)
        self.assertTrue(
            any('Garantie non renseignée : Onduleur X' in r
                for r in raisons), raisons)


class PortailDocumentsRemiseTests(TestCase):
    """G5/G6 — le client retrouve le PV et le BL signés dans « Mes documents »."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.client_obj = make_client(self.company)
        self.inst = make_installation(self.company, self.client_obj)

    def _signer(self):
        return self.api.post(
            f'{BASE}/{self.inst.pk}/signer-client/',
            {'signature_client': SIG, 'signataire_nom': 'Samir Alaoui'},
            format='json')

    def _documents_portail(self, company, client):
        from apps.ged.selectors import documents_partages_client_portail
        return list(documents_partages_client_portail(company, client.id))

    def test_signature_partage_le_pv_et_le_bl_avec_le_client(self):
        from apps.documents import builders
        from apps.ged import services as ged_services
        self.assertEqual(
            self._documents_portail(self.company, self.client_obj), [])
        r = self._signer()
        self.assertEqual(r.status_code, 200, r.data)
        attendus = {
            ged_services.find_document_by_source(
                self.company, source_type=source,
                source_id=self.inst.pk).pk
            for source in (builders.SOURCE_PV_RECEPTION,
                           builders.SOURCE_BON_LIVRAISON)}
        vus = {d.pk for d in self._documents_portail(
            self.company, self.client_obj)}
        self.assertEqual(len(attendus), 2)
        self.assertEqual(vus, attendus)

    def test_resignature_ne_duplique_pas_le_partage(self):
        from apps.ged.models import AclGed
        self.assertEqual(self._signer().status_code, 200)
        r = self.api.post(
            f'{BASE}/{self.inst.pk}/signer-client/',
            {'signature_client': SIG_B,
             'signataire_nom': 'Samir Alaoui',
             'motif_override_signature': 'Signature illisible'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(
            AclGed.objects.filter(
                company=self.company, client=self.client_obj).count(), 2)

    def test_un_autre_client_ou_une_autre_societe_ne_voit_rien(self):
        self.assertEqual(self._signer().status_code, 200)
        autre_client = make_client(self.company)
        self.assertEqual(
            self._documents_portail(self.company, autre_client), [])
        autre_societe = make_company()
        client_etranger = make_client(autre_societe)
        self.assertEqual(
            self._documents_portail(autre_societe, client_etranger), [])
        # Même identifiant de client, mauvaise société : introuvable.
        self.assertEqual(
            self._documents_portail(autre_societe, self.client_obj), [])

    def test_service_de_partage_est_idempotent_et_scope(self):
        from apps.documents import builders
        from apps.ged import services as ged_services
        self.assertEqual(self._signer().status_code, 200)
        document = ged_services.find_document_by_source(
            self.company, source_type=builders.SOURCE_PV_RECEPTION,
            source_id=self.inst.pk)
        a = ged_services.partager_document_avec_client_portail(
            document, self.client_obj.id)
        b = ged_services.partager_document_avec_client_portail(
            document, self.client_obj.id)
        self.assertEqual(a.pk, b.pk)
        self.assertEqual(a.company_id, self.company.id)
        self.assertEqual(a.niveau, 'lecture')
        self.assertIsNone(
            ged_services.partager_document_avec_client_portail(document, None))

    def _jalon(self, phase, libelle):
        return JalonProjet.objects.create(
            company=self.company, installation=self.inst, phase=phase,
            libelle=libelle, atteint=True)

    def test_email_reception_mentionne_les_documents(self):
        jalon = self._jalon(JalonProjet.Phase.RECEPTION, 'Réception')
        with patch('apps.ventes.email_service.is_email_configured',
                   return_value=True), \
                patch('apps.portail.selectors.compte_portail_client_actif',
                      return_value=True):
            _notifier_client_jalon_atteint(self.inst, jalon)
        self.assertEqual(len(mail.outbox), 1)
        corps = mail.outbox[0].body
        self.assertIn('Mes documents', corps)
        self.assertIn('procès-verbal de réception', corps)

    def test_email_d_un_autre_jalon_ne_parle_pas_des_documents(self):
        jalon = self._jalon(JalonProjet.Phase.POSE, 'Pose')
        with patch('apps.ventes.email_service.is_email_configured',
                   return_value=True), \
                patch('apps.portail.selectors.compte_portail_client_actif',
                      return_value=True):
            _notifier_client_jalon_atteint(self.inst, jalon)
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn('Mes documents', mail.outbox[0].body)


class ChatterCreationTests(TestCase):
    """P29 — plus de « Chantier créé par ? »."""

    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)

    def _devis(self):
        n = next(_seq)
        return Devis.objects.create(
            company=self.company, reference=f'DEV-RCR-{n:04d}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), mode_installation='residentiel')

    def _corps_creation(self, inst):
        return InstallationActivity.objects.get(
            installation=inst, kind=InstallationActivity.Kind.CREATION).body

    def test_acceptation_client_en_ligne_sans_utilisateur(self):
        devis = self._devis()
        inst, cree = create_installation_from_devis(
            devis, None, self.company)
        self.assertTrue(cree)
        self.assertEqual(
            self._corps_creation(inst),
            f"Chantier créé à l'acceptation du devis {devis.reference} "
            "(acceptation client en ligne)")

    def test_acceptation_par_un_utilisateur(self):
        devis = self._devis()
        user = make_user(self.company)
        inst, _ = create_installation_from_devis(devis, user, self.company)
        self.assertEqual(
            self._corps_creation(inst),
            f"Chantier créé à l'acceptation du devis {devis.reference} "
            f"par {user.username}")


class AvertissementsClotureTests(TestCase):
    """G14 — consultatifs, jamais bloquants, détail « Réceptionné » seulement."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.client_obj = make_client(self.company)

    def _devis_avec_prix(self):
        n = next(_seq)
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-RCR-C{n:04d}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), mode_installation='residentiel')
        produit = make_produit(self.company, f'Panneau C{n}', 'panneau')
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=produit.nom,
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), taux_tva=Decimal('20.00'))
        return devis

    def _facture(self, devis, statut):
        from apps.ventes.selectors import etat_vente
        ttc = Decimal(etat_vente(devis)['prix_convenu_ttc'])
        return Facture.objects.create(
            company=self.company, reference=f'FAC-RCR-{next(_seq):04d}',
            devis=devis, client=self.client_obj, statut=statut,
            type_facture='solde', montant_ht=(ttc / Decimal('1.2')).quantize(
                Decimal('0.01')),
            montant_tva=(ttc - ttc / Decimal('1.2')).quantize(
                Decimal('0.01')),
            montant_ttc=ttc, created_by=self.user), ttc

    def _chantier(self, devis=None, **extra):
        extra.setdefault('statut', Installation.Statut.RECEPTIONNE)
        return make_installation(
            self.company, self.client_obj, devis=devis, **extra)

    def test_solde_non_facture(self):
        inst = self._chantier(devis=self._devis_avec_prix())
        self.assertIn('Solde non facturé', avertissements_cloture(inst))

    def test_solde_facture_non_encaisse(self):
        devis = self._devis_avec_prix()
        self._facture(devis, Facture.Statut.EMISE)
        inst = self._chantier(devis=devis)
        avertissements = avertissements_cloture(inst)
        self.assertNotIn('Solde non facturé', avertissements)
        self.assertIn('Solde non encaissé', avertissements)

    def test_solde_encaisse_plus_aucun_avertissement_financier(self):
        devis = self._devis_avec_prix()
        facture, ttc = self._facture(devis, Facture.Statut.PAYEE)
        Paiement.objects.create(
            company=self.company, facture=facture, montant=ttc,
            date_paiement=date.today(), mode='virement',
            created_by=self.user)
        inst = self._chantier(devis=devis)
        avertissements = avertissements_cloture(inst)
        self.assertNotIn('Solde non facturé', avertissements)
        self.assertNotIn('Solde non encaissé', avertissements)

    def test_sans_devis_aucun_avertissement_financier(self):
        avertissements = avertissements_cloture(self._chantier())
        self.assertNotIn('Solde non facturé', avertissements)
        self.assertNotIn('Solde non encaissé', avertissements)

    def test_reception_definitive_site_pro_seulement(self):
        pro = self._chantier(
            type_installation=Installation.TypeInstallation.INDUSTRIEL)
        residentiel = self._chantier(
            type_installation=Installation.TypeInstallation.RESIDENTIEL)
        self.assertIn('Réception définitive non prononcée',
                      avertissements_cloture(pro))
        self.assertNotIn('Réception définitive non prononcée',
                         avertissements_cloture(residentiel))
        Installation.objects.filter(pk=pro.pk).update(
            date_reception_definitive=date(2026, 10, 20))
        pro.refresh_from_db()
        self.assertNotIn('Réception définitive non prononcée',
                         avertissements_cloture(pro))

    def test_series_manquantes_au_parc(self):
        onduleur = make_produit(
            self.company, 'Onduleur C', 'onduleur', garantie_mois=60)
        inst = self._chantier()
        inst.bom = [ligne(onduleur, quantite=3)]
        inst.save(update_fields=['bom'])
        Equipement.objects.create(
            company=self.company, installation=inst, produit=onduleur,
            numero_serie='SN-RCR-1')
        self.assertIn('2 séries manquantes au parc',
                      avertissements_cloture(inst))
        for n in (2, 3):
            Equipement.objects.create(
                company=self.company, installation=inst, produit=onduleur,
                numero_serie=f'SN-RCR-{n}')
        self.assertFalse(any('série' in a
                             for a in avertissements_cloture(inst)))

    def test_pack_incomplet_liste_les_pieces_manquantes(self):
        avertissements = avertissements_cloture(self._chantier())
        pack = [a for a in avertissements
                if a.startswith('Pack de remise incomplet')]
        self.assertEqual(len(pack), 1)
        self.assertIn('Certificat de recette', pack[0])

    def test_detail_receptionne_expose_la_liste_hors_receptionne_null(self):
        recep = self._chantier()
        installe = self._chantier(statut=Installation.Statut.INSTALLE)
        r = self.api.get(f'{BASE}/{recep.pk}/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsInstance(r.data['avertissements_cloture'], list)
        self.assertTrue(any(
            a.startswith('Pack de remise incomplet')
            for a in r.data['avertissements_cloture']))
        r = self.api.get(f'{BASE}/{installe.pk}/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNone(r.data['avertissements_cloture'])

    def test_liste_ne_calcule_pas_les_avertissements(self):
        self._chantier()
        r = self.api.get(f'{BASE}/')
        self.assertEqual(r.status_code, 200, r.data)
        lignes = r.data['results'] if isinstance(r.data, dict) else r.data
        self.assertTrue(lignes)
        for row in lignes:
            self.assertIsNone(row['avertissements_cloture'])

    def test_autre_societe_ne_voit_pas_le_chantier(self):
        inst = self._chantier()
        autre = make_user(make_company())
        r = auth(autre).get(f'{BASE}/{inst.pk}/')
        self.assertEqual(r.status_code, 404)
