# ms-entrepot-omop

| Information | Valeur |
| :--- | :--- |
| Service Name | `ms-entrepot-omop` |
| Groupe | G3 — Health Data Hub |
| Rôle fonctionnel | Réception des données cliniques FHIR, pseudonymisation, conversion au standard OMOP et contrôle qualité. |
| IP Proxmox | `192.168.1.13` |
| Port | `8006` |
| Route API Gateway | `/api/v1/entrepot/**` |

G3 : ajoutez ici l'implémentation du service et exposez sa documentation OpenAPI à `/docs`.

## Lancer l'environnement G3 en local

Prérequis : Docker et Docker Compose.

```bash
cd ms-entrepot-omop
cp .env.g3.example .env.g3
docker compose -f docker-compose.g3.yml --env-file .env.g3 up --build
```

Vérification :

```bash
curl.exe http://localhost:8006/health
```

Tout remettre à zéro (le SQL de db/init/ ne s'exécute qu'au premier démarrage sur un volume vide) :

```bash
docker compose -f docker-compose.g3.yml --env-file .env.g3 down -v
```

Le fichier .env.g3 ne doit jamais être poussé sur GitHub.
