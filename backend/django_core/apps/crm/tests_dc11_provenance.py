"""DC11 — provenance des valeurs énergie/toiture reprises du lead.

Les valeurs énergie/toiture recopiées dans ``Devis.etude_params`` portent une
estampille ``{source_lead_id, captured_at, valeurs}`` ; un changement du lead
APRÈS capture est détecté (bannière « valeurs du lead modifiées depuis »).
Multi-tenant : la détection est scopée société.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Lead
from apps.crm import selectors


class TestLeadProvenance(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='dc11-co', defaults={'nom': 'DC11 Co'})[0]
        self.other = Company.objects.create(slug='dc11-other', nom='Autre')
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect',
            facture_hiver=Decimal('1200'), facture_ete=Decimal('800'),
            ete_differente=True, type_toiture='tuiles', orientation='sud',
            surface_toiture_m2=Decimal('60'))

    def test_stamp_carries_source_lead_and_valeurs(self):
        stamp = selectors.lead_provenance_stamp(self.lead)
        self.assertEqual(stamp['source_lead_id'], self.lead.pk)
        self.assertIn('captured_at', stamp)
        self.assertEqual(stamp['valeurs']['facture_hiver'], '1200')
        self.assertEqual(stamp['valeurs']['facture_ete'], '800')
        self.assertEqual(stamp['valeurs']['ete_differente'], True)
        self.assertEqual(stamp['valeurs']['type_toiture'], 'tuiles')

    def test_stamp_none_without_lead(self):
        self.assertIsNone(selectors.lead_provenance_stamp(None))

    def test_no_change_returns_empty(self):
        stamp = selectors.lead_provenance_stamp(self.lead)
        self.assertEqual(
            selectors.lead_values_changed_since(stamp, company=self.company),
            [])

    def test_detects_changed_fields(self):
        stamp = selectors.lead_provenance_stamp(self.lead)
        self.lead.facture_hiver = Decimal('1500')
        self.lead.orientation = 'est'
        self.lead.save(update_fields=['facture_hiver', 'orientation'])
        changed = selectors.lead_values_changed_since(
            stamp, company=self.company)
        self.assertIn('facture_hiver', changed)
        self.assertIn('orientation', changed)
        self.assertNotIn('facture_ete', changed)

    def test_empty_stamp_no_false_alert(self):
        self.assertEqual(selectors.lead_values_changed_since(None), [])
        self.assertEqual(selectors.lead_values_changed_since({}), [])

    def test_scoped_to_company(self):
        # Un stamp d'un lead d'une autre société ne lève pas de fausse alerte
        # quand on filtre sur la société courante (lead introuvable → []).
        stamp = selectors.lead_provenance_stamp(self.lead)
        self.lead.facture_hiver = Decimal('9999')
        self.lead.save(update_fields=['facture_hiver'])
        self.assertEqual(
            selectors.lead_values_changed_since(stamp, company=self.other),
            [])


class LeCheminVivantDeLaProvenance(TestCase):
    """QJR106 (décision fondateur D6 du 29/08/2026) — LE CHEMIN VIVANT.

    Les six tests ci-dessus prouvaient les trois fonctions du sélecteur EN
    VASE CLOS : un grep du dépôt ne trouvait qu'elles et leurs définitions, et
    ``etude_params`` n'a jamais porté de clé de provenance. Ces tests-ci
    prouvent le BRANCHEMENT : ``pipeline`` estampille, le sérialiseur rend le
    verdict, et une dérive en cours n'est pas éteinte par un enregistrement.

    Lecture cross-app par ``selectors``/``services`` uniquement (jamais
    ``apps.ventes.models`` importé par ``apps.crm`` en production) : ces
    imports vivent DANS les tests, où ils décrivent le contrat inter-apps.
    """

    def setUp(self):
        from apps.crm.services import resolve_client_for_lead
        from apps.ventes.models import Devis

        self.company = Company.objects.get_or_create(
            slug='dc11-vivant', defaults={'nom': 'DC11 Vivant'})[0]
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect vivant',
            facture_hiver=Decimal('1200'), facture_ete=Decimal('800'),
            ete_differente=True, type_toiture='tuiles', orientation='sud',
            surface_toiture_m2=Decimal('60'))
        self.client_obj = resolve_client_for_lead(self.lead)
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-DC11-1',
            client=self.client_obj, lead=self.lead, statut='brouillon')

    def _intention(self, **extra):
        from apps.ventes.domain import pipeline

        champs = dict(origine=pipeline.ORIGINE_ECRAN, company=self.company)
        champs.update(extra)
        return pipeline.IntentionDevis(**champs)

    # ── L'ESTAMPILLE est POSÉE ───────────────────────────────────────────────

    def test_le_pipeline_estampille_un_devis_a_lead(self):
        from apps.ventes.domain import pipeline

        pipeline.estampiller_provenance(self.devis, self._intention())
        self.devis.refresh_from_db()
        stamp = self.devis.etude_params['provenance']
        self.assertEqual(stamp['source_lead_id'], self.lead.pk)
        self.assertIn('captured_at', stamp)
        # LA FORME EST str, LA VÉRIFICATION EST PAR VALEUR — et c'est le
        # contrat du sélecteur, pas une commodité de test. `crm.selectors.
        # _lead_provenance_valeurs` rend `str(v)` pour un Decimal (JSON-safe) :
        # la CHAÎNE obtenue dépend donc de l'exposant du Decimal qu'il a sous la
        # main, pas du champ. Un lead ENCORE EN MÉMOIRE porte le `Decimal
        # ('1200')` qu'on lui a passé → « 1200 » ; le MÊME lead relu de la base
        # porte `Decimal('1200.00')` (decimal_places appliqués) → « 1200.00 ».
        # Les deux sont la même somme. C'est précisément pourquoi
        # `lead_values_changed_since` compare par valeur (son `_norm`) et non
        # par texte — sans quoi chaque champ décimal INCHANGÉ lèverait une
        # fausse alerte. On assertit donc ici la MÊME chose que lui : le type
        # (JSON-safe) et la VALEUR.
        facture = stamp['valeurs']['facture_hiver']
        self.assertIsInstance(facture, str)
        self.assertEqual(Decimal(facture), self.lead.facture_hiver)

    def test_le_lead_de_l_intention_prime_sur_celui_du_devis(self):
        """À la CRÉATION le devis n'est pas encore rattaché : c'est
        l'intention qui porte le lead."""
        from apps.ventes.domain import pipeline
        from apps.ventes.models import Devis

        orphelin = Devis.objects.create(
            company=self.company, reference='DEV-DC11-2',
            client=self.client_obj, statut='brouillon')
        pipeline.estampiller_provenance(
            orphelin, self._intention(lead=self.lead))
        orphelin.refresh_from_db()
        self.assertEqual(
            orphelin.etude_params['provenance']['source_lead_id'],
            self.lead.pk)

    def test_un_devis_sans_lead_n_est_jamais_estampille(self):
        from apps.ventes.domain import pipeline
        from apps.ventes.models import Devis

        sans_lead = Devis.objects.create(
            company=self.company, reference='DEV-DC11-3',
            client=self.client_obj, statut='brouillon')
        self.assertIsNone(
            pipeline.estampiller_provenance(sans_lead, self._intention()))
        sans_lead.refresh_from_db()
        self.assertNotIn('provenance', sans_lead.etude_params or {})

    def test_l_estampille_ne_remplace_pas_le_reste_de_l_etude(self):
        """Écrivain unique (QJR62) : la fusion, jamais un remplacement."""
        from apps.ventes.domain import pipeline

        self.devis.etude_params = {'conso_annuelle': 9000}
        self.devis.save(update_fields=['etude_params'])
        pipeline.estampiller_provenance(self.devis, self._intention())
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.etude_params['conso_annuelle'], 9000)
        self.assertIn('provenance', self.devis.etude_params)

    def test_une_derive_en_cours_n_est_pas_eteinte_par_un_enregistrement(self):
        """LE POINT DE LA FONCTIONNALITÉ. Si un simple ré-enregistrement
        réestampillait, la bannière s'éteindrait sans que personne n'ait
        regardé le lead — le devis resterait chiffré sur la facture d'AVANT.
        """
        from apps.ventes.domain import pipeline

        pipeline.estampiller_provenance(self.devis, self._intention())
        self.lead.facture_hiver = Decimal('1500')
        self.lead.save(update_fields=['facture_hiver'])

        self.assertIsNone(
            pipeline.estampiller_provenance(self.devis, self._intention()))
        self.devis.refresh_from_db()
        stamp = self.devis.etude_params['provenance']
        # Comparaison PAR VALEUR (voir la note de forme dans
        # `test_le_pipeline_estampille_un_devis_a_lead`) : l'estampille doit
        # porter la facture d'AVANT — 1200, jamais les 1500 qui viennent
        # d'être enregistrés sur le lead.
        self.assertEqual(Decimal(stamp['valeurs']['facture_hiver']),
                         Decimal('1200'))
        self.assertIn(
            'facture_hiver',
            selectors.lead_values_changed_since(stamp, company=self.company))

    def test_un_changement_de_lead_source_reestampille(self):
        from apps.ventes.domain import pipeline

        autre = Lead.objects.create(company=self.company, nom='Autre prospect',
                                    facture_hiver=Decimal('300'))
        pipeline.estampiller_provenance(self.devis, self._intention())
        pipeline.estampiller_provenance(self.devis,
                                        self._intention(lead=autre))
        self.devis.refresh_from_db()
        self.assertEqual(
            self.devis.etude_params['provenance']['source_lead_id'], autre.pk)

    # ── LE PIPELINE l'appelle vraiment ───────────────────────────────────────

    def test_le_mode_ecrire_du_pipeline_estampille(self):
        """Le geste d'enregistrement de l'écran (``atomic`` /
        ``replace-lines``) passe par ``appliquer(mode='ecrire')`` : c'est LÀ
        que la création et la mise à jour de l'écran sont estampillées."""
        from apps.ventes.domain import pipeline

        vrai = pipeline.ecrire_lignes
        pipeline.ecrire_lignes = lambda *a, **k: []
        try:
            pipeline.appliquer(self.devis, self._intention(
                mode=pipeline.MODE_ECRIRE, composition=[]))
        finally:
            pipeline.ecrire_lignes = vrai
        self.devis.refresh_from_db()
        self.assertEqual(
            self.devis.etude_params['provenance']['source_lead_id'],
            self.lead.pk)

    def test_l_etape_ecrire_etude_params_estampille(self):
        """Étape 6 du pipeline complet (créations auto / tunnel / 3D)."""
        from apps.ventes.domain import pipeline

        pipeline.ecrire_etude_params(
            self.devis, self._intention(lead=self.lead,
                                        origine=pipeline.ORIGINE_AUTO), [])
        self.devis.refresh_from_db()
        self.assertEqual(
            self.devis.etude_params['provenance']['source_lead_id'],
            self.lead.pk)

    # ── LE CANAL DE LA BANNIÈRE ──────────────────────────────────────────────

    def test_le_serializer_rend_les_champs_du_lead_qui_ont_bouge(self):
        from apps.ventes.domain import pipeline
        from apps.ventes.serializers import DevisSerializer

        pipeline.estampiller_provenance(self.devis, self._intention())
        self.lead.facture_hiver = Decimal('1500')
        self.lead.orientation = 'est'
        self.lead.save(update_fields=['facture_hiver', 'orientation'])
        self.devis.refresh_from_db()

        champs = DevisSerializer(self.devis).data['lead_valeurs_modifiees']
        self.assertIn('facture_hiver', champs)
        self.assertIn('orientation', champs)
        self.assertNotIn('facture_ete', champs)

    def test_le_serializer_ne_crie_pas_quand_rien_n_a_bouge(self):
        from apps.ventes.domain import pipeline
        from apps.ventes.serializers import DevisSerializer

        pipeline.estampiller_provenance(self.devis, self._intention())
        self.devis.refresh_from_db()
        self.assertEqual(
            DevisSerializer(self.devis).data['lead_valeurs_modifiees'], [])

    def test_sans_estampille_le_serializer_ne_dit_rien(self):
        from apps.ventes.serializers import DevisSerializer

        self.assertIsNone(
            DevisSerializer(self.devis).data['lead_valeurs_modifiees'])

    def test_la_liste_ne_paie_pas_la_detection(self):
        """NTCPQ21 — la détection coûte une lecture du lead PAR devis : elle
        n'est calculée que sur le DÉTAIL, jamais sur une page de liste."""
        from apps.ventes.domain import pipeline
        from apps.ventes.models import Devis
        from apps.ventes.serializers import DevisSerializer

        pipeline.estampiller_provenance(self.devis, self._intention())
        self.lead.facture_hiver = Decimal('1500')
        self.lead.save(update_fields=['facture_hiver'])
        page = DevisSerializer(
            Devis.objects.filter(pk=self.devis.pk), many=True).data
        self.assertIsNone(page[0]['lead_valeurs_modifiees'])
