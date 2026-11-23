# Documents de l'ERP (GED) : où va quoi (décisions de Reda, 23/11/2026)

Reda, le 23/11 : « les documents de l'ERP sont à réorganiser… il y a des fichiers dans tous les dossiers, je ne comprends
pas pourquoi c'est éparpillé ». Constat (production lue le 23/11) : 23 documents dans cinq armoires, aucune créée par une
personne : chacune vient d'une fonction différente, à une date différente (armoire par défaut, reprise des pièces jointes,
première puis seconde version de la publication des guides, classement automatique des factures).

## L'ordre décidé

- **« Documentation »** : tous les guides. « Guides » (pour tous), « Guides — Responsables » (palier responsable).
- **« Documents internes » → « Vidéos et publicité »** : les fichiers de travail de Meryem (fiche des vidéos, note de la
  semaine), palier responsable.
- **« Documents clients » → Ventes → Factures → année** : rangé par l'ERP tout seul, on n'y touche pas.
- **« Importé » → « Pièces jointes importées »** : pièces jointes des fiches, rangées par l'ERP ; on n'y touche pas.

## Comment on ajoute un document pour Meryem

Jamais à la main dans l'écran, jamais par la console : le PDF et sa source vont dans `docs/meryem/`, une entrée dans
`docs/meryem/manifest.json` (avec `cabinet`, `dossier`, et `acces: "responsable"` si seuls les responsables doivent le
lire). La commande `publier_documents_meryem` le publie au prochain déploiement complet et notifie la responsable des
leads et la direction : **publier, c'est donc l'envoyer à Meryem.** Demander à Reda avant.

## Fait le 23/11 sur son accord (quatre réponses à boutons)

- Mis à la corbeille (récupérable) : les trois anciens guides retirés de la publication le 17/11 (Guide de Meryem,
  Protocole de rappel, Carte une page) et le doublon de la carte ; son CV et le logo, qui étaient des pièces jointes
  d'une fiche d'essai.
- Supprimée : l'armoire vide « Administratif ».
- Ajoutés à la liste de publication : la fiche des vidéos (partie 1) et la note de la semaine du 23/11.

## Ce qui reste

Les dossiers « Commercial » et « Guides de Meryem » de « Documents internes » restent, vides à l'écran : l'ERP refuse de
supprimer un dossier qui a encore un document en corbeille, pour que la corbeille reste récupérable. Ils s'enlèvent une
fois la corbeille vidée.
