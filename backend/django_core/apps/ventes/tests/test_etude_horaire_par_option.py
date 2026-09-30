"""I7 (audit prod du 30/09/2026) — L'ÉTUDE HORAIRE SE CALCULE PAR OPTION.

LE DÉFAUT. ``rafraichir_etude_horaire_devis`` comptait les panneaux de TOUTES
les lignes produit, sans distinguer ``LigneDevis.variante``. Sur un devis à
deux options dont les champs PV divergent (L-2OPT : 6 panneaux « sans »,
8 panneaux « avec »), le bloc ``etude_params['etude_horaire']`` était calculé
pour 6 + 8 = 14 panneaux — une installation qu'AUCUNE option ne vend
(DEV-202609-0053 : bloc 9,94 kWc = 4,26 + 5,68). ``pricing._lire_etude_horaire``
le refusait alors pour les DEUX colonnes (garde de fraîcheur 2 %), et le devis
retombait en silence sur le modèle « factures » / « estimation ». En prod :
60 blocs horaires sur 145 dans cet état (15 devis envoyés).

LA DÉCISION : UN BLOC PAR OPTION. Un bloc unique ne peut servir qu'UNE
colonne (il porte UNE puissance) ; or la donut de couverture lit l'option AVEC
(``residential.renderer.synthese_economies``) et le lien public télécharge
l'une OU l'autre variante (L-VAR). Sur un devis divergent :

* ``etude_horaire`` décrit l'option AVEC — celle que les scalaires legacy du
  document mettent en avant (``builder._scalaires_par_option``) ;
* ``etude_horaire_sans`` décrit l'option SANS (commune + « sans »), le compte
  de panneaux que montre l'écran générateur (``r.variante !== 'avec'``).

Sans divergence : UN bloc, sur toutes les lignes, comme avant (byte-identique),
et la clé ``etude_horaire_sans`` est ABSENTE.

Lancer :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_etude_horaire_par_option"
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.services import rafraichir_etude_horaire_devis

User = get_user_model()

#: 6 × 710 W — l'option SANS (panneaux communs + « sans »).
KWC_SANS = 4.26
#: 8 × 710 W — l'option AVEC.
KWC_AVEC = 5.68
#: 14 × 710 W — la SOMME des deux paniers : la puissance de personne.
KWC_SOMME = 9.94

PANNEAU = 'Panneau Canadien Solar 710W'
#: Le devis prod DEV-202609-0053, réduit à l'essentiel : deux champs PV.
LIGNES_DIVERGENTES = (
    (PANNEAU, '6', '1166.67', 'sans'),
    (PANNEAU, '8', '1166.67', 'avec'),
    ('Onduleur réseau Huawei 5kW Monophasé', '1', '12000.00', ''),
    ('Onduleur hybride Deye 5kW Monophasé', '1', '17000.00', ''),
    ('Batterie Dyness 5 kWh', '1', '16000.00', ''),
    ('Installation', '1', '4000.00', ''),
)
#: Le même devis, un seul champ PV commun de 14 panneaux (tout l'existant).
LIGNES_COMMUNES = (
    (PANNEAU, '14', '1166.67', ''),
    ('Onduleur réseau Huawei 5kW Monophasé', '1', '12000.00', ''),
    ('Onduleur hybride Deye 5kW Monophasé', '1', '17000.00', ''),
    ('Batterie Dyness 5 kWh', '1', '16000.00', ''),
    ('Installation', '1', '4000.00', ''),
)
DEUX_OPTIONS = {'scenario': 'Les deux (Sans + Avec)'}


class _Base(TestCase):
    """Casablanca, facture d'hiver réelle : la chaîne PVGIS passe par la table
    de référence de la ville (aucun réseau), comme ``test_cj2b_*``."""

    def _devis(self, slug, lignes=LIGNES_DIVERGENTES, etude_params=None):
        from authentication.models import Company
        company = Company.objects.get_or_create(
            slug=slug, defaults={'nom': slug})[0]
        User.objects.get_or_create(
            username=f'{slug}-user',
            defaults={'password': 'x', 'company': company})
        client_obj = Client.objects.create(company=company, nom=f'C {slug}')
        lead = Lead.objects.create(
            company=company, nom='Lead', prenom=slug,
            telephone='+212600000000', ville='Casablanca',
            facture_hiver=1800, ete_differente=False)
        devis = Devis.objects.create(
            company=company, reference=f'DEV-{slug.upper()}-01',
            client=client_obj, lead=lead, statut='brouillon',
            taux_tva=Decimal('20'), mode_installation='residentiel',
            etude_params=dict(DEUX_OPTIONS, **(etude_params or {})))
        for i, (nom, qte, pu, variante) in enumerate(lignes):
            produit = Produit.objects.create(
                company=company, nom=nom, sku=f'{slug}-{i}', prix_vente=pu,
                quantite_stock=50)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                remise=Decimal('0'), variante=variante)
        return devis

    def _rafraichir(self, devis, **kwargs):
        rafraichir_etude_horaire_devis(devis, **kwargs)
        return Devis.objects.get(pk=devis.pk)


class BlocParOptionTests(_Base):
    """Le RANGEMENT : chaque bloc décrit une puissance qu'une option vend."""

    def test_le_bloc_principal_decrit_l_option_avec_jamais_la_somme(self):
        """ROUGE avant I7 : le bloc portait 9,94 kWc (6 + 8 panneaux)."""
        devis = self._rafraichir(self._devis('i7-principal'), force=True)
        bloc = devis.etude_params.get('etude_horaire')
        self.assertIsInstance(bloc, dict, 'étude horaire non calculée')
        self.assertNotEqual(bloc['kwc'], KWC_SOMME)
        self.assertEqual(bloc['kwc'], KWC_AVEC)

    def test_l_option_sans_porte_son_propre_bloc(self):
        devis = self._rafraichir(self._devis('i7-sans'), force=True)
        bloc_sans = devis.etude_params.get('etude_horaire_sans')
        self.assertIsInstance(bloc_sans, dict)
        self.assertEqual(bloc_sans['kwc'], KWC_SANS)
        # Même estampille d'entrées que le bloc principal : même profil client.
        self.assertTrue(bloc_sans.get('_empreinte_entrees'))
        self.assertEqual(
            bloc_sans['_empreinte_entrees'],
            devis.etude_params['etude_horaire']['_empreinte_entrees'])

    def test_une_variante_mal_casse_est_lue_comme_le_builder_la_lit(self):
        """``variante`` n'a aucune contrainte en base : une valeur « Sans » /
        « AVEC » (import, ``.update()``) est normalisée par le builder
        (``_variante_de_ligne``). Le rafraîchisseur lit la MÊME chose — sinon
        ces panneaux sortiraient des deux paniers et le bloc décrirait
        encore une puissance que le document ne chiffre pas."""
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis('i7-casse')
        devis.lignes.filter(variante='sans').update(variante=' Sans ')
        devis.lignes.filter(variante='avec').update(variante='AVEC')
        devis = self._rafraichir(Devis.objects.get(pk=devis.pk), force=True)
        data = build_quote_data(devis)
        self.assertEqual(
            (devis.etude_params['etude_horaire']['kwc'],
             devis.etude_params['etude_horaire_sans']['kwc']),
            (data['puissance_kwc_avec'], data['puissance_kwc_sans']))
        self.assertEqual(data['savings_model_sans'], 'horaire')

    def test_un_devis_non_divergent_garde_un_seul_bloc_sur_toutes_ses_lignes(
            self):
        """Tout l'existant : 14 panneaux communs ⇒ 9,94 kWc, et aucune clé
        ``etude_horaire_sans`` (byte-identique à avant)."""
        devis = self._rafraichir(
            self._devis('i7-commun', LIGNES_COMMUNES), force=True)
        self.assertEqual(devis.etude_params['etude_horaire']['kwc'], KWC_SOMME)
        self.assertNotIn('etude_horaire_sans', devis.etude_params)

    def test_une_divergence_disparue_retire_le_bloc_sans(self):
        """Règle Z2 appliquée à la fraîcheur : un bloc qui décrit une option
        qui n'existe plus est RETIRÉ, jamais laissé en place."""
        devis = self._rafraichir(self._devis('i7-retrait'), force=True)
        self.assertIn('etude_horaire_sans', devis.etude_params)
        devis.lignes.filter(variante='avec').delete()
        devis.lignes.filter(variante='sans').update(variante='')
        devis = self._rafraichir(devis)
        self.assertNotIn('etude_horaire_sans', devis.etude_params)
        self.assertEqual(devis.etude_params['etude_horaire']['kwc'], KWC_SANS)

    def test_deux_blocs_a_jour_ne_relancent_aucun_calcul(self):
        """La garde anti-recalcul (CJ2b) couvre les DEUX blocs : rien n'a
        bougé ⇒ aucun passage du moteur horaire dans le handler HTTP.

        (Un ``side_effect=AssertionError`` serait AVALÉ par le ``try/except``
        du rafraîchisseur — la preuve passe donc par ``assert_not_called``.)
        """
        from apps.ventes.domain.etudes import _blocs_horaires_deja_a_jour
        devis = self._rafraichir(self._devis('i7-stable'), force=True)
        self.assertTrue(_blocs_horaires_deja_a_jour(devis, KWC_AVEC, KWC_SANS))
        with mock.patch(
                'apps.ventes.etude_horaire.etude_horaire_pour_devis') as moteur:
            rafraichir_etude_horaire_devis(devis)
        moteur.assert_not_called()

    def test_un_bloc_sans_orphelin_est_retire_meme_principal_frais(self):
        """Le devis redevient mono-champ SANS changer de puissance AVEC
        (8 panneaux communs = 5,68 kWc) : le bloc principal est frais, mais le
        bloc « sans » décrit une option disparue — il doit partir."""
        devis = self._rafraichir(self._devis('i7-orphelin'), force=True)
        devis.lignes.filter(variante='sans').delete()
        devis.lignes.filter(variante='avec').update(variante='')
        devis = self._rafraichir(Devis.objects.get(pk=devis.pk))
        self.assertNotIn('etude_horaire_sans', devis.etude_params)
        self.assertEqual(devis.etude_params['etude_horaire']['kwc'], KWC_AVEC)

    def test_un_bloc_sans_manquant_est_recalcule(self):
        """Un devis rangé AVANT I7 n'a pas de bloc « sans » : il n'est pas à
        jour, même si son bloc principal décrit bien l'option AVEC."""
        devis = self._rafraichir(self._devis('i7-ancien'), force=True)
        etude = dict(devis.etude_params)
        etude.pop('etude_horaire_sans')
        Devis.objects.filter(pk=devis.pk).update(etude_params=etude)
        devis = self._rafraichir(Devis.objects.get(pk=devis.pk))
        self.assertEqual(devis.etude_params['etude_horaire_sans']['kwc'],
                         KWC_SANS)

    def test_le_rafraichissement_ne_touche_ni_statut_ni_lignes_ni_totaux(self):
        """Règle #4 : ``update_fields=['etude_params']`` et rien d'autre."""
        from apps.ventes.utils.options import option_totaux

        def _etat(d):
            return (d.statut, d.remise_globale, option_totaux(d),
                    list(d.lignes.order_by('pk').values_list(
                        'pk', 'quantite', 'prix_unitaire', 'variante')))

        devis = self._devis('i7-regle4')
        avant = _etat(devis)
        devis = self._rafraichir(devis, force=True)
        self.assertEqual(_etat(devis), avant)


