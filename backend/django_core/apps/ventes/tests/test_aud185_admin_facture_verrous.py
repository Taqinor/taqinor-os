"""AUD185 — l'administration Django n'est plus une porte dérobée sur l'argent.

Constat F3 de l'audit L3 : `FactureAdmin.readonly_fields` se limitait à
`('reference', 'date_emission', 'fichier_pdf')` (apps/ventes/admin.py:32-38
avant ce correctif). Or :

* `Facture.save()` (apps/facturation/models.py:355-386) ne porte AUCUN garde —
  ni verrou de période, ni gel des champs financiers ;
* le verrou de période (YLEDG3, `_guard_periode_verrouillee`,
  apps/ventes/views/facture.py:188-203) et le gel de
  `FACTURE_CHAMPS_FINANCIERS` (XFAC24, :45-53) vivent EXCLUSIVEMENT dans le
  ViewSet, que le `ModelAdmin` n'appelle jamais (il n'avait aucun `save_model`
  ni aucun `form`).

Un superutilisateur pouvait donc réécrire `remise_globale`, `taux_tva`,
`escompte_*` ou `type_facture` d'une facture ÉMISE d'un exercice CLÔTURÉ, et
supprimer purement et simplement une facture émise (et ses encaissements en
CASCADE). S'y ajoutait F10 : aucun `admin.py` ne scopait `get_queryset`, donc
un compte `is_staff` d'une société listait les factures des autres.

Cadrage honnête (adjudication) : l'acteur est un SUPERUSER — défense en
profondeur et intégrité de la piste d'audit, pas une brèche tenant prouvée. La
branche « statut → PAYEE » est HORS périmètre (l'API l'autorise également),
d'où l'absence de gel sur `statut`.
"""
import json
from datetime import date, datetime
from decimal import Decimal

from django.contrib import admin as django_admin
from django.core.exceptions import PermissionDenied
from django.test import Client as HttpClient
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.compta.models import PeriodeComptable
from apps.ventes.admin import SUPPRESSION_FACTURE_POSTEE_INTERDITE
from apps.ventes.models import Facture
from testkit.factories import ClientFactory, CompanyFactory, UserFactory


def payload_depuis_form(model_admin, request, obj):
    """Reconstruit le POST du formulaire d'admin depuis ses valeurs actuelles.

    Construit à partir de `model_admin.get_form(...)` plutôt qu'à la main :
    aucun champ obligatoire ne peut être oublié, et les champs devenus
    `readonly` disparaissent AUTOMATIQUEMENT du POST — exactement comme dans le
    navigateur.
    """
    form_class = model_admin.get_form(request, obj, change=obj is not None)
    form = form_class(instance=obj)
    data = {}
    for nom, champ in form.fields.items():
        brut = form.initial.get(nom, champ.initial)
        if brut is None or brut == '':
            data[nom] = ''
        elif isinstance(brut, bool):
            if brut:
                data[nom] = 'on'
            # un booléen faux s'OMET (case décochée), comme en HTML
        elif isinstance(brut, (dict, list, tuple)):
            data[nom] = json.dumps(brut)
        elif isinstance(brut, datetime):
            data[nom] = brut.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(brut, date):
            data[nom] = brut.strftime('%Y-%m-%d')
        elif hasattr(brut, 'pk'):
            data[nom] = str(brut.pk)
        else:
            data[nom] = str(brut)
    return data


def inline_vide(prefix):
    """Management-form d'un inline sans aucune ligne."""
    return {
        f'{prefix}-TOTAL_FORMS': '0',
        f'{prefix}-INITIAL_FORMS': '0',
        f'{prefix}-MIN_NUM_FORMS': '0',
        f'{prefix}-MAX_NUM_FORMS': '1000',
    }


