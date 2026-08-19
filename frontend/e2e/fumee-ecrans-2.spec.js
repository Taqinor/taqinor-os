// PACT8 — fumée des écrans, GROUPE 2/3. Voir `fumee-ecrans.partition.js` pour
// le pourquoi du découpage et la logique partagée : ce fichier ne fait que
// déclarer sa part.
import { test } from '@playwright/test'

import { declarerGroupe } from './fumee-ecrans.partition.js'

declarerGroupe(test, 1)