class FraicheurSansPuissanceTests(SimpleTestCase):
    """Revue I7 (F2) — une puissance ILLISIBLE (panneaux sans wattage lu) ne
    doit pas relancer le moteur horaire à CHAQUE sauvegarde de ligne."""

    def _frais(self, etude_params, kwc, kwc_sans):
        from apps.ventes.domain import etudes
        devis = mock.Mock(etude_params=etude_params)
        # Seul le bloc d'une puissance CONNUE peut être comparé ; on isole ici
        # la décision « puissance absente » (aucune base, aucun moteur).
        with mock.patch.object(etudes, '_bloc_horaire_deja_a_jour',
                               side_effect=lambda d, k, cle='etude_horaire':
                               bool(k)):
            return etudes._blocs_horaires_deja_a_jour(devis, kwc, kwc_sans)

    def test_option_avec_illisible_ne_boucle_pas(self):
        """kWc AVEC illisible, kWc SANS lu et son bloc frais : rien à faire."""
        self.assertTrue(self._frais(
            {'etude_horaire_sans': {'kwc': KWC_SANS}}, None, KWC_SANS))

    def test_aucune_puissance_et_aucun_bloc_rien_a_faire(self):
        self.assertTrue(self._frais({}, None, None))

    def test_un_bloc_sans_puissance_qui_le_justifie_est_perime(self):
        """Règle Z2 : un bloc qui ne décrit plus aucune puissance du devis
        doit être retiré — donc « pas à jour »."""
        self.assertFalse(self._frais(
            {'etude_horaire': {'kwc': KWC_AVEC}}, None, None))


