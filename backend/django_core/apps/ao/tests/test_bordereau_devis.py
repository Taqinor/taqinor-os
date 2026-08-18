"""UN SEUL chemin de chiffrage : bordereau des prix (BOQ) → devis ventes.

Le bordereau d'un appel d'offres n'avait AUCUN lien avec le moteur de devis :
un chiffrage d'AO se re-saisissait à la main pour sortir un devis client. Le
point de contact unique ``apps.ventes.services.creer_devis_depuis_bordereau``
(symétrique de ``apps.ao.services.creer_appel_offre_depuis_avis``) ferme cette
traversée, et l'action ``POST /ao/bordereaux-prix/<id>/creer-devis/`` l'appelle
PAR RÉFÉRENCE — ``ao`` n'importe jamais ``apps.ventes.models``.

Ce qui est prouvé ici :

* la réponse est CONFORME à l'échantillon committé
  ``contract_samples/ao_bordereau_devis.json`` (PACT10) ;
* le devis reprend la STRUCTURE du bordereau (sections en intertitres, lignes
  dans l'ordre, TVA par ligne, remise de ligne, remise globale) et ses TOTAUX
  au centime — la chaîne HT → remise → TVA → TTC est la MÊME des deux côtés ;
* la référence passe par la fabrique anti-collision (``DEV-YYYYMM-NNNN``),
  JAMAIS ``count()+1`` ;
* l'action est IDEMPOTENTE : un second appel réouvre le brouillon existant ;
* le devis naît ``brouillon`` et n'ouvre aucun statut aval (règle #4) ;
* sans client résoluble, le refus est un 400 FRANÇAIS qui nomme le geste ;
* un bordereau d'une AUTRE société est INTROUVABLE (404).

Run :
    python manage.py test apps.ao.tests.test_bordereau_devis -v2
"""
import json
import pathlib
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao.models import (
    AppelOffre, BordereauPrix, LigneBordereau, SectionBordereau,
)
from apps.crm.models import Lead
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.services import creer_devis_depuis_bordereau
from authentication.models import Company

User = get_user_model()

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'ao_bordereau_devis.json').read_text(encoding='utf-8'))

CLAUSE = ("Marché à prix unitaires : les quantités portées au présent "
          "bordereau sont prévisionnelles.")


def url_creer_devis(pk):
    return f'/api/django/ao/bordereaux-prix/{pk}/creer-devis/'


