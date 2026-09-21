"""AOF141 — bascule d'équipement : UNE transaction, ou RIEN.

Le défaut réel que ce module verrouille
=======================================
Dans le dossier du 27/07, la bascule de batterie a été PARTIELLE : le montant
a cascadé jusqu'au bordereau, mais la fiche technique annexée et une
justification de texte sont restées sur l'ancien matériel. Un dossier à moitié
basculé est pire qu'un dossier non basculé — il part avec deux vérités
contradictoires, et c'est le maître d'ouvrage qui les met côte à côte.

Ce qui est prouvé ici :

* le NOUVEAU snapshot est figé depuis le produit cible, le prédécesseur est
  désactivé et chaîné par ``remplace`` ;
* la fiche technique bascule EN UN SEUL GESTE : la nouvelle est annexée ET
  l'ancienne retirée (aucune fiche orpheline ne subsiste) ;
* les grandeurs DÉRIVÉES sont recalculées — et ne sont PAS écrasées par un
  zéro quand rien ne permet de les dériver ;
* les artefacts documentaires produits avant la bascule sont PÉRIMÉS ;
* **ATOMICITÉ** : si une étape échoue — la première comme la dernière — RIEN
  n'est écrit (ni équipement, ni annexe, ni désactivation) ;
* aucun COÛT ne sort du sérialiseur, alors même que le produit du catalogue en
  porte un.

Run :
    python manage.py test apps.ao.tests.test_bascule_equipement -v2
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import services
from apps.ao.fabrique import annexes
from apps.ao.fabrique.coherence import empreinte_dossier
from apps.ao.models import (
    AppelOffre, BatimentAO, BordereauPrix, ControleCoherence, EquipementAO,
    LigneBordereau, PieceDossierAO, ToitureAO, VarianteCalepinage,
)
from apps.ao.permissions import AO_GERER, AO_VOIR
from apps.ao.serializers import EquipementAOSerializer
from apps.records.models import Attachment
from apps.roles.models import Role
from apps.stock.models import Produit
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ao/equipements/'

#: Prix VOLONTAIREMENT distinctifs : ils n'apparaissent dans aucune
#: désignation, donc les retrouver dans une sortie d'API ne peut être qu'une
#: fuite, jamais une coïncidence.
PRIX_ACHAT_ANCIEN = Decimal('1937.00')
PRIX_VENTE_ANCIEN = Decimal('2811.00')
PRIX_ACHAT_NOUVEAU = Decimal('1743.00')
PRIX_VENTE_NOUVEAU = Decimal('2619.00')


class BaseBascule(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF141 Co',
                                              slug='aof141-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-141-1', objet='Bascule')
        self.batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.ancien_produit = Produit.objects.create(
            company=self.company, nom='Batterie BOS-G 100 kWh', marque='BOS',
            sku='BOS-G', prix_vente=PRIX_VENTE_ANCIEN,
            prix_achat=PRIX_ACHAT_ANCIEN, garantie='10 ans')
        self.nouveau_produit = Produit.objects.create(
            company=self.company, nom='Batterie BOS-B Pro-A3', marque='BOS',
            sku='BOS-B-PRO-A3', prix_vente=PRIX_VENTE_NOUVEAU,
            prix_achat=PRIX_ACHAT_NOUVEAU, garantie='10 ans')
        self.fiche_ancienne = self._fiche('fiche-bos-g.pdf')
        self.fiche_nouvelle = self._fiche('fiche-bos-b.pdf')
        self.equipement = services.engager_equipement(
            self.ao, role=EquipementAO.Role.BATTERIE,
            produit_id=self.ancien_produit.id, quantite=Decimal('3'),
            batiment=self.batiment, unite='U',
            fiche_technique=self.fiche_ancienne)

    def _fiche(self, nom):
        return Attachment.objects.create(
            company=self.company, content_object=self.ao,
            file_key=f'ao/{nom}', filename=nom, size=1,
            mime='application/pdf')

    def _etat_des_annexes(self):
        """Verdict d'annexe DÉRIVÉ de la base, au format ``fabrique/annexes``."""
        equipements = list(EquipementAO.objects.filter(appel_offre=self.ao))
        return annexes.controler_annexes(
            [{'reference': e.reference_constructeur,
              'designation': e.designation, 'role': e.role, 'actif': e.actif}
             for e in equipements],
            [{'reference_equipement': e.reference_constructeur,
              'titre': e.designation}
             for e in equipements if e.fiche_technique_id],
        )


