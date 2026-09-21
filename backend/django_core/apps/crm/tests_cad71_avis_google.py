"""CAD71 — `avis_google` enverrait au client le lien de SON DEVIS à la
place du lien d'avis.

Avant CAD71 : le texte disait « un avis sur Google nous aide énormément :
{lien} », mais dans `message_pour_etape` le contexte `lien` n'était
alimenté QUE par `url_proposition(devis)` — aucun champ « lien de la fiche
Google » n'existait. Un lead avec devis assigné `avis_google` recevait donc
le lien de SA proposition à la place d'un lien vers la fiche Google.

Fix : placeholder dédié `{lien_google}`, alimenté par
`CompanyProfile.lien_avis_google` (réglage société) ; et
`verifier_gabarit_assignable` refuse l'assignation du gabarit tant que ce
réglage est vide, en nommant le réglage manquant.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from decimal import Decimal

from apps.crm import horaires
from apps.crm.models import Client, Lead, RelanceEtape
from apps.crm.services import (
    GabaritNonAssignable, message_pour_etape, verifier_gabarit_assignable,
)
from apps.parametres.models import CompanyProfile
from apps.ventes.models import Devis

User = get_user_model()

LUNDI = datetime.datetime(2026, 9, 7, 9, 0, tzinfo=horaires.CASABLANCA)


def _company(slug, *, lien_avis_google=''):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.update_or_create(
        company=company, defaults={'lien_avis_google': lien_avis_google})
    return company


class VerifierGabaritAssignableTests(TestCase):
    """Le Done « refus nommant le réglage » / « avec lien → assignable »."""

    def test_refuse_avis_google_sans_lien_google(self):
        company = _company('cad71-vide', lien_avis_google='')
        with self.assertRaises(GabaritNonAssignable) as ctx:
            verifier_gabarit_assignable(company, 'avis_google')
        self.assertIn('lien de la fiche Google', str(ctx.exception))

    def test_accepte_avis_google_avec_lien_google(self):
        company = _company(
            'cad71-rempli',
            lien_avis_google='https://g.page/r/exemple-taqinor/review')
        verifier_gabarit_assignable(company, 'avis_google')  # ne lève rien

    def test_un_gabarit_sans_exigence_nest_jamais_refuse(self):
        """`identite` (et tout gabarit hors `_GABARITS_REGLAGE_REQUIS`) n'a
        aucune exigence — comportement historique inchangé."""
        company = _company('cad71-sans-exigence', lien_avis_google='')
        verifier_gabarit_assignable(company, 'identite')  # ne lève rien

    def test_sans_profil_du_tout_le_refus_tient_quand_meme(self):
        """Une société sans `CompanyProfile` (jamais créé) ne doit pas planter
        — elle refuse, comme si le réglage était vide."""
        company, _ = Company.objects.get_or_create(
            slug='cad71-sans-profil', defaults={'nom': 'cad71-sans-profil'})
        with self.assertRaises(GabaritNonAssignable):
            verifier_gabarit_assignable(company, 'avis_google')


class MessagePourEtapeAvisGoogleTests(TestCase):
    """Le Done « avec lien → c'est le lien Google qui est rendu »."""

    def _lead_et_touche(self, company):
        acteur = User.objects.create_user(
            username=f'{company.slug}-u', password='x',
            role_legacy='responsable', company=company, first_name='Conseiller')
        lead = Lead.objects.create(
            company=company, nom='Benali', prenom='Aziz',
            ville='Casablanca', telephone='+212651971400', owner=acteur)
        etape = RelanceEtape.objects.create(
            company=company, lead=lead, ordre=1, canal='whatsapp',
            due_date=LUNDI.date(), due_at=LUNDI, cadence='apres_devis',
            template_cle='avis_google')
        return acteur, etape

    def test_sans_lien_google_la_phrase_est_omise_pas_un_blanc(self):
        company = _company('cad71-rendu-vide', lien_avis_google='')
        acteur, etape = self._lead_et_touche(company)
        rendu = message_pour_etape(etape, user=acteur)
        self.assertIn('lien_google', rendu['placeholders_manquants'])
        self.assertNotIn('{lien_google}', rendu['message'])
        self.assertNotIn(' :  .', rendu['message'])
        self.assertNotIn(' : .', rendu['message'])

    def test_avec_lien_google_cest_ce_lien_qui_est_rendu(self):
        lien = 'https://g.page/r/exemple-taqinor/review'
        company = _company('cad71-rendu-plein', lien_avis_google=lien)
        acteur, etape = self._lead_et_touche(company)
        rendu = message_pour_etape(etape, user=acteur)
        self.assertNotIn('lien_google', rendu['placeholders_manquants'])
        self.assertIn(lien, rendu['message'])

    def test_le_lien_du_devis_najamais_dans_le_rendu_avis_google(self):
        """Anti-régression directe du bug : MÊME avec un devis attaché à la
        touche (donc `{lien}` calculable), le lien de la proposition ne doit
        JAMAIS apparaître dans `avis_google` — il n'y a plus de `{lien}`
        dans ce gabarit, seulement `{lien_google}`."""
        lien_google = 'https://g.page/r/exemple-taqinor/review'
        company = _company('cad71-rendu-devis', lien_avis_google=lien_google)
        acteur, etape = self._lead_et_touche(company)
        client = Client.objects.create(
            company=company, nom='Benali', email='cad71-devis@ex.com')
        devis = Devis.objects.create(
            company=company, reference='DEV-CAD71-0001', client=client,
            lead=etape.lead, statut='envoye', taux_tva=Decimal('20.00'))
        etape.devis = devis
        etape.save(update_fields=['devis'])
        rendu = message_pour_etape(etape, user=acteur)
        self.assertNotIn('/proposal/', rendu['message'])
        self.assertNotIn('/devis/', rendu['message'])
        self.assertIn(lien_google, rendu['message'])