class BaseChiffrage(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Chiffrage Co',
                                              slug='chiffrage-co')
        self.role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='chiffrage_dir', password='x', company=self.company,
            role=self.role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.lead = Lead.objects.create(
            company=self.company, nom='Commune urbaine de Rabat',
            email='marches@rabat.ma')
        self.affaire = AppelOffre.objects.create(
            company=self.company, reference='AO-BOQ-1',
            objet='Centrale PV 500 kWc', lead_id=self.lead.pk)
        self.bordereau = BordereauPrix.objects.create(
            company=self.company, appel_offre=self.affaire,
            clause_reserve=CLAUSE)
        self.section_a = SectionBordereau.objects.create(
            company=self.company, bordereau=self.bordereau, numero='A',
            libelle='Bâtiment A', ordre=1)
        self.section_b = SectionBordereau.objects.create(
            company=self.company, bordereau=self.bordereau, numero='B',
            libelle='Prestations communes', ordre=2)
        self._ligne(1, self.section_a, 'Modules photovoltaïques 625 Wc', 'U',
                    '100', '1200.00', taux_tva=Decimal('20.00'))
        self._ligne(2, self.section_a, 'Onduleur 60 kWc', 'U', '2',
                    '41000.00', taux_tva=Decimal('20.00'))
        self._ligne(3, self.section_b, 'Câbles DC', 'ml', '300', '45.00',
                    taux_tva=Decimal('10.00'))

    def _ligne(self, numero, section, designation, unite, quantite, pu,
               **extra):
        return LigneBordereau.objects.create(
            company=self.company, bordereau=self.bordereau, section=section,
            numero=numero, designation=designation, unite=unite,
            quantite=Decimal(quantite), prix_unitaire=Decimal(pu), **extra)

    def _voisin(self):
        autre = Company.objects.create(nom='Chiffrage Voisin',
                                       slug='chiffrage-voisin')
        role = Role.objects.create(company=autre, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        user = User.objects.create_user(username='chiffrage_voisin',
                                        password='x', company=autre,
                                        role=role)
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return client


class LeContratEstRespecte(BaseChiffrage):
    def test_cles_de_premier_niveau_identiques_a_l_echantillon(self):
        reponse = self.api.post(url_creer_devis(self.bordereau.pk))
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(sorted(reponse.data), sorted(CONTRAT['exemple']))
        self.assertEqual(sorted(reponse.data['devis']),
                         sorted(CONTRAT['exemple']['devis']))

    def test_second_appel_meme_forme_et_cree_faux(self):
        premiere = self.api.post(url_creer_devis(self.bordereau.pk))
        seconde = self.api.post(url_creer_devis(self.bordereau.pk))
        self.assertEqual(seconde.status_code, 200, seconde.data)
        self.assertEqual(sorted(seconde.data),
                         sorted(CONTRAT['exemple_deja_cree']))
        self.assertFalse(seconde.data['cree'])
        self.assertEqual(seconde.data['devis']['id'],
                         premiere.data['devis']['id'])
        self.assertEqual(Devis.objects.filter(company=self.company).count(), 1)


class LaStructureDuBordereauEstReprise(BaseChiffrage):
    def test_sections_en_intertitres_puis_lignes_dans_l_ordre(self):
        self.api.post(url_creer_devis(self.bordereau.pk))
        devis = Devis.objects.get(company=self.company)
        lignes = list(devis.lignes.order_by('ordre', 'id'))
        self.assertEqual(
            [(li.type_ligne, li.designation) for li in lignes],
            [
                (LigneDevis.TypeLigne.SECTION, 'A — Bâtiment A'),
                (LigneDevis.TypeLigne.PRODUIT,
                 'Modules photovoltaïques 625 Wc'),
                (LigneDevis.TypeLigne.PRODUIT, 'Onduleur 60 kWc'),
                (LigneDevis.TypeLigne.SECTION, 'B — Prestations communes'),
                (LigneDevis.TypeLigne.PRODUIT, 'Câbles DC (ml)'),
                # La clause de réserve FERME le devis, en ligne NOTE : sans
                # elle, les quantités reprises deviennent un engagement ferme.
                (LigneDevis.TypeLigne.NOTE, CLAUSE),
            ])

    def test_les_intertitres_ne_portent_aucun_prix(self):
        self.api.post(url_creer_devis(self.bordereau.pk))
        devis = Devis.objects.get(company=self.company)
        for ligne in devis.lignes.filter(
                type_ligne=LigneDevis.TypeLigne.SECTION):
            self.assertIsNone(ligne.quantite)
            self.assertIsNone(ligne.prix_unitaire)
            self.assertFalse(ligne.compte_dans_totaux)

    def test_tva_par_ligne_reprise_du_bordereau(self):
        self.api.post(url_creer_devis(self.bordereau.pk))
        devis = Devis.objects.get(company=self.company)
        taux = sorted(
            str(li.taux_tva) for li in devis.lignes.filter(
                type_ligne=LigneDevis.TypeLigne.PRODUIT))
        self.assertEqual(taux, ['10.00', '20.00', '20.00'])

    def test_taux_et_remise_globale_du_bordereau_deviennent_ceux_du_devis(self):
        self.bordereau.taux_tva_defaut = Decimal('10.00')
        self.bordereau.remise_globale_pct = Decimal('5.00')
        self.bordereau.save(update_fields=['taux_tva_defaut',
                                           'remise_globale_pct'])
        self.api.post(url_creer_devis(self.bordereau.pk))
        devis = Devis.objects.get(company=self.company)
        self.assertEqual(devis.taux_tva, Decimal('10.00'))
        self.assertEqual(devis.remise_globale, Decimal('5.00'))

    def test_les_totaux_du_devis_egalent_ceux_du_bordereau(self):
        """La chaîne HT → TVA → TTC est la MÊME des deux côtés, au centime."""
        reponse = self.api.post(url_creer_devis(self.bordereau.pk))
        # Les montants SERVIS (chaîne canonique unique) valent ceux du BOQ.
        self.assertEqual(reponse.data['devis']['total_ht'],
                         str(self.bordereau.total_ht))
        self.assertEqual(reponse.data['devis']['total_ttc'],
                         str(self.bordereau.total_ttc))
        devis = Devis.objects.get(company=self.company)
        self.assertEqual(Decimal(devis.total_ht).quantize(Decimal('0.01')),
                         self.bordereau.total_ht)
        self.assertEqual(Decimal(devis.total_tva).quantize(Decimal('0.01')),
                         self.bordereau.total_tva)
        self.assertEqual(Decimal(devis.total_ttc).quantize(Decimal('0.01')),
                         self.bordereau.total_ttc)


class LeDevisEstUnDevisNormal(BaseChiffrage):
    def test_brouillon_scope_societe_et_relie_au_lead(self):
        self.api.post(url_creer_devis(self.bordereau.pk))
        devis = Devis.objects.get(company=self.company)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertEqual(devis.company_id, self.company.pk)
        self.assertEqual(devis.lead_id, self.lead.pk)
        self.assertIsNotNone(devis.client_id)

    def test_reference_par_la_fabrique_anti_collision(self):
        reponse = self.api.post(url_creer_devis(self.bordereau.pk))
        reference = reponse.data['devis']['reference']
        self.assertRegex(reference, r'^DEV-\d{6}-\d{4}$')

    def test_l_origine_du_devis_est_tracee(self):
        self.api.post(url_creer_devis(self.bordereau.pk))
        devis = Devis.objects.get(company=self.company)
        origine = devis.etude_params['origine']
        self.assertEqual(origine['type'], 'bordereau_ao')
        self.assertEqual(origine['bordereau'], self.bordereau.pk)
        self.assertEqual(origine['appel_offre'], self.affaire.pk)
        self.assertEqual(origine['reference_ao'], 'AO-BOQ-1')

    def test_le_bordereau_n_est_pas_touche(self):
        avant = list(self.bordereau.lignes.values_list('pk', 'quantite',
                                                       'prix_unitaire'))
        self.api.post(url_creer_devis(self.bordereau.pk))
        self.bordereau.refresh_from_db()
        self.assertEqual(
            list(self.bordereau.lignes.values_list('pk', 'quantite',
                                                   'prix_unitaire')), avant)


class LesRefusSontMotivesEnFrancais(BaseChiffrage):
    def test_sans_lead_ni_client_le_refus_nomme_le_geste(self):
        self.affaire.lead_id = None
        self.affaire.save(update_fields=['lead_id'])
        reponse = self.api.post(url_creer_devis(self.bordereau.pk))
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('rattacher-lead', str(reponse.data))
        self.assertFalse(Devis.objects.filter(company=self.company).exists())

    def test_bordereau_sans_ligne_chiffrable_refuse(self):
        vide = BordereauPrix.objects.create(
            company=self.company, appel_offre=self.affaire,
            intitule='Bordereau vide', indice_revision='Z',
            clause_reserve=CLAUSE)
        reponse = self.api.post(url_creer_devis(vide.pk))
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('aucune ligne chiffrable', str(reponse.data))

    def test_quantite_arrondie_est_annoncee(self):
        """Le devis compte au centième, le bordereau au millième."""
        self._ligne(4, self.section_b, 'Terrassement', 'm3',
                    '12.345', '100.00')
        reponse = self.api.post(url_creer_devis(self.bordereau.pk))
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertTrue(any('arrondie' in a
                            for a in reponse.data['avertissements']))
        devis = Devis.objects.get(company=self.company)
        ligne = devis.lignes.get(designation__startswith='Terrassement')
        self.assertEqual(ligne.quantite, Decimal('12.35'))


class LaClauseDeReserveTraverse(BaseChiffrage):
    """``raisons_de_non_conformite()`` REFUSE de rendre remettable un bordereau
    « marché à prix unitaires » sans clause de réserve, parce que « sans elle,
    les quantités du bordereau sont lues comme un engagement ferme ». Le devis
    reprenait les quantités et laissait la clause derrière lui : le document
    remis au CLIENT contredisait celui remis à l'ACHETEUR sur la nature même de
    l'engagement."""

    def test_la_clause_devient_une_ligne_NOTE_du_devis(self):
        self.api.post(url_creer_devis(self.bordereau.pk))
        devis = Devis.objects.get(company=self.company)
        notes = list(devis.lignes.filter(
            type_ligne=LigneDevis.TypeLigne.NOTE))
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].designation, CLAUSE)
        # Une note ne porte AUCUN montant et ne compte dans aucun total.
        self.assertIsNone(notes[0].quantite)
        self.assertIsNone(notes[0].prix_unitaire)
        self.assertFalse(notes[0].compte_dans_totaux)

    def test_la_clause_est_aussi_tracee_dans_l_origine(self):
        """Une ligne NOTE est pour l'ŒIL ; ``origine`` est pour la MACHINE."""
        self.api.post(url_creer_devis(self.bordereau.pk))
        devis = Devis.objects.get(company=self.company)
        origine = devis.etude_params['origine']
        self.assertEqual(origine['clause_reserve'], CLAUSE)
        self.assertTrue(origine['marche_prix_unitaires'])

    def test_un_bordereau_sans_clause_ne_fabrique_aucune_note(self):
        self.bordereau.clause_reserve = ''
        self.bordereau.marche_prix_unitaires = False
        self.bordereau.save(update_fields=['clause_reserve',
                                           'marche_prix_unitaires'])
        self.api.post(url_creer_devis(self.bordereau.pk))
        devis = Devis.objects.get(company=self.company)
        self.assertFalse(devis.lignes.filter(
            type_ligne=LigneDevis.TypeLigne.NOTE).exists())
        self.assertEqual(devis.etude_params['origine']['clause_reserve'], '')


