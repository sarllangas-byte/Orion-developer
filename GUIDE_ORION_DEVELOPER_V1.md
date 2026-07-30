# Guide opérationnel ORION Developer V1

## Périmètre

ORION V1 est un exécuteur de mission borné, pas un agent autonome permanent. Il ne choisit jamais sa
mission, ne travaille pas en arrière-plan, n'accède pas au dépôt principal GeoStab et ne possède
aucun outil de merge, push forcé, déploiement ou suppression.

Le seul périmètre initial autorisé est le dépôt fictif `workspace/geostab-demo`.

## Les douze lots intégrés

1. **Initialisation** — arborescence `agent/`, `tools/`, `memory/`, `security/`, `tests/`, `logs/`,
   `reports/`, `workspace/`, `config/` et `.devcontainer/`.
2. **Mission structurée** — JSON contenant objectif, dépôt, contraintes et limites ; statuts
   explicites de `CREATED` à `COMPLETED`, `FAILED` ou `CANCELLED`.
3. **Analyse** — cartographie du type de projet, entrées, tests, configurations, candidats et
   risques sans lire les fichiers sensibles.
4. **Plan** — compréhension, fichiers lus/modifiés/créés, étapes, tests, risques, rollback,
   complexité et autorisation requise ; aucune écriture à ce stade.
5. **Sécurité du workspace** — validation de chaque chemin, confinement réel après résolution des
   liens symboliques et refus systématique des secrets et suppressions.
6. **Git** — dépôt propre obligatoire, refus de `main`/`master`, branche
   `agent/<mission-id>-<description>`, statut, diff et restauration locale seulement.
7. **Modification contrôlée** — opération `create` ou `replace`, motif, hash original, taille,
   contenu, budget, sauvegarde temporaire, écriture atomique et journalisation.
8. **Tests autorisés** — détection des outils présents, exécution sans shell et allowlist définie
   dans `config.yaml` et documentée dans `config/allowed_commands.yaml`.
9. **Correction bornée** — trois corrections, dix itérations et arrêt après deux erreurs identiques,
   projet initial dégradé, régression ou action sensible.
10. **Audit qualité séparé** — objectif, tests, sécurité, périmètre et taille du diff ; recommandation
    `READY_FOR_HUMAN_REVIEW` seulement si tous les contrôles passent.
11. **Rapport final** — mission, plan, branche, fichiers, tests, erreurs, risques, audit, diff et
    décision finale. ORION s'arrête ensuite.
12. **Arrêt d'urgence** — `python -m agent.main stop` crée `STOP_AGENT`. Le moteur le vérifie entre
    les étapes et passe à `CANCELLED` sans nouvelle modification.

## Première démonstration

Dans GitHub Codespaces ou un clone local :

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python scripts/bootstrap_demo.py
python -m agent.main --mission config/mission-rga.example.json --dry-run
python -m agent.main --mission config/mission-rga.example.json
```

Le plan propose de modifier `geostab/scoring.py` et `tests/test_scoring.py`. Saisir `APPROVE` pour
autoriser cette portée. ORION crée une branche `agent/*`, implémente
`calculate_rga_exposure_score`, exécute pytest et Ruff, audite le diff, écrit un rapport et s'arrête.
Il ne crée aucun commit et ne fusionne rien.

## Mission personnalisée

Créer un fichier JSON sur le modèle suivant :

```json
{
  "objective": "Objectif précis et vérifiable",
  "repository": "workspace/geostab-demo",
  "constraints": ["Aucune donnée réelle", "Aucun déploiement"],
  "max_files_changed": 5,
  "max_iterations": 10
}
```

Puis lancer :

```bash
python -m agent.main --mission chemin/mission.json
```

Le scénario RGA fonctionne hors ligne. Une mission générique utilise facultativement GitHub Models
avec le secret Codespaces `GITHUB_MODELS_TOKEN`; le modèle n'obtient jamais de terminal.

## Vérification et arrêt

```bash
python -m agent.main status
python -m agent.main stop
```

Pour autoriser une nouvelle mission après un arrêt, un humain doit supprimer `STOP_AGENT`. L'agent
ne peut pas modifier lui-même cette règle.

Inspecter ensuite :

```bash
cd workspace/geostab-demo
git status --short --branch
git diff
```

Les rapports sont dans `reports/`, les événements dans `logs/orion.jsonl` et la mémoire structurée
dans `memory/orion.db`.