class TestBasculeComplete(BaseBascule):
    def setUp(self):
        super().setUp()
        self.resultat = services.basculer_equipement(
            self.equipement, self.nouveau_produit.id, user=None,
            fiche_technique=self.fiche_nouvelle, motif='Gamme arrêtée')
        self.nouveau = EquipementAO.objects.get(
            pk=self.resultat['equipement'].pk)
        self.equipement.refresh_from_db()

    def test_le_nouveau_snapshot_est_fige_depuis_le_produit_cible(self):
        self.assertEqual(self.nouveau.designation, 'Batterie BOS-B Pro-A3')
        self.assertEqual(self.nouveau.marque, 'BOS')
        self.assertEqual(self.nouveau.reference_constructeur, 'BOS-B-PRO-A3')
        self.assertEqual(self.nouveau.produit_id, self.nouveau_produit.id)
        self.assertIsNotNone(self.nouveau.snapshot_le)

    def test_le_contexte_de_l_equipement_est_repris_tel_quel(self):
        """Rôle, bâtiment, quantité et unité ne se re-saisissent pas."""
        self.assertEqual(self.nouveau.role, EquipementAO.Role.BATTERIE)
        self.assertEqual(self.nouveau.batiment_id, self.batiment.id)
        self.assertEqual(self.nouveau.quantite, Decimal('3.000'))
        self.assertEqual(self.nouveau.unite, 'U')

    def test_le_predecesseur_est_desactive_et_chaine(self):
        self.assertFalse(self.equipement.actif)
        self.assertTrue(self.nouveau.actif)
        self.assertEqual(self.nouveau.remplace_id, self.equipement.id)
        self.assertEqual(list(self.equipement.remplace_par.all()),
                         [self.nouveau])

    def test_la_fiche_technique_bascule_en_un_seul_geste(self):
        """La nouvelle est annexée ET l'ancienne retirée — jamais l'une sans l'autre."""
        self.assertEqual(self.nouveau.fiche_technique_id,
                         self.fiche_nouvelle.id)
        self.assertIsNone(self.equipement.fiche_technique_id)

    def test_aucune_fiche_orpheline_ne_subsiste(self):
        verdict = self._etat_des_annexes()
        self.assertEqual(verdict['orphelines'], [])
        self.assertFalse(verdict['bloquant'])
        annexees = [ligne['reference'] for ligne in verdict['index']
                    if ligne['presente']]
        self.assertEqual(annexees, ['BOS-B-PRO-A3'])

    def test_le_rapport_publie_le_plan_de_bascule(self):
        plan = self.resultat['rapport']['plan']
        changements = {(item.get('nature'), item.get('champ'))
                       for item in plan}
        self.assertIn(('champ', 'designation'), changements)
        self.assertIn(('champ', 'reference'), changements)

    def test_le_rapport_ne_porte_aucun_prix(self):
        """Un équipement d'AO n'a pas de prix — le rapport ne peut pas en citer."""
        rendu = str(self.resultat['rapport'])
        for interdit in (str(PRIX_ACHAT_ANCIEN), str(PRIX_ACHAT_NOUVEAU),
                         str(PRIX_VENTE_ANCIEN), str(PRIX_VENTE_NOUVEAU),
                         '1937', '1743', '2811', '2619'):
            self.assertNotIn(interdit, rendu, interdit)

    def test_la_bascule_est_tracee_au_chatter_generique(self):
        from apps.records.models import Activity

        self.assertTrue(Activity.objects.filter(
            company=self.company, field='equipement_bascule').exists())