class LesDeuxColonnesAlHeureTests(_Base):
    """La LECTURE : le document chiffre chaque option au moteur horaire."""

    def test_les_deux_colonnes_et_le_document_sont_horaires(self):
        """ROUGE avant I7 : le bloc 9,94 kWc était refusé pour les deux
        colonnes ⇒ modèle « factures » partout."""
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._rafraichir(self._devis('i7-document'), force=True)
        data = build_quote_data(devis)
        self.assertTrue(data['panneaux_divergents'])
        self.assertEqual(data['puissance_kwc_sans'], KWC_SANS)
        self.assertEqual(data['puissance_kwc_avec'], KWC_AVEC)
        self.assertEqual(data['savings_model'], 'horaire')
        self.assertEqual(data['savings_model_sans'], 'horaire')
        self.assertEqual(data['savings_model_avec'], 'horaire')
        # COUV-HOR (#738) — la donut lit la couverture du moteur horaire, qui
        # n'est servie QUE pour une colonne réellement chiffrée à l'heure.
        self.assertIsNotNone(data.get('couverture_sans'))
        self.assertIsNotNone(data.get('couverture_avec'))

    def test_la_variante_sans_telechargee_est_horaire(self):
        """L-VAR : le PDF « Sans batterie » du lien public titre 4,26 kWc — il
        lit le bloc de SA branche."""
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._rafraichir(self._devis('i7-lvar'), force=True)
        data = build_quote_data(devis, {'variante_option': 'sans'})
        self.assertEqual(data['puissance_kwc'], KWC_SANS)
        self.assertEqual(data['savings_model'], 'horaire')


