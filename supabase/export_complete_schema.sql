-- Requête complète pour exporter TOUTE la structure en Markdown
-- Exécutez cette requête dans Supabase SQL Editor
-- Copiez le résultat et collez-le dans un fichier .md

DO $$
DECLARE
    result TEXT := '';
    table_rec RECORD;
    col_rec RECORD;
    idx_rec RECORD;
    fk_rec RECORD;
BEGIN
    -- Header
    result := result || '# Structure de la Base de Données\n\n';
    result := result || 'Généré le: ' || CURRENT_TIMESTAMP || E'\n\n';
    result := result || '---\n\n';
    
    -- Tables
    FOR table_rec IN 
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
          AND table_name NOT LIKE 'pg_%'
        ORDER BY table_name
    LOOP
        result := result || '## Table: `' || table_rec.table_name || '`\n\n';
        
        -- Colonnes
        result := result || '### Colonnes\n\n';
        result := result || '| Colonne | Type | Nullable | Default | Contraintes |\n';
        result := result || '|---------|------|----------|---------|-------------|\n';
        
        FOR col_rec IN
            SELECT 
                c.column_name,
                c.data_type,
                c.character_maximum_length,
                c.numeric_precision,
                c.numeric_scale,
                c.is_nullable,
                c.column_default,
                CASE WHEN pk.column_name IS NOT NULL THEN 'PRIMARY KEY' ELSE '' END as is_pk
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT ku.table_name, ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku 
                    ON tc.constraint_name = ku.constraint_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = 'public'
                  AND tc.table_name = table_rec.table_name
            ) pk ON c.column_name = pk.column_name
            WHERE c.table_schema = 'public'
              AND c.table_name = table_rec.table_name
            ORDER BY c.ordinal_position
        LOOP
            result := result || '| ' || col_rec.column_name || ' | ';
            
            -- Type
            result := result || col_rec.data_type;
            IF col_rec.character_maximum_length IS NOT NULL THEN
                result := result || '(' || col_rec.character_maximum_length || ')';
            ELSIF col_rec.numeric_precision IS NOT NULL THEN
                result := result || '(' || col_rec.numeric_precision;
                IF col_rec.numeric_scale IS NOT NULL THEN
                    result := result || ',' || col_rec.numeric_scale;
                END IF;
                result := result || ')';
            END IF;
            result := result || ' | ';
            
            -- Nullable
            result := result || CASE WHEN col_rec.is_nullable = 'YES' THEN '✓' ELSE '✗' END || ' | ';
            
            -- Default
            result := result || COALESCE(col_rec.column_default, '-') || ' | ';
            
            -- Constraints
            result := result || COALESCE(col_rec.is_pk, '') || ' |\n';
        END LOOP;
        
        result := result || E'\n';
        
        -- Foreign Keys
        IF EXISTS (
            SELECT 1 FROM information_schema.table_constraints tc
            WHERE tc.table_schema = 'public'
              AND tc.table_name = table_rec.table_name
              AND tc.constraint_type = 'FOREIGN KEY'
        ) THEN
            result := result || '### Clés Étrangères\n\n';
            result := result || '| Colonne | Table Référencée | Colonne Référencée |\n';
            result := result || '|---------|------------------|-------------------|\n';
            
            FOR fk_rec IN
                SELECT
                    ku.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                    ON tc.constraint_name = ku.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.table_schema = 'public'
                  AND tc.table_name = table_rec.table_name
                  AND tc.constraint_type = 'FOREIGN KEY'
            LOOP
                result := result || '| ' || fk_rec.column_name || ' | ';
                result := result || '`' || fk_rec.foreign_table_name || '` | ';
                result := result || '`' || fk_rec.foreign_column_name || '` |\n';
            END LOOP;
            
            result := result || E'\n';
        END IF;
        
        -- Indexes
        IF EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = table_rec.table_name
        ) THEN
            result := result || '### Indexes\n\n';
            result := result || '| Nom | Définition |\n';
            result := result || '|-----|------------|\n';
            
            FOR idx_rec IN
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = table_rec.table_name
                ORDER BY indexname
            LOOP
                result := result || '| `' || idx_rec.indexname || '` | ';
                result := result || '`' || idx_rec.indexdef || '` |\n';
            END LOOP;
            
            result := result || E'\n';
        END IF;
        
        result := result || '---\n\n';
    END LOOP;
    
    -- Output result
    RAISE NOTICE '%', result;
    
    -- Also return as a result set
    CREATE TEMP TABLE schema_markdown (content TEXT);
    INSERT INTO schema_markdown VALUES (result);
END $$;

SELECT content FROM schema_markdown;