class TestAtomicite(BaseBascule):
    """Si une étape échoue, RIEN n'est écrit — ni objet, ni annexe."""

    def _etat_avant(self):
        return (EquipementAO.objects.count(),
                self._etat_des_annexes()['index'])

    def _assert_rien_n_a_bouge(self, avant):
        compte, index = avant
        self.assertEqual(EquipementAO.objects.count(), compte)
        self.assertEqual(self._etat_des_annexes()['index'], index)
        self.equipement.refresh_from_db()
        self.assertTrue(self.equipement.actif)
        self.assertEqual(self.equipement.fiche_technique_id,
                         self.fiche_ancienne.id)
        self.assertFalse(EquipementAO.objects.filter(
            fiche_technique=self.fiche_nouvelle).exists())

    def test_une_annexe_impossible_annule_l_equipement_deja_cree(self):
        """Échec APRÈS la création : le nouvel équipement ne survit pas.

        Une fiche qui ne cite aucune référence serait orpheline dès son ajout ;
        ``fabrique/annexes`` refuse, et le refus emporte TOUTE la bascule.
        """
        sans_reference = Produit.objects.create(
            company=self.company, nom='Batterie sans référence',
            prix_vente=Decimal('1.00'))
        avant = self._etat_avant()
        with self.assertRaises(ValidationError):
            services.basculer_equipement(
                self.equipement, sans_reference.id, user=None,
                fiche_technique=self.fiche_nouvelle)
        self._assert_rien_n_a_bouge(avant)

    def test_un_echec_de_la_derniere_etape_annule_aussi_les_premieres(self):
        """La péremption est la SIXIÈME étape : son échec défait les cinq autres."""
        avant = self._etat_avant()
        with patch.object(services, '_perimer_artefacts_du_dossier',
                          side_effect=RuntimeError('péremption indisponible')):
            with self.assertRaises(RuntimeError):
                services.basculer_equipement(
                    self.equipement, self.nouveau_produit.id, user=None,
                    fiche_technique=self.fiche_nouvelle)
        self._assert_rien_n_a_bouge(avant)

    def test_un_produit_d_une_autre_societe_n_ecrit_rien(self):
        autre = Company.objects.create(nom='AOF141 X', slug='aof141-x')
        produit_autre = Produit.objects.create(
            company=autre, nom='Interdit', prix_vente=Decimal('1.00'))
        avant = self._etat_avant()
        with self.assertRaises(ValidationError):
            services.basculer_equipement(
                self.equipement, produit_autre.id, user=None)
        self._assert_rien_n_a_bouge(avant)

    def test_un_equipement_deja_bascule_ne_rebascule_pas(self):
        services.basculer_equipement(
            self.equipement, self.nouveau_produit.id, user=None)
        self.equipement.refresh_from_db()
        compte = EquipementAO.objects.count()
        with self.assertRaises(ValidationError):
            services.basculer_equipement(
                self.equipement, self.ancien_produit.id, user=None)
        self.assertEqual(EquipementAO.objects.count(), compte)

    def test_une_bascule_sur_le_meme_produit_est_refusee(self):
        avant = self._etat_avant()
        with self.assertRaises(ValidationError):
            services.basculer_equipement(
                self.equipement, self.ancien_produit.id, user=None)
        self._assert_rien_n_a_bouge(avant)