class SelectionDuBlocParPuissanceTests(TestCase):
    """Le builder et ``offres_tailles`` choisissent le bloc de la puissance
    demandée — blocs FACTICES, aucun moteur (déterministe)."""

    def setUp(self):
        from apps.ventes.tests.test_cj2b_graphe_mensuel import bloc_horaire
        self.bloc_avec = bloc_horaire(KWC_AVEC)
        self.bloc_sans = bloc_horaire(KWC_SANS)
        self.bloc_sans['annuel']['taux_autoconso_sans'] = 0.77

    def test_le_builder_rend_le_bloc_de_chaque_puissance(self):
        from apps.ventes.quote_engine.builder import bloc_horaire_pour_kwc
        etude = {'etude_horaire': self.bloc_avec,
                 'etude_horaire_sans': self.bloc_sans}
        self.assertIs(bloc_horaire_pour_kwc(etude, KWC_AVEC), self.bloc_avec)
        self.assertIs(bloc_horaire_pour_kwc(etude, KWC_SANS), self.bloc_sans)
        # Aucune puissance ne correspond : le bloc principal, que la garde de
        # fraîcheur de ``pricing`` refusera — comportement d'avant I7.
        self.assertIs(bloc_horaire_pour_kwc(etude, KWC_SOMME), self.bloc_avec)
        self.assertIs(bloc_horaire_pour_kwc({}, KWC_SANS), None)

    def test_offres_tailles_lit_les_taux_du_bloc_de_la_carte(self):
        from apps.ventes.offres_tailles import _annuel_frais
        devis = mock.Mock(etude_params={
            'etude_horaire': self.bloc_avec,
            'etude_horaire_sans': self.bloc_sans})
        self.assertEqual(
            _annuel_frais(devis, KWC_SANS)['taux_autoconso_sans'], 0.77)
        self.assertEqual(
            _annuel_frais(devis, KWC_AVEC)['taux_autoconso_sans'], 0.41)


class FrontieresTests(_Base):
    """Le second bloc suit les MÊMES frontières que le premier."""

    def test_le_schema_le_declare_derivee_du_moteur_horaire(self):
        from apps.ventes.domain.etude_schema import (
            DERIVEE, MOTEUR_HORAIRE, SCHEMA)
        regle = SCHEMA['etude_horaire_sans']
        self.assertEqual(regle['proprietaire'], MOTEUR_HORAIRE)
        self.assertEqual(regle['nature'], DERIVEE)

    def test_une_copie_de_devis_ne_le_reprend_pas(self):
        from apps.ventes.domain.etudes import etude_params_pour_copie
        copie = etude_params_pour_copie({
            'scenario': DEUX_OPTIONS['scenario'],
            'etude_horaire': {'kwc': KWC_AVEC},
            'etude_horaire_sans': {'kwc': KWC_SANS}})
        self.assertEqual(copie, DEUX_OPTIONS)

    def test_la_page_publique_ne_publie_pas_le_bloc_brut(self):
        devis = self._rafraichir(self._devis('i7-public'), force=True)
        Devis.objects.filter(pk=devis.pk).update(statut='envoye')
        link = ShareLink.objects.create(company=devis.company, devis=devis)
        resp = APIClient().get(
            f'/api/django/public/proposal/{link.token}/data/')
        self.assertEqual(resp.status_code, 200)
        quote = resp.json().get('quote') or {}
        # Sans ce contrôle, un bloc « etude » absent rendrait le test vide.
        self.assertIsInstance(quote.get('etude'), dict)
        etude = quote['etude']
        self.assertNotIn('etude_horaire', etude)
        self.assertNotIn('etude_horaire_sans', etude)

    def test_les_profils_comparatifs_comparent_a_la_puissance_du_bloc(self):
        """Le profil RÉEL réutilise le bloc principal : les autres profils
        doivent être simulés à LA MÊME puissance."""
        from apps.ventes.profils_comparatifs import _kwc_du_devis
        devis = self._devis('i7-profils')
        self.assertEqual(_kwc_du_devis(devis), KWC_AVEC)
