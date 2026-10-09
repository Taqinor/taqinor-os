"""ACHT73 (C-ACHT-069) — un référentiel en usage ne se supprime pas (409 FR
nommant l'usage, rien d'effacé) : étape de chantier portée par un chantier,
équipe terrain affectée, champ de fiche ayant des valeurs, gabarit ayant des
relevés ; les inutilisés se suppriment (204 + AuditLog). `ensure_fiche_releve`
ne supprime plus de valeurs ; une recette dont l'instrument est introuvable
porte l'avertissement « Instrument de l'essai « isolement » supprimé ».

Rejoue COUT-8 : DELETE étape utilisée 204, equipe_ref_id None, valeurs [].

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht73_referentiels_en_usage"
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations import field_services, services
from apps.installations.models import (
    CommissioningRecord, Equipe, FicheInterventionChamp,
    FicheInterventionTemplate, FicheInterventionValeur, Installation,
    Intervention, StageModele,
)

User = get_user_model()
BASE = '/api/django/installations'


class ReferentielsEnUsageTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACHT73', slug='acht73-co')
        self.admin = User.objects.create_user(
            username='admin-acht73', password='x', company=self.company,
            role_legacy='admin', is_superuser=False)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.etape_utilisee = StageModele.objects.create(
            company=self.company, cle='cq_perso', libelle='CQ perso',
            ordre=90)
        self.etape_libre = StageModele.objects.create(
            company=self.company, cle='libre', libelle='Libre', ordre=91)
        self.chantier = Installation.objects.create(
            company=self.company, reference='CH-ACHT73',
            etape=self.etape_utilisee)
        self.eq_utilisee = Equipe.objects.create(
            company=self.company, nom='Eq1')
        self.eq_libre = Equipe.objects.create(
            company=self.company, nom='Eq2')
        self.iv = Intervention.objects.create(
            company=self.company, installation=self.chantier,
            type_intervention='controle', equipe_ref=self.eq_utilisee,
            statut=Intervention.Statut.TERMINEE)
        self.template = FicheInterventionTemplate.objects.create(
            company=self.company, nom='Contrôle', type_intervention='controle')
        self.champ = FicheInterventionChamp.objects.create(
            company=self.company, template=self.template, cle='isolement',
            libelle='Isolement', type_champ='nombre')
        self.champ_libre = FicheInterventionChamp.objects.create(
            company=self.company, template=self.template, cle='libre',
            libelle='Libre', type_champ='texte')
        self.releve = field_services.ensure_fiche_releve(self.iv)
        self.valeur = FicheInterventionValeur.objects.get(
            releve=self.releve, champ=self.champ)
        self.valeur.valeur = '550'
        self.valeur.save()

    def test_etape_en_usage_409(self):
        r = self.api.delete(f'{BASE}/etapes-chantier/{self.etape_utilisee.id}/')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn('Utilisé par 1 chantier', str(r.data))
        self.chantier.refresh_from_db()
        self.assertEqual(self.chantier.etape_id, self.etape_utilisee.id)
        r = self.api.delete(f'{BASE}/etapes-chantier/{self.etape_libre.id}/')
        self.assertEqual(r.status_code, 204)

    def test_equipe_affectee_409(self):
        r = self.api.delete(f'{BASE}/equipes/{self.eq_utilisee.id}/')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn('Affectée à 1 intervention', str(r.data))
        self.iv.refresh_from_db()
        self.assertEqual(self.iv.equipe_ref_id, self.eq_utilisee.id)
        r = self.api.delete(f'{BASE}/equipes/{self.eq_libre.id}/')
        self.assertEqual(r.status_code, 204)

    def test_champ_et_gabarit_en_usage_409(self):
        r = self.api.delete(f'{BASE}/fiche-intervention-champs/{self.champ.id}/')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertTrue(FicheInterventionValeur.objects.filter(
            pk=self.valeur.pk, valeur='550').exists())
        r = self.api.delete(
            f'{BASE}/fiche-intervention-templates/{self.template.id}/')
        self.assertEqual(r.status_code, 409, r.data)
        r = self.api.delete(
            f'{BASE}/fiche-intervention-champs/{self.champ_libre.id}/')
        self.assertEqual(r.status_code, 204)

    def test_ensure_fiche_releve_ne_supprime_pas_de_valeur(self):
        # Gabarit changé : la valeur de l'ancien champ reste en historique.
        autre = FicheInterventionTemplate.objects.create(
            company=self.company, nom='Autre', type_intervention='controle',
            actif=False)
        FicheInterventionChamp.objects.create(
            company=self.company, template=autre, cle='x', libelle='X',
            type_champ='texte')
        self.releve.template = autre
        self.releve.save()
        field_services.ensure_fiche_releve(self.iv)
        self.assertTrue(FicheInterventionValeur.objects.filter(
            pk=self.valeur.pk, valeur='550').exists())

    def test_avertissement_instrument_supprime(self):
        fiche = CommissioningRecord.objects.create(
            company=self.company, installation=self.chantier,
            instruments_par_essai={'isolement': 999999})
        comparaison = services.comparaison_recette_ci(fiche)
        self.assertIn("Instrument de l'essai « isolement » supprimé.",
                      comparaison['avertissements'])
