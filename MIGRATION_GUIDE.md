# Guide de Migration - InvoiceToSheet AI

## Structure de Base de Données Existante

Le système utilise déjà :
- `utilisateurs` : Table principale des utilisateurs (liaison avec `auth.users`)
- `entreprises` : Table des entreprises/organisations
- Beaucoup d'autres tables pour CRM/Email marketing

## Tables Créées pour InvoiceToSheet AI

Deux nouvelles tables sont créées spécifiquement pour InvoiceToSheet AI :

### 1. `invoicetosheet_profiles`
Stocke la configuration spécifique de chaque utilisateur pour InvoiceToSheet AI.

**Colonnes :**
- `id` (UUID, PK) → Référence `utilisateurs.id`
- `email` (TEXT)
- `google_refresh_token` (TEXT)
- `target_sheet_id` (TEXT)
- `monthly_limit` (INTEGER, default: 100)
- `created_at`, `updated_at` (TIMESTAMP)

### 2. `invoicetosheet_usage_logs`
Stocke tous les traitements d'invoices pour facturation et analytics.

**Colonnes :**
- `id` (UUID, PK)
- `user_id` (UUID) → Référence `utilisateurs.id`
- `entreprise_id` (UUID) → Référence `entreprises.id`
- `file_name`, `file_size`
- `status` ('success', 'failed', 'processing')
- `extracted_data` (JSONB)
- `error_message`, `processing_time_ms`
- `created_at` (TIMESTAMP)

## Intégration avec le Système Existant

### Utilisateurs
- Utilise la table `utilisateurs` existante
- L'ID utilisateur vient de `auth.users` (UUID)
- Le profil InvoiceToSheet est lié via `invoicetosheet_profiles.id = utilisateurs.id`

### Entreprises
- Récupère `entreprise_id` depuis `utilisateurs.entreprise_id`
- Stocke dans `invoicetosheet_usage_logs.entreprise_id` pour analytics

### Authentification
- Utilise Supabase Auth existant
- JWT tokens vérifiés via `auth.users`
- OAuth Google tokens capturés via trigger automatique

## Installation

### 1. Exécuter le Schema SQL

Dans Supabase SQL Editor, exécutez :

```sql
-- Le fichier: supabase/invoicetosheet_schema.sql
```

Cela créera :
- Les 2 tables nécessaires
- Les index pour performance
- Les RLS policies
- Le trigger pour capturer les tokens OAuth

### 2. Vérifier les Permissions

Assurez-vous que le service role key a accès à :
- `invoicetosheet_profiles`
- `invoicetosheet_usage_logs`
- `utilisateurs` (lecture)
- `entreprises` (lecture)

### 3. Tester l'Intégration

1. Créer un utilisateur via Supabase Auth
2. Vérifier que le trigger crée automatiquement un profil dans `invoicetosheet_profiles`
3. Tester l'upload d'une facture

## Modifications du Code

### Backend (FastAPI)

Toutes les références ont été mises à jour :
- `user_profiles` → `invoicetosheet_profiles`
- `usage_logs` → `invoicetosheet_usage_logs`
- Récupération de `entreprise_id` depuis `utilisateurs`

### Frontend

Aucune modification nécessaire, utilise toujours l'API backend.

## Sécurité

### Row Level Security (RLS)

- Les utilisateurs peuvent voir/modifier uniquement leur propre profil
- Les utilisateurs peuvent voir uniquement leurs propres logs d'utilisation
- Le service role a accès complet pour les opérations backend

### Tokens OAuth

- Capturés automatiquement via trigger sur `auth.users`
- Stockés de manière sécurisée dans `google_refresh_token`
- Utilisés uniquement pour accéder à Google Sheets API

## Données de Test

Pour tester avec un utilisateur existant :

```sql
-- Créer un profil de test
INSERT INTO invoicetosheet_profiles (id, email, monthly_limit)
SELECT id, email, 100
FROM utilisateurs
WHERE id = 'VOTRE_USER_ID'
ON CONFLICT (id) DO NOTHING;
```

## Monitoring

Les métriques Prometheus incluent :
- `supabase_db_calls_total` avec labels pour `invoicetosheet_profiles` et `invoicetosheet_usage_logs`
- Temps de traitement des factures

## Support Multi-Entreprise

Le système est déjà multi-entreprise grâce à :
- `invoicetosheet_usage_logs.entreprise_id` pour filtrer par organisation
- Possibilité d'ajouter des limites par entreprise si nécessaire
