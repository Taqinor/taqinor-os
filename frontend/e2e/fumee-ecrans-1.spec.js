// PACT8 — fumée des écrans, GROUPE 1/3. Voir `fumee-ecrans.partition.js` pour
// le pourquoi du découpage et la logique partagée : ce fichier ne fait que
// déclarer sa part. Le groupe 1 porte en plus les deux gardes (lecture des
// routes + complétude de l'union), qui sont purement calculatoires.
import { test } from '@playwright/test'

import { declarerGardeUnion, declarerGroupe } from './fumee-ecrans.partition.js'

declarerGardeUnion(test)
declarerGroupe(test, 0)