class LArrondiEstLeMemeDesDeuxCotes(BaseChiffrage):
    """HALF_EVEN côté bordereau contre HALF_UP côté devis : les deux écrans
    affichaient deux totaux HT différents pour la MÊME donnée. Le test
    d'origine ne le voyait pas — il ne testait qu'avec remise globale = 0."""

    def test_une_demi_valeur_de_remise_globale_ne_diverge_plus(self):
        # Lignes = 1 000,50 HT ; remise 5 % ⇒ 50,025 EXACTEMENT.
        # HALF_EVEN → 50,02 (950,48) ; HALF_UP → 50,03 (950,47).
        self.bordereau.lignes.all().delete()
        self.bordereau.remise_globale_pct = Decimal('5.00')
        self.bordereau.save(update_fields=['remise_globale_pct'])
        self._ligne(1, self.section_a, 'Poste unique', 'U', '1', '1000.50',
                    taux_tva=Decimal('20.00'))

        self.assertEqual(self.bordereau.montant_remise_globale,
                         Decimal('50.03'))
        self.assertEqual(self.bordereau.total_ht, Decimal('950.47'))

        reponse = self.api.post(url_creer_devis(self.bordereau.pk))
        self.assertEqual(reponse.status_code, 201, reponse.data)
        # L'écran Bordereau et la carte « devis créé » affichent LE MÊME HT.
        self.assertEqual(reponse.data['devis']['total_ht'],
                         str(self.bordereau.total_ht))


