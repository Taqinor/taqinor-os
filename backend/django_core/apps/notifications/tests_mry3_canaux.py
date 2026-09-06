"""MRY3 — Les canaux par lesquels Meryem est réellement prévenue.

Le moteur de relances ne vaut que si l'alerte ARRIVE. Trois événements portent
le travail de Meryem : `lead_new` (un prospect vient d'arriver),
`relance_due` (ses touches du jour, MRY17) et `premier_contact_depasse`
(l'objectif « moins de 5 minutes » est dépassé, MRY17).

Ce que ce fichier VERROUILLE : pour un utilisateur qui n'a JAMAIS ouvert ses
préférences — le cas réel, personne ne les configure — `resolve_prefs` doit
renvoyer in-app ET push ET e-mail à True sur ces trois événements. Le défaut
générique laisse l'e-mail à False (rien de spammeur) : sans override explicite,
une notification d'arrivée de lead resterait une ligne in-app qu'un téléphone
posé ne montre jamais.

Aucun service payant nouveau : e-mail = SendGrid déjà en place (repli console
en local), push = VAPID auto-généré (`VapidKeyPair.ensure`). Les vérifications
d'exploitation correspondantes (clé SendGrid dans le `.env` serveur, clé VAPID
publique servie, push activé sur le téléphone de Meryem) sont des gestes
serveur — elles ne sont pas simulables ici et ne sont donc PAS mimées par un
faux test qui passerait toujours.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.notifications.models import EventType, NotificationPreference
from apps.notifications.services import default_prefs_for, resolve_prefs

User = get_user_model()

#: Les trois événements du travail quotidien de Meryem. `relance_due` et
#: `premier_contact_depasse` naissent avec MRY17 : tant qu'ils n'existent pas
#: dans `EventType`, ils sont ignorés ici plutôt que d'inventer une clé.
EVENEMENTS_MERYEM = ('lead_new', 'relance_due', 'premier_contact_depasse')


def evenements_declares():
    cles = {choix[0] for choix in EventType.choices}
    return [nom for nom in EVENEMENTS_MERYEM if nom in cles]


class CanauxParDefautTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='MRY3', slug='mry3')
        self.user = User.objects.create_user(
            username='meryem-mry3', password='x', company=self.company)

    def test_lead_new_est_bien_declare(self):
        """Garde-fou anti-faux-vert : si la liste ci-dessus ne correspondait
        plus à aucune clé réelle, tous les tests suivants passeraient à vide."""
        self.assertIn('lead_new', evenements_declares())

    def test_trois_canaux_actifs_sans_ligne_de_preference(self):
        self.assertFalse(
            NotificationPreference.objects.filter(user=self.user).exists())
        for nom in evenements_declares():
            with self.subTest(evenement=nom):
                prefs = resolve_prefs(self.user, nom)
                self.assertTrue(prefs['in_app'], f'{nom} : in-app coupé')
                self.assertTrue(prefs['push'], f'{nom} : push coupé')
                self.assertTrue(prefs['email'], f'{nom} : e-mail coupé')

    def test_une_preference_explicite_prime_toujours(self):
        """L'override de défaut ne doit jamais écraser un choix humain : si
        Meryem coupe l'e-mail, il reste coupé."""
        NotificationPreference.objects.create(
            user=self.user, event_type='lead_new',
            in_app=True, push=True, email=False, whatsapp=False)
        prefs = resolve_prefs(self.user, 'lead_new')
        self.assertFalse(prefs['email'])
        self.assertTrue(prefs['in_app'])

    def test_les_autres_evenements_gardent_le_defaut_sobre(self):
        """Le défaut générique reste « rien de spammeur » : seuls les
        événements explicitement surchargés ouvrent l'e-mail."""
        self.assertFalse(default_prefs_for('chantier_due')['email'])
        self.assertTrue(default_prefs_for('chantier_due')['in_app'])
