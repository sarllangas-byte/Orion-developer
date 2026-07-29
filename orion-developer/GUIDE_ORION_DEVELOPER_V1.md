# PLAN DE CRÉATION ORION DEVELOPER V1 GRATUIT

Vérification effectuée le **29 juillet 2026** sur les documentations officielles. Les quotas peuvent
changer : les liens de contrôle sont fournis ci-dessous.

## Décision recommandée

Utiliser un **compte personnel GitHub Free**, un dépôt public ne contenant que le POC et des données
fictives, une machine Codespaces 2 cœurs, GitHub Actions sur runner Ubuntu standard, Python 3.12,
SQLite et **GitHub Models avec `openai/gpt-4.1-mini`**. Le scénario RGA livré fonctionne aussi sans
aucun modèle ni jeton.

Cette combinaison réduit les comptes, les secrets et les composants. Ne pas joindre de moyen de
paiement est la barrière de coût la plus simple : GitHub bloque l'usage une fois le quota inclus
épuisé. L'usage payant de GitHub Models est un opt-in séparé.

## 1. Services gratuits, rôles, limites et risques

| Service | Rôle dans V1 | Gratuit vérifié | Risque et parade |
|---|---|---|---|
| GitHub Free personnel | Dépôt, branches, diff, PR et historique | Dépôts publics/privés ; branches protégées gratuites **sur dépôt public** | Un dépôt public ne doit contenir aucune donnée GeoStab/client. Pour un dépôt privé avec protection GitHub, GitHub Pro est requis ; le garde-fou local d'ORION reste actif dans tous les cas. |
| GitHub Codespaces | CPU et environnement Python distants | 120 core-hours et 15 GB-month/mois. Avec 2 cœurs, 120 core-hours représentent environ 60 heures d'exécution murale | Fermer l'onglet ne stoppe pas toujours le Codespace. Régler l'arrêt d'inactivité et cliquer **Stop codespace**. Sans moyen de paiement, l'usage est bloqué au quota. |
| GitHub Actions | Tests CI sur PR | Runner standard gratuit sans compteur de minutes sur dépôt public ; dépôt privé GitHub Free : 2 000 min/mois, 500 MB d'artefacts, cache inclus jusqu'à 10 GB/dépôt | Éviter les runners larges, macOS/Windows, artefacts et boucles CI. Le workflow livré utilise Ubuntu et aucun artefact. |
| GitHub Models | Raisonnement distant optionnel | Le modèle recommandé est actuellement en catégorie **low** : Copilot Free, 15 requêtes/min, 150/jour, 8 000 tokens d'entrée, 4 000 de sortie, 5 requêtes concurrentes | Prototype seulement, quota non garanti, réponse 429 possible. ORION limite les itérations, le contexte et sait exécuter la recette RGA sans modèle. Ne jamais activer l'usage payant. |
| Python 3.12 | Boucle, outils, validations, API | Open source, inclus dans le devcontainer | Figer les versions dans `requirements.txt`, exécuter la CI. |
| SQLite | Mémoire locale | Inclus dans Python, aucun serveur | Un seul processus ORION à la fois ; sauvegarder le fichier DB si l'historique est important. |
| Git | Isolation des changements | Open source, inclus dans Codespaces | ORION refuse `main`/`master` et ne possède aucun outil merge/deploy. |

Sources officielles :