class FactureAdminVerrousTests(TestCase):
    def setUp(self):
        super().setUp()
        self.societe_a = CompanyFactory(nom='AUD185 A', slug='aud185-a')
        self.societe_b = CompanyFactory(nom='AUD185 B', slug='aud185-b')
        self.client_a = ClientFactory(company=self.societe_a, nom='ClientA185')
        self.client_b = ClientFactory(company=self.societe_b, nom='ClientB185')

        self.superuser = UserFactory(
            company=self.societe_a, username='aud185-root-ventes',
            is_staff=True, is_superuser=True)

        # ``Facture.created_by`` est ``null=True`` MAIS ``blank=False`` : le
        # formulaire d'admin le rend donc OBLIGATOIRE. Une facture posée sans
        # lui faisait échouer la validation du POST reconstruit ci-dessous
        # (« Ce champ est obligatoire »), et l'admin ré-affichait le
        # formulaire en 200 au lieu d'enregistrer en 302 — un rouge qui ne
        # disait rien des verrous mesurés ici. Le fixture porte donc son
        # auteur, comme toute facture réellement créée par l'ERP.
        self.emise = Facture.objects.create(
            company=self.societe_a, reference='FAC-AUD185-EMISE',
            client=self.client_a, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0.00'),
            created_by=self.superuser)
        self.brouillon = Facture.objects.create(
            company=self.societe_a, reference='FAC-AUD185-BROUILLON',
            client=self.client_a, statut=Facture.Statut.BROUILLON,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0.00'),
            created_by=self.superuser)
        self.facture_b = Facture.objects.create(
            company=self.societe_b, reference='FAC-AUD185-AUTRE-SOCIETE',
            client=self.client_b, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))

        self.http = HttpClient()
        self.http.force_login(self.superuser)
        self.model_admin = django_admin.site._registry[Facture]

    def _request(self):
        request = RequestFactory().get('/')
        request.user = self.superuser
        return request

    def _post_change(self, facture, **surcharges):
        data = payload_depuis_form(self.model_admin, self._request(), facture)
        data.update(inline_vide('lignes'))
        data.update(surcharges)
        url = reverse('admin:facturation_facture_change', args=[facture.pk])
        return self.http.post(url, data)

    def _assert_enregistre(self, reponse):
        """302 = enregistré. Sur un 200, NOMME les erreurs du formulaire.

        Un `AssertionError: 200 != 302` nu ne dit pas QUEL champ a refusé le
        POST ; la diagnose coûtait alors un cycle de CI complet.
        """
        if reponse.status_code != 302:
            try:
                erreurs = dict(reponse.context['adminform'].form.errors)
            except Exception:  # noqa: BLE001 — le diagnostic ne casse jamais
                erreurs = '<erreurs de formulaire illisibles>'
            self.fail(
                "le formulaire d'admin n'a pas enregistré (HTTP %s au lieu de "
                '302) — erreurs : %r' % (reponse.status_code, erreurs))

    # ── (1) période comptable verrouillée ──────────────────────────────────
    def test_periode_verrouillee_refuse_la_modification(self):
        """Rouge avant AUD185 : le formulaire d'admin n'appelait aucun service,
        donc la facture d'un exercice clôturé s'enregistrait sans un mot."""
        PeriodeComptable.objects.create(
            company=self.societe_a, date_debut=date(2000, 1, 1),
            date_fin=date(2100, 1, 1), verrouillee=True,
            type_periode=PeriodeComptable.Type.EXERCICE,
            libelle='AUD185 exercice clôturé')

        # `date_echeance` est un champ NON financier (donc encore éditable) :
        # si le formulaire s'enregistrait, il changerait. C'est le témoin.
        reponse = self._post_change(self.emise, date_echeance='2099-12-31')

        # 200 = formulaire ré-affiché avec son erreur ; 302 aurait voulu dire
        # « enregistré ».
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'Période comptable clôturée')
        self.emise.refresh_from_db()
        self.assertNotEqual(str(self.emise.date_echeance), '2099-12-31')

    # ── (F3) gel des champs financiers d'une facture émise ─────────────────
    def test_champs_financiers_geles_sur_facture_emise(self):
        readonly = self.model_admin.get_readonly_fields(
            self._request(), self.emise)
        for champ in ('remise_globale', 'taux_tva', 'escompte_pct',
                      'escompte_jours', 'type_facture', 'client',
                      'montant_ht', 'montant_tva', 'montant_ttc',
                      'pourcentage'):
            self.assertIn(champ, readonly, f'{champ} encore modifiable')

        # Et le POST correspondant ne les change pas : ils ont disparu du
        # formulaire, donc la valeur envoyée est ignorée.
        reponse = self._post_change(
            self.emise, remise_globale='15.00', taux_tva='7.00')
        self._assert_enregistre(reponse)
        self.emise.refresh_from_db()
        self.assertEqual(self.emise.remise_globale, Decimal('0.00'))
        self.assertEqual(self.emise.taux_tva, Decimal('20.00'))

    def test_garde_cible_la_facture_brouillon_reste_modifiable(self):
        """Le gel est CIBLÉ : une facture encore au brouillon se corrige."""
        readonly = self.model_admin.get_readonly_fields(
            self._request(), self.brouillon)
        self.assertNotIn('remise_globale', readonly)

        reponse = self._post_change(self.brouillon, remise_globale='5.00')
        self._assert_enregistre(reponse)
        self.brouillon.refresh_from_db()
        self.assertEqual(self.brouillon.remise_globale, Decimal('5.00'))

    # ── (4) suppression d'un document posté ────────────────────────────────
    def test_suppression_facture_emise_refusee(self):
        url = reverse('admin:facturation_facture_delete', args=[self.emise.pk])
        self.assertEqual(self.http.get(url).status_code, 403)
        self.assertEqual(self.http.post(url, {'post': 'yes'}).status_code, 403)
        self.assertTrue(Facture.objects.filter(pk=self.emise.pk).exists())

        self.assertFalse(self.model_admin.has_delete_permission(
            self._request(), self.emise))
        with self.assertRaises(PermissionDenied):
            self.model_admin.delete_model(self._request(), self.emise)
        with self.assertRaises(PermissionDenied):
            self.model_admin.delete_queryset(
                self._request(),
                Facture.objects.filter(pk=self.emise.pk))
        self.assertTrue(Facture.objects.filter(pk=self.emise.pk).exists())

    def test_message_de_refus_nomme_le_chemin_supporte(self):
        self.assertIn('avoir', SUPPRESSION_FACTURE_POSTEE_INTERDITE)

    def test_suppression_facture_brouillon_reste_possible(self):
        self.assertTrue(self.model_admin.has_delete_permission(
            self._request(), self.brouillon))

    # ── (5) scope société ──────────────────────────────────────────────────
    def test_liste_admin_scopee_sur_la_societe_de_l_utilisateur(self):
        reponse = self.http.get(
            reverse('admin:facturation_facture_changelist'))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'FAC-AUD185-EMISE')
        self.assertNotContains(reponse, 'FAC-AUD185-AUTRE-SOCIETE')

        queryset = self.model_admin.get_queryset(self._request())
        self.assertNotIn(self.facture_b, queryset)

    def test_fiche_d_une_autre_societe_introuvable(self):
        reponse = self.http.get(reverse(
            'admin:facturation_facture_change', args=[self.facture_b.pk]))
        # get_object() passe par get_queryset() → l'objet « n'existe pas ».
        self.assertIn(reponse.status_code, (302, 404))
