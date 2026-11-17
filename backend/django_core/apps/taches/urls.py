"""Routes de l'app `taches` — les 106 couples méthode × chemin de reference/api.md §3, déclarés ici
UNE fois (monté par `path('taches/', include('apps.taches.urls'))` en fin de `_APP_URLS`).

Une vue non construite lève `PasEncore` (501) : les tâches de construction remplissent les vues,
jamais ce fichier. Noms : `taches-<chemin>`.
"""
from django.urls import path

from apps.taches.views import (
    agenda,
    agenda_externe,
    donnees,
    erp,
    journee,
    presence,
    projets,
    reglages,
    rythme,
    saisie,
    taches,
)

# §3.1 — journée, rituels, agenda
journee_urls = [
    path('aujourdhui/', journee.AujourdhuiVue.as_view(), name='taches-aujourdhui'),
    path('aujourdhui/ailleurs/', erp.AilleursVue.as_view(), name='taches-aujourdhui-ailleurs'),
    path('badge/', journee.BadgeVue.as_view(), name='taches-badge'),
    path('vu/', journee.VuVue.as_view(), name='taches-vu'),
    path('journee/proposition/', journee.PropositionJourneeVue.as_view(), name='taches-journee-proposition'),
    path('journee/priorites/', journee.PrioritesVue.as_view(), name='taches-journee-priorites'),
    path('journee/point/', journee.PointVue.as_view(), name='taches-journee-point'),
    path('journee/planifier/', journee.PlanifierJourneeVue.as_view(), name='taches-journee-planifier'),
    path('journee/essentiel/', journee.EssentielVue.as_view(), name='taches-journee-essentiel'),
    path('journee/alleger/', journee.AllegerVue.as_view(), name='taches-journee-alleger'),
    path('journee/cloture/', journee.ClotureVue.as_view(), name='taches-journee-cloture'),
    path('journee/cloturer/', journee.CloturerVue.as_view(), name='taches-journee-cloturer'),
    path('agenda/', agenda.AgendaVue.as_view(), name='taches-agenda'),
    path('recherche/', taches.RechercheVue.as_view(), name='taches-recherche'),
]

# §3.2 — saisie, À trier, tâches
tache_urls = [
    path('saisie-rapide/', saisie.SaisieRapideVue.as_view(), name='taches-saisie-rapide'),
    path('capture/', saisie.CaptureVue.as_view(), name='taches-capture'),
    path('taches/', taches.TachesVue.as_view(), name='taches-taches'),
    path('taches/lot/', taches.LotVue.as_view(), name='taches-lot'),
    path('taches/lier-activite/', erp.LierActiviteVue.as_view(), name='taches-lier-activite'),
    path('taches/<int:id>/', taches.TacheVue.as_view(), name='taches-tache'),
    path('taches/<int:id>/planifier/', taches.TachePlanifierVue.as_view(), name='taches-tache-planifier'),
    path('taches/<int:id>/terminer/', taches.TacheTerminerVue.as_view(), name='taches-tache-terminer'),
    path('taches/<int:id>/rouvrir/', taches.TacheRouvrirVue.as_view(), name='taches-tache-rouvrir'),
    path('taches/<int:id>/trancher/', taches.TacheTrancherVue.as_view(), name='taches-tache-trancher'),
    path('taches/<int:id>/sauter/', taches.TacheSauterVue.as_view(), name='taches-tache-sauter'),
    path('taches/<int:id>/attendre/', taches.TacheAttendreVue.as_view(), name='taches-tache-attendre'),
    path('taches/<int:id>/recu/', taches.TacheRecuVue.as_view(), name='taches-tache-recu'),
    path('taches/<int:id>/reordonner/', taches.TacheReordonnerVue.as_view(), name='taches-tache-reordonner'),
    path('taches/<int:id>/restaurer/', taches.TacheRestaurerVue.as_view(), name='taches-tache-restaurer'),
    path('taches/<int:id>/rappels/', taches.TacheRappelsVue.as_view(), name='taches-tache-rappels'),
    path('taches/<int:id>/changement/apercu/', taches.TacheChangementApercuVue.as_view(),
         name='taches-tache-changement-apercu'),
    path('convertir-activite/', erp.ConvertirActiviteVue.as_view(), name='taches-convertir-activite'),
    path('rappels/<int:id>/', taches.RappelVue.as_view(), name='taches-rappel'),
    path('rappels/<int:id>/repeter/', taches.RappelRepeterVue.as_view(), name='taches-rappel-repeter'),
    path('recurrences/<int:id>/', taches.RecurrenceVue.as_view(), name='taches-recurrence'),
    path('checklist/', taches.ChecklistVue.as_view(), name='taches-checklist'),
    path('checklist/<int:id>/', taches.ElementChecklistVue.as_view(), name='taches-checklist-element'),
    path('checklist/<int:id>/reordonner/', taches.ElementChecklistReordonnerVue.as_view(),
         name='taches-checklist-reordonner'),
    path('etiquettes/', taches.EtiquettesVue.as_view(), name='taches-etiquettes'),
    path('etiquettes/<int:id>/', taches.EtiquetteVue.as_view(), name='taches-etiquette'),
    path('vues/', taches.VuesVue.as_view(), name='taches-vues'),
    path('vues/<int:id>/', taches.VueEnregistreeVue.as_view(), name='taches-vue'),
    path('supprimees/', taches.SupprimeesVue.as_view(), name='taches-supprimees'),
    path('gestes/', taches.GestesVue.as_view(), name='taches-gestes'),
    path('gestes/<int:id>/annuler/', taches.GesteAnnulerVue.as_view(), name='taches-geste-annuler'),
    path('suggestions/', erp.SuggestionsVue.as_view(), name='taches-suggestions'),
    path('suggestions/<int:id>/accepter/', erp.SuggestionAccepterVue.as_view(), name='taches-suggestion-accepter'),
    path('suggestions/<int:id>/refuser/', erp.SuggestionRefuserVue.as_view(), name='taches-suggestion-refuser'),
]