- [Quotas et facturation Codespaces](https://docs.github.com/en/billing/concepts/product-billing/github-codespaces)
- [Arrêter réellement un Codespace](https://docs.github.com/en/codespaces/developing-in-a-codespace/stopping-and-starting-a-codespace)
- [Quotas et facturation GitHub Actions](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [Limites gratuites GitHub Models](https://docs.github.com/en/github-models/use-github-models/prototyping-with-ai-models)
- [Démarrage API GitHub Models](https://docs.github.com/en/github-models/quickstart)
- [Fiche actuelle de GPT-4.1-mini](https://github.com/marketplace/models/azure-openai/gpt-4-1-mini)
- [Branches protégées et disponibilité selon le plan](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)

### Alternatives gratuites, non retenues

- **Gemini API Free Tier** : disponible dans l'EEE sans passer au palier payant, mais les limites
  actives dépendent du projet et sont affichées dans AI Studio ; la capacité n'est pas garantie.
  C'est le premier secours si GitHub Models est indisponible. L'intégration n'est volontairement pas
  incluse dans V1 pour ne pas multiplier comptes et secrets.
  [Quotas officiels](https://ai.google.dev/gemini-api/docs/rate-limits) et
  [facturation officielle](https://ai.google.dev/gemini-api/docs/billing).
- **Hugging Face Inference Providers** : le compte gratuit ne reçoit actuellement que
  **0,10 USD de crédit mensuel**, sujet à changement. Après épuisement, il faut acheter du crédit.
  Les Inference Endpoints dédiés demandent un abonnement actif et une carte ; ils ne conviennent
  donc pas à ce POC zéro euro.
  [Tarifs Inference Providers](https://huggingface.co/docs/inference-providers/en/pricing) et
  [tarifs Endpoints dédiés](https://huggingface.co/docs/inference-endpoints/pricing).
- **Exécution locale d'un LLM** : reportée, car elle contredit la contrainte matérielle.

## 2. Architecture globale

```text
Utilisateur
    ↓
Interface de commande
    ↓
Agent ORION
    ↓
Modèle IA distant
    ↓
Outils Python
    ↓
Workspace Git isolé
    ↓
Tests
    ↓
Validation humaine
    ↓
GitHub
```

- **Utilisateur** : formule l'objectif et approuve le plan puis le résultat.
- **Interface de commande** : `python -m agent.main`; pas de serveur web ni de port ouvert.
- **Agent ORION** : borne les itérations, orchestre et arrête le flux en cas d'erreur.
- **Modèle IA distant** : facultatif pour le scénario RGA ; il ne reçoit que les fichiers
  explicitement lus et ne renvoie que du JSON.
- **Outils Python** : seuls composants autorisés à lire, écrire, appeler Git et lancer les tests.
- **Workspace Git isolé** : dépôt distinct sous `workspace/geostab`, avec branche
  `orion/objective-N`.
- **Tests** : commandes immuables de `config.yaml`, lancées avec `shell=False`.
- **Validation humaine** : obligatoire avant modification et après audit.
- **GitHub** : l'humain peut ensuite committer, pousser et ouvrir une PR. ORION V1 ne le fait pas.

Le modèle n'est pas réellement « au-dessus » des outils : la flèche représente le flux logique.
Techniquement, le programme Python appelle le modèle, valide son JSON, puis décide si des outils
bornés peuvent agir. Le modèle n'obtient jamais un terminal.

## 3. Ordre exact de construction et d'exploitation

1. Créer un dépôt public de démonstration sans données sensibles.
2. Ajouter ce projet ORION et le pousser sur `main`.
3. Activer une règle de protection de `main`.
4. Ouvrir un Codespace 2 cœurs ; le devcontainer installe Python et les dépendances.
5. Créer le secret Codespaces `GITHUB_MODELS_TOKEN`, facultatif pour le test RGA.
6. Exécuter la suite de tests ORION.
7. Amorcer `workspace/geostab`, dépôt Git de démonstration distinct.
8. Lancer une mission en `--dry-run`.
9. Approuver le plan et relancer la mission complète.
10. Examiner le diff, les tests, `logs/orion.jsonl`, `memory/orion.db` et le rapport.
11. Accepter ou refuser. ORION s'arrête sans commit ni push.
12. Seulement après revue humaine, créer manuellement commit, push et PR.

## 4. Composants obligatoires et composants reportés

Obligatoires dans V1 : CLI, configuration, garde de chemins, garde de branche, limites, client JSON,
recette hors-ligne RGA, Git borné, tests/lint bornés, SQLite, journal JSONL, rapport, deux validations,
devcontainer et CI.

Reportés : interface web, Docker hors devcontainer, base vectorielle, multi-agent, ingestion de
dossiers clients, déploiement, auto-merge, création automatique de PR, accès aux issues, RAG,
observabilité cloud, véritable formule métier RGA et ORION GeoStab Observer.

## LIVRABLE 1 — Guide d'installation

### Étape 1 — Créer le dépôt GitHub

1. Connectez-vous à GitHub et choisissez **New repository**.
2. Nom : `orion-developer`.
3. Visibilité recommandée pour ce POC sans données sensibles : **Public**. Ne copiez aucun code
   confidentiel GeoStab ni dossier client.
4. N'ajoutez pas de README automatique si vous poussez directement ce dossier.
5. Dans un terminal local placé dans ce dossier :

```bash
git init -b main
git add .
git commit -m "Initialiser ORION Developer V1"
git remote add origin https://github.com/VOTRE-COMPTE/orion-developer.git
git push -u origin main
```

### Étape 2 — Protéger `main`

Dans le dépôt : **Settings → Branches → Add branch protection rule**. Pattern : `main`. Activez
au minimum **Require a pull request before merging**, **Require status checks to pass** (après le
premier passage CI), **Block force pushes** et **Do not allow deletions**. Appliquez la règle aux
administrateurs si l'option est disponible.

Sur GitHub Free, cette protection est disponible pour les dépôts publics. Sur un dépôt privé
personnel, le contrôle logiciel ORION reste valable, mais la protection distante complète exige
actuellement GitHub Pro.

### Étape 3 — Ouvrir Codespaces et le terminal

Dans le dépôt : **Code → Codespaces → Create codespace on main**. GitHub détecte
`.devcontainer/devcontainer.json`, choisit Python 3.12 et exécute :

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Dans VS Code web, ouvrez **Terminal → New Terminal**. Vérifiez :

```bash
python --version
git --version
python -m pytest -q
```

### Étape 4 — Créer le secret du modèle, facultatif

Le test RGA ne nécessite aucun secret. Pour les objectifs génériques :

1. Créez un fine-grained personal access token GitHub avec uniquement la permission
   **Models: Read** (`models: read`) et une durée courte.
2. Ouvrez **GitHub Settings → Codespaces → Secrets → New secret**.
3. Nom : `GITHUB_MODELS_TOKEN`; valeur : le jeton ; sélectionnez seulement ce dépôt.
4. Redémarrez le Codespace.

Ne mettez jamais le jeton dans `.env`, un prompt, un log, une capture ou Git. `.env` est ignoré,
mais un secret Codespaces est préférable. Le code masque les clés sensibles du journal.

### Étape 5 — Amorcer la démonstration

```bash
python scripts/bootstrap_demo.py
python -m pytest -q
python -m ruff check .
```

Résultat attendu : tous les tests ORION passent ; `workspace/geostab` contient un petit dépôt Git
sur `main`. Le script refuse d'écraser un workspace non vide.

### Étape 6 — Lancer et arrêter

```bash
python -m agent.main --dry-run \
  --objective "Ajouter une fonction de calcul du score d'exposition RGA."

python -m agent.main \
  --objective "Ajouter une fonction de calcul du score d'exposition RGA."
```

Répondez `oui` au périmètre seulement après lecture. Pour arrêter immédiatement : `Ctrl+C`.
L'interruption renvoie le code 130 et aucun merge/deploy n'existe dans le programme.

Après la session, choisissez **Codespaces: Stop Current Codespace** dans la palette ou :

```bash
gh codespace stop
```

Fermer seulement l'onglet du navigateur ne garantit pas l'arrêt.

### Étape 7 — Surveiller les quotas et empêcher les coûts

- GitHub **Settings → Billing and licensing → Usage** : Codespaces, Actions et Models.
- [Vos Codespaces](https://github.com/codespaces) : arrêter ou supprimer les instances inutilisées.
- Conserver la machine 2 cœurs, abaisser l'idle timeout et ne pas activer les prebuilds.
- Ne pas ajouter de carte bancaire ; si une carte existe déjà, créer un budget de 0 USD avec arrêt
  de l'usage et vérifier que GitHub Models paid usage est désactivé.
- Une réponse HTTP 429 du modèle signifie quota temporaire atteint : attendre, ne pas boucler.

## LIVRABLE 2 — Architecture détaillée

```text
orion-developer/
├── .devcontainer/devcontainer.json    Environnement Codespaces 2 cœurs/Python 3.12
├── .github/workflows/ci.yml           Tests et lint sur branche/PR
├── agent/
│   ├── main.py                        CLI et boucle bornée
│   ├── config.py                      Lecture YAML et limites
│   ├── state.py                       Contrats Plan/Change/Result/Run
│   ├── model_client.py                Appel GitHub Models JSON uniquement
│   ├── planner.py                     Plan local RGA ou plan distant
│   ├── executor.py                    Validation et application des changements
│   ├── evaluator.py                   Tests puis lint
│   └── approval.py                    Portes d'approbation humaine
├── tools/
│   ├── audit.py                       Journal JSONL avec masquage
│   ├── security_tools.py              Confinement, branches, budgets
│   ├── filesystem_tools.py            list/read/search/create/write atomique
│   ├── git_tools.py                   branch/status/diff sans shell
│   ├── test_tools.py                  tests/lint configurés
│   └── report_tools.py                Rapport Markdown
├── memory/
│   ├── database.py                    API SQLite paramétrée
│   └── schema.sql                     Dix tables exigées
├── prompts/                           Contrats système/planner/coder/reviewer
├── examples/geostab-demo/             Source du dépôt fictif
├── workspace/geostab/                 Dépôt actif, ignoré par Git
├── scripts/bootstrap_demo.py          Amorçage non destructif
├── tests/                              Tests de l'agent et scénario complet
├── reports/                            Audits finaux, ignorés par Git
├── logs/                               Événements JSONL, ignorés par Git
├── config.yaml                         Politique modifiable
├── .env.example                       Noms de variables, sans secret
├── requirements.txt                   Versions figées
└── pyproject.toml                      Configuration pytest/ruff
```

### Flux d'exécution

```text
Objectif → inventaire borné → plan JSON → validation des chemins → approbation
→ branche orion/* → propositions JSON → contrôle du budget → écritures atomiques
→ pytest → ruff → au plus 3 corrections et 10 itérations
→ diff + rapport → validation humaine → arrêt
```

### Outils autorisés et implantation

| Contrat demandé | Implantation |
|---|---|
| `list_files`, `read_file`, `search_code`, `write_file`, `create_file` | `FileSystemTools` |
| `show_diff`, `create_git_branch`, `get_git_status` | `GitTools` |
| `run_tests`, `run_linter`, `read_test_results` | `TestTools` |
| `save_memory`, `load_memory` | `MemoryDatabase` |
| `create_report` | `ReportTools` |
| `request_approval` | `ApprovalGate` |

Chaque résultat est un `ToolResult {ok, tool, summary, data, error}`. Le modèle ne peut pas choisir
une commande : `pytest` et `ruff` proviennent uniquement de `config.yaml` et sont exécutés avec
`shell=False`.

### Mémoire

Les dix tables sont `objectives`, `tasks`, `plans`, `actions`, `tool_calls`, `results`, `errors`,
`approvals`, `lessons`, `file_changes`. Les requêtes utilisent des paramètres SQLite. Le journal
`actions` possède tous les champs du JSON demandé, dont `files_changed_json`, `created_at` et
`approval_required`.

### Règles de sécurité effectives

- Chemin absolu, `..`, symlink sortant, dossier ignoré et nom sensible : refusés.
- Extension non autorisée : écriture refusée.
- `main`, `master` ou branche détachée : écriture refusée.
- Branche créée : seulement `orion/...`.
- Suppression : aucun outil exposé.
- Commande système produite par modèle : jamais exécutée.
- Déploiement, merge, push, modification GitHub, achat : aucun code correspondant.
- Maximum 10 fichiers modifiés, 10 itérations, 3 reprises par tâche.
- Contenu maximal lu : 200 000 octets par fichier ; inventaire/recherche : 200 résultats.
- Approbation avant écriture et après diff.

## LIVRABLE 3 — Code complet du MVP

Le code complet est livré dans cette arborescence, fichier par fichier, avec les chemins exacts
ci-dessus. Les principaux points d'entrée sont :

- `agent/main.py` : `python -m agent.main`
- `scripts/bootstrap_demo.py` : création sûre du dépôt fictif
- `config.yaml` : toutes les limites modifiables demandées
- `memory/schema.sql` : schéma SQLite complet
- `.devcontainer/devcontainer.json` : compatibilité Codespaces

Le runtime ne dépend que de PyYAML ; pytest et ruff sont des dépendances de vérification. L'appel
HTTP GitHub Models utilise la bibliothèque standard Python.

## LIVRABLE 4 — Tests

Exécuter :

```bash
python -m pytest -q
python -m ruff check .
```

Couverture fonctionnelle :

- `test_security_paths.py` : traversée, absolu, secret, extension ;
- `test_iteration_limits.py` : 10 itérations et 3 reprises ;
- `test_main_branch_refusal.py` : aucune écriture sur `main` ;
- `test_memory.py` : dix tables et aller-retour SQLite ;
- `test_git_tool.py` : branche `orion/*` et refus d'une autre branche ;
- `test_geostab_scenario.py` : objectif RGA complet hors-ligne, branche, code, tests, lint et diff.

Résultat attendu : code de sortie 0. La CI rejoue ces commandes sur chaque PR.

## LIVRABLE 5 — Guide d'utilisation

### Lancer une mission

Pour prévisualiser :

```bash
python -m agent.main --dry-run --objective "Votre objectif précis"
```

Pour exécuter après revue :

```bash
python -m agent.main --objective "Votre objectif précis"
```

`--approve-plan` représente une approbation explicite fournie dans la commande et évite seulement
la première question ; la validation finale reste interactive.

### Suivre actions, mémoire, statut et diff

```bash
tail -f logs/orion.jsonl
cd workspace/geostab
git status --short --branch
git diff
```

Pour interroger SQLite :

```bash
python -m sqlite3 memory/orion.db "SELECT id, description, status FROM objectives;"
```

Les rapports se trouvent dans `reports/objective-*.md`.

### Accepter

Répondre `oui` à la validation finale. Cela enregistre l'approbation, mais ne commite rien. Après
revue humaine, depuis `workspace/geostab` :

```bash
git status
git diff
git add geostab_demo/rga.py tests/test_rga.py
git commit -m "Ajouter le score RGA fictif"
git push -u origin HEAD
```

Ouvrir ensuite une PR vers `main` dans GitHub. Ne fusionner qu'après CI et revue.

### Refuser

Répondre autre chose que `oui`. Rien n'est fusionné. Conserver une sauvegarde récupérable :

```bash
cd workspace/geostab
git stash push -u -m "ORION résultat refusé"
git switch main
```

### Reprendre après erreur

Lire d'abord la dernière erreur :

```bash
git status --short --branch
python -m sqlite3 ../../memory/orion.db \
  "SELECT created_at, error_type, message FROM errors ORDER BY id DESC LIMIT 5;"
```

Corriger la cause (quota, dépendance, test), puis relancer avec un nouvel objectif précis. ORION ne
reprend pas silencieusement une boucle interrompue.

### Réinitialiser sans perte

ORION n'a pas le droit de supprimer. Déplacer le workspace actuel en sauvegarde, puis réamorcer :

```bash
mv workspace/geostab workspace/geostab-backup
python scripts/bootstrap_demo.py
```

Sous PowerShell :

```powershell
Move-Item -LiteralPath workspace\geostab -Destination workspace\geostab-backup
python scripts/bootstrap_demo.py
```

### Arrêt immédiat

`Ctrl+C`, puis arrêter le Codespace. Le moteur capture l'interruption et s'arrête ; il ne lance
aucune tâche de fond, fusion ou opération de production.

## LIVRABLE 6 — Étape suivante : ORION GeoStab Observer

Après validation de V1, créer un **processus séparé en lecture seule**, pas un mode caché du
Developer :

1. Réutiliser `SecurityGuard`, `AuditLogger`, `MemoryDatabase` et les limites.
2. N'exposer que `list_files`, `read_file`, `search_code` adapté aux formats de dossiers et
   `create_report`.
3. Retirer totalement `write_file`, `create_file`, `GitTools`, `TestTools` et tout accès réseau non
   nécessaire.
4. Utiliser un workspace monté/dupliqué en lecture seule avec données fictives au début.
5. Produire un JSON d'observations séparant `faits_observés`, `hypothèses`, `informations_manquantes`,
   `incertitudes` et `revue_humaine_requise`.
6. Interdire les mots/conclusions définitives de diagnostic et afficher un avertissement.
7. Tester l'absence d'écriture, la résistance aux fichiers malveillants, la taille, les données
   personnelles et les injections de prompt dans les documents.
8. Faire valider le modèle de données et les formulations par un expert GeoStab et un référent RGPD
   avant tout dossier réel.

Le premier essai Observer doit seulement décrire la présence et la structure de pièces fictives.
Il ne doit ni modifier le code, ni calculer une décision, ni produire un rapport client définitif.