class TestGrandeursDerivees(BaseBascule):
    def _module(self, quantite):
        return services.engager_equipement(
            self.ao, role=EquipementAO.Role.MODULE,
            produit_id=self.ancien_produit.id, quantite=quantite)

    def test_la_quantite_de_modules_se_rederive_du_calepinage(self):
        toiture = ToitureAO.objects.create(
            company=self.company, batiment=self.batiment, code_document='05H')
        VarianteCalepinage.objects.create(
            company=self.company, toiture=toiture, appel_offre=self.ao,
            nom='Retenue', est_retenue=True,
            resultat={'total_modules': 314})
        module = self._module(Decimal('0'))
        resultat = services.basculer_equipement(
            module, self.nouveau_produit.id, user=None)
        nouveau = EquipementAO.objects.get(pk=resultat['equipement'].pk)
        self.assertEqual(nouveau.quantite, Decimal('314.000'))

    def test_sans_variante_retenue_la_quantite_n_est_pas_ecrasee(self):
        """Un total dérivé de RIEN vaut zéro : il ne doit écraser aucune saisie."""
        module = self._module(Decimal('314'))
        resultat = services.basculer_equipement(
            module, self.nouveau_produit.id, user=None)
        nouveau = EquipementAO.objects.get(pk=resultat['equipement'].pk)
        self.assertEqual(nouveau.quantite, Decimal('314.000'))


class TestPeremptionDesArtefacts(BaseBascule):
    def setUp(self):
        super().setUp()
        self.dossier = services.creer_dossier_ao(self.company, self.ao)
        self.piece = PieceDossierAO.objects.create(
            company=self.company, dossier=self.dossier, code='02',
            libelle='Mémoire technique', presente=True,
            empreinte_source=empreinte_dossier(self.dossier))

    def test_les_pieces_produites_avant_la_bascule_sont_perimees(self):
        resultat = services.basculer_equipement(
            self.equipement, self.nouveau_produit.id, user=None)
        codes = [piece['code'] for piece in resultat['artefacts_perimes']]
        self.assertIn('02', codes)

    def test_la_peremption_est_inscrite_en_base_par_la_passe(self):
        services.basculer_equipement(
            self.equipement, self.nouveau_produit.id, user=None)
        self.assertTrue(ControleCoherence.objects.filter(
            dossier=self.dossier, code_regle='AO_ARTEFACT_PERIME').exists())

    def test_le_rapport_nomme_les_textes_restes_sur_l_ancienne_reference(self):
        """Le bordereau nomme encore l'ancien matériel : il est CITÉ, pas réécrit."""
        bordereau = BordereauPrix.objects.create(
            company=self.company, appel_offre=self.ao, indice_revision='A')
        LigneBordereau.objects.create(
            company=self.company, bordereau=bordereau, numero=7,
            designation='Fourniture batterie BOS-G 100 kWh', unite='U',
            quantite=Decimal('3'), prix_unitaire=Decimal('100.00'))
        resultat = services.basculer_equipement(
            self.equipement, self.nouveau_produit.id, user=None)
        emplacements = {suspect['emplacement']
                        for suspect in resultat['rapport']['suspects']}
        self.assertIn('bordereau ligne 7', emplacements)


class TestAucunCoutNeSort(BaseBascule):
    """Le produit porte un prix d'achat ; l'équipement ne le laisse PAS passer."""

    def test_le_serialiseur_ne_declare_aucun_champ_de_cout(self):
        champs = set(EquipementAOSerializer().fields)
        for interdit in ('prix_achat', 'prix_vente', 'prix_unitaire',
                         'montant', 'marge', 'benefice'):
            self.assertNotIn(interdit, champs, interdit)

    def test_aucun_montant_du_catalogue_n_apparait_dans_la_sortie(self):
        donnees = dict(EquipementAOSerializer(self.equipement).data)
        # L'horodatage du snapshot porte des microsecondes : le laisser dans
        # la comparaison rendrait ce test ALÉATOIRE (un « 1937 » de
        # microseconde n'est pas une fuite de prix). Tout le reste est
        # contrôlé, y compris les caractéristiques figées.
        donnees.pop('snapshot_le', None)
        rendu = str(donnees)
        for interdit in ('1937', '2811'):
            self.assertNotIn(interdit, rendu, interdit)

    def test_la_designation_courante_du_catalogue_est_publiee(self):
        """Le seul dérivé qui traverse la string-FK : le NOM, jamais un prix."""
        donnees = EquipementAOSerializer(self.equipement).data
        self.assertEqual(donnees['produit_designation'],
                         'Batterie BOS-G 100 kWh')
        self.assertEqual(donnees['designation'], 'Batterie BOS-G 100 kWh')
        self.assertEqual(donnees['fiche_technique_nom'], 'fiche-bos-g.pdf')