class LIdempotenceNeSertPasUnDevisPerime(BaseChiffrage):
    """Le brouillon existant était renvoyé TEL QUEL « en affirmant qu'il en est
    issu » : l'utilisateur corrigeait un prix au bordereau, recliquait « Créer
    le devis », lisait « aucun doublon créé » — et repartait avec un devis
    client obsolète que l'écran ne pouvait plus jamais rafraîchir."""

    def test_bordereau_inchange_zero_ecriture_et_message_de_reouverture(self):
        premiere = self.api.post(url_creer_devis(self.bordereau.pk))
        devis = Devis.objects.get(company=self.company)
        pks_avant = list(devis.lignes.values_list('pk', flat=True))

        seconde = self.api.post(url_creer_devis(self.bordereau.pk))

        self.assertEqual(seconde.status_code, 200, seconde.data)
        self.assertFalse(seconde.data['cree'])
        self.assertEqual(seconde.data['devis']['id'],
                         premiere.data['devis']['id'])
        # Rien n'a bougé : un double-clic reste un no-op COMPLET.
        self.assertEqual(list(devis.lignes.values_list('pk', flat=True)),
                         pks_avant)
        self.assertTrue(any('réouvert' in a
                            for a in seconde.data['avertissements']))

    def test_un_bordereau_modifie_RAFRAICHIT_le_brouillon(self):
        self.api.post(url_creer_devis(self.bordereau.pk))
        ligne = self.bordereau.lignes.get(numero=2)
        ligne.prix_unitaire = Decimal('45000.00')
        ligne.save(update_fields=['prix_unitaire'])

        seconde = self.api.post(url_creer_devis(self.bordereau.pk))

        self.assertEqual(seconde.status_code, 200, seconde.data)
        self.assertFalse(seconde.data['cree'])
        self.assertEqual(Devis.objects.filter(company=self.company).count(), 1)
        devis = Devis.objects.get(company=self.company)
        maj = devis.lignes.get(designation='Onduleur 60 kWc')
        self.assertEqual(maj.prix_unitaire, Decimal('45000.00'))
        # Les totaux servis suivent le bordereau, au centime.
        self.assertEqual(seconde.data['devis']['total_ht'],
                         str(self.bordereau.total_ht))
        self.assertTrue(any('MIS À JOUR' in a
                            for a in seconde.data['avertissements']))

    def test_une_ligne_AJOUTEE_au_bordereau_arrive_dans_le_brouillon(self):
        self.api.post(url_creer_devis(self.bordereau.pk))
        self._ligne(4, self.section_b, 'Génie civil', 'U', '1', '9000.00',
                    taux_tva=Decimal('20.00'))

        self.api.post(url_creer_devis(self.bordereau.pk))

        devis = Devis.objects.get(company=self.company)
        self.assertTrue(devis.lignes.filter(designation='Génie civil').exists())

    def test_une_remise_globale_modifiee_recale_l_entete_du_devis(self):
        self.api.post(url_creer_devis(self.bordereau.pk))
        self.bordereau.remise_globale_pct = Decimal('7.50')
        self.bordereau.save(update_fields=['remise_globale_pct'])

        self.api.post(url_creer_devis(self.bordereau.pk))

        devis = Devis.objects.get(company=self.company)
        self.assertEqual(devis.remise_globale, Decimal('7.50'))

    def test_le_rafraichissement_ne_touche_JAMAIS_le_statut(self):
        self.api.post(url_creer_devis(self.bordereau.pk))
        ligne = self.bordereau.lignes.get(numero=1)
        ligne.quantite = Decimal('150')
        ligne.save(update_fields=['quantite'])

        self.api.post(url_creer_devis(self.bordereau.pk))

        devis = Devis.objects.get(company=self.company)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)


