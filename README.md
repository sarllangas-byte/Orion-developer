# ORION Developer V1

MVP gratuit, contrôlé et traçable d'un agent développeur pour un dépôt GeoStab de démonstration.

ORION V1 :

- travaille uniquement dans un workspace Git isolé ;
- refuse les écritures sur `main` et `master` ;
- ne peut ni supprimer, ni déployer, ni fusionner ;
- n'exécute que les commandes de test définies dans `config.yaml` ;
- journalise objectifs, actions, erreurs et validations dans SQLite ;
- utilise une recette RGA hors-ligne testable sans API ;
- peut demander à GitHub Models un plan et du code JSON pour une mission générique ;
- s'arrête avant commit, push, pull request ou merge.

## Démarrage en cinq commandes

```bash
python -m pip install -r requirements.txt
python scripts/bootstrap_demo.py
python -m pytest -q
python -m agent.main --dry-run \
  --objective "Ajouter une fonction de calcul du score d'exposition RGA."
python -m agent.main \
  --objective "Ajouter une fonction de calcul du score d'exposition RGA."
```

Le dernier appel demande une approbation du plan, crée une branche `orion/objective-N`, écrit deux
fichiers, exécute tests et lint, montre le diff, puis demande une validation finale. Il ne fusionne
rien.

Pour une mission générique, créez un secret `GITHUB_MODELS_TOKEN` ayant seulement la permission
`models: read`. Le scénario RGA reste entièrement hors-ligne.

Documentation complète : [GUIDE_ORION_DEVELOPER_V1.md](GUIDE_ORION_DEVELOPER_V1.md).

> Le score RGA du dépôt de démonstration est fictif. Ce logiciel n'est pas un outil de diagnostic.