class TestApiEquipements(BaseBascule):
    def _api(self, permissions, suffixe):
        role = Role.objects.create(
            company=self.company, nom=f'AOF141 {suffixe}',
            permissions=list(permissions))
        user = User.objects.create_user(
            username=f'aof141_{suffixe}', password='x',
            company=self.company, role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_la_liste_est_filtrable_par_appel_offre_et_batiment(self):
        autre_batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='D')
        services.engager_equipement(
            self.ao, role=EquipementAO.Role.CABLE, designation='Câble 6 mm²',
            batiment=autre_batiment, quantite=Decimal('1'), unite='ml')
        api = self._api([AO_VOIR], 'lecteur')
        reponse = api.get(URL, {'appel_offre': self.ao.id,
                                'batiment': self.batiment.id})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual([ligne['id'] for ligne in reponse.data['results']],
                         [self.equipement.id])

    def test_la_bascule_exige_la_permission_d_ecriture(self):
        api = self._api([AO_VOIR], 'lecteur-seul')
        reponse = api.post(
            f'{URL}{self.equipement.id}/bascule/',
            {'produit': self.nouveau_produit.id}, format='json')
        self.assertEqual(reponse.status_code, 403)
        self.equipement.refresh_from_db()
        self.assertTrue(self.equipement.actif)

    def test_la_bascule_repond_le_nouvel_equipement_et_son_rapport(self):
        api = self._api([AO_VOIR, AO_GERER], 'gestionnaire')
        reponse = api.post(
            f'{URL}{self.equipement.id}/bascule/',
            {'produit': self.nouveau_produit.id,
             'fiche_technique': self.fiche_nouvelle.id,
             'motif': 'Gamme arrêtée'}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['equipement']['designation'],
                         'Batterie BOS-B Pro-A3')
        self.assertFalse(reponse.data['remplace']['actif'])
        self.assertIn('plan', reponse.data['rapport'])
        self.assertIn('artefacts_perimes', reponse.data)

    def test_une_bascule_sans_produit_est_un_400_motive(self):
        api = self._api([AO_VOIR, AO_GERER], 'gestionnaire-2')
        reponse = api.post(f'{URL}{self.equipement.id}/bascule/', {},
                           format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('produit', reponse.data)

    def test_un_identifiant_de_produit_non_numerique_est_un_400(self):
        """Une ``ValueError`` de l'ORM rendrait un 500 muet sur une faute client."""
        api = self._api([AO_VOIR, AO_GERER], 'gestionnaire-4')
        reponse = api.post(f'{URL}{self.equipement.id}/bascule/',
                           {'produit': 'BOS-B-PRO-A3'}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('produit', reponse.data)

    def test_la_societe_n_est_jamais_lue_du_corps_de_requete(self):
        autre = Company.objects.create(nom='AOF141 Y', slug='aof141-y')
        api = self._api([AO_VOIR, AO_GERER], 'gestionnaire-3')
        reponse = api.post(URL, {
            'appel_offre': self.ao.id, 'role': EquipementAO.Role.CABLE,
            'designation': 'Câble 6 mm²', 'quantite': '10',
            'company': autre.id,
        }, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        cree = EquipementAO.objects.get(pk=reponse.data['id'])
        self.assertEqual(cree.company_id, self.company.id)