class LaQuantiteHorsGabaritEstRefusEE(BaseChiffrage):
    """``LigneDevis.quantite`` a le MÊME gabarit que le P.U. (10 chiffres, 2
    décimales) alors que ``LigneBordereau.quantite`` monte à 999 999 999,999 :
    le P.U. était gardé, la quantité non — et une ligne « Terrassement » à
    150 000 000 m³ faisait lever un ``numeric field overflow`` DANS la
    transaction, donc un 500 muet au lieu du refus français promis."""

    def test_une_quantite_geante_est_ecartee_avec_un_avertissement(self):
        self._ligne(4, self.section_b, 'Terrassement', 'm3',
                    '150000000.000', '2.00')

        reponse = self.api.post(url_creer_devis(self.bordereau.pk))

        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertTrue(any('hors gabarit' in a
                            for a in reponse.data['avertissements']),
                        reponse.data['avertissements'])
        devis = Devis.objects.get(company=self.company)
        self.assertFalse(devis.lignes.filter(
            designation__startswith='Terrassement').exists())
        # Le reste du devis a bien été repris : une ligne ne perd pas tout.
        self.assertEqual(
            devis.lignes.filter(
                type_ligne=LigneDevis.TypeLigne.PRODUIT).count(), 3)


class LeCloisonnementMultiSociete(BaseChiffrage):
    def test_bordereau_d_une_autre_societe_introuvable(self):
        voisin = self._voisin()
        reponse = voisin.post(url_creer_devis(self.bordereau.pk))
        self.assertEqual(reponse.status_code, 404)
        self.assertFalse(Devis.objects.filter(company=self.company).exists())

    def test_le_service_scope_le_devis_sur_la_societe_du_bordereau(self):
        devis, rapport = creer_devis_depuis_bordereau(
            self.bordereau, user=self.user)
        self.assertTrue(rapport['cree'])
        self.assertEqual(devis.company_id, self.bordereau.company_id)
        self.assertEqual(devis.client.company_id, self.company.pk)