# §3.3 — projets, étapes, modèles, revue
projet_urls = [
    path('projets/', projets.ProjetsVue.as_view(), name='taches-projets'),
    path('projets/trier-par-priorite/', projets.TrierParPrioriteVue.as_view(), name='taches-projets-trier'),
    path('projets/<int:id>/', projets.ProjetVue.as_view(), name='taches-projet'),
    path('projets/<int:id>/reordonner/', projets.ProjetReordonnerVue.as_view(), name='taches-projet-reordonner'),
    path('projets/<int:id>/vue/', projets.ProjetAffichageVue.as_view(), name='taches-projet-vue'),
    path('projets/<int:id>/planification/apercu/', projets.PlanificationApercuVue.as_view(),
         name='taches-projet-planification-apercu'),
    path('projets/<int:id>/planification/', projets.PlanificationVue.as_view(),
         name='taches-projet-planification'),
    path('projets/<int:id>/decaler/', projets.DecalerVue.as_view(), name='taches-projet-decaler'),
    path('projets/<int:id>/terminer/', projets.ProjetTerminerVue.as_view(), name='taches-projet-terminer'),
    path('projets/<int:id>/rouvrir/', projets.ProjetRouvrirVue.as_view(), name='taches-projet-rouvrir'),
    path('projets/<int:id>/restaurer/', projets.ProjetRestaurerVue.as_view(), name='taches-projet-restaurer'),
    path('projets/<int:id>/dupliquer/', projets.DupliquerVue.as_view(), name='taches-projet-dupliquer'),
    path('projets/<int:id>/enregistrer-modele/', projets.EnregistrerModeleVue.as_view(),
         name='taches-projet-enregistrer-modele'),
    path('sections/', projets.SectionsVue.as_view(), name='taches-sections'),
    path('sections/<int:id>/', projets.SectionVue.as_view(), name='taches-section'),
    path('sections/<int:id>/reordonner/', projets.SectionReordonnerVue.as_view(), name='taches-section-reordonner'),
    path('modeles/', projets.ModelesVue.as_view(), name='taches-modeles'),
    path('modeles/<int:id>/', projets.ModeleVue.as_view(), name='taches-modele'),
    path('modeles/<int:id>/instancier/', projets.ModeleInstancierVue.as_view(), name='taches-modele-instancier'),
    path('revue/projets/', projets.RevueProjetsVue.as_view(), name='taches-revue-projets'),
    path('revue/projets/<int:projet_id>/', projets.RevueDecisionVue.as_view(), name='taches-revue-decision'),
]

# §3.4 — rythme, réglages, iPhone, données, agendas externes
reglage_urls = [
    path('rythme/', rythme.RythmeVue.as_view(), name='taches-rythme'),
    path('rythme/propositions/<int:id>/repondre/', rythme.RepondrePropositionVue.as_view(),
         name='taches-proposition-repondre'),
    path('preferences/', rythme.PreferencesVue.as_view(), name='taches-preferences'),
    path('preferences/<str:cle>/', rythme.PreferenceVue.as_view(), name='taches-preference'),
    path('coach/entete/', rythme.CoachEnteteVue.as_view(), name='taches-coach-entete'),
    path('reglages/', reglages.ReglagesVue.as_view(), name='taches-reglages'),
    path('reglages-societe/', reglages.ReglagesSocieteVue.as_view(), name='taches-reglages-societe'),
    path('jetons/', presence.JetonsVue.as_view(), name='taches-jetons'),
    path('jetons/<int:id>/revoquer/', presence.JetonRevoquerVue.as_view(), name='taches-jeton-revoquer'),
    path('mon-iphone/test-notification/', presence.TestNotificationVue.as_view(),
         name='taches-test-notification'),
    path('tuile/', presence.TuileVue.as_view(), name='taches-tuile'),
    path('flux/<str:jeton>.ics', presence.FluxVue.as_view(), name='taches-flux'),
    path('mes-donnees/', donnees.MesDonneesVue.as_view(), name='taches-mes-donnees'),
    path('tout-effacer/', donnees.ToutEffacerVue.as_view(), name='taches-tout-effacer'),
    path('agendas-externes/', agenda_externe.AgendasExternesVue.as_view(), name='taches-agendas-externes'),
    path('agendas-externes/<int:id>/', agenda_externe.AgendaExterneVue.as_view(), name='taches-agenda-externe'),
    path('agendas-externes/<int:id>/rafraichir/', agenda_externe.AgendaExterneRafraichirVue.as_view(),
         name='taches-agenda-externe-rafraichir'),
]

urlpatterns = journee_urls + tache_urls + projet_urls + reglage_urls
