# Architecture technique

## Responsabilités

Le navigateur consomme uniquement l'API versionnée `/api/v1`. Nginx sert les fichiers React et agit comme reverse proxy, de sorte qu'aucune URL technique ni port backend n'est exposé aux utilisateurs. FastAPI valide les contrats Pydantic, applique le JWT et les rôles, puis délègue les accès persistants à SQLAlchemy. PostgreSQL conserve les données dans un volume Docker local.

Dans le backend, `api` contient le protocole HTTP, `schemas` les contrats, `services` les cas d'usage, `repositories` les accès persistants, `models` le domaine relationnel, `security` l'identité, `database` les sessions, `core` la configuration et `utils` les fonctions sans état. Cette séparation permet de déplacer une règle métier hors d'une route sans modifier le frontend.

## Modèle et intégrité

Les principales relations sont : client vers achats, achat vers lignes, ligne vers produit, produit vers catégorie et produit vers mouvements de stock. Les suppressions utilisent `CASCADE`, `RESTRICT` ou `SET NULL` selon le risque métier. Les emails, références, ICE et codes-barres disposent de contraintes d'unicité; les recherches et clés étrangères sont indexées.

Le démarrage initialise les tables sur une installation neuve. Alembic est configuré pour versionner toute évolution ultérieure : depuis `backend`, créer une révision avec `alembic revision --autogenerate -m "description"`, la relire, puis appliquer `alembic upgrade head`.

## Sécurité

Les mots de passe sont hachés avec bcrypt. Les jetons JWT expirent et chaque accès protégé recharge l'utilisateur actif. Les permissions distinguent administrateur, manager, agent et lecteur. Les opérations sensibles sont journalisées. Les secrets restent dans `docker/.env`, ignoré par Git.

Avec PostgreSQL, la sauvegarde et la restauration se font par les scripts de `database/`. Les anciennes routes de sauvegarde et de restauration de l'API sont réservées à SQLite et répondent par une erreur avec PostgreSQL.
