-- Requête SQL pour exporter la structure des tables en format Markdown
-- À exécuter dans l'éditeur SQL de Supabase

WITH table_info AS (
  SELECT 
    t.table_name,
    c.column_name,
    c.data_type,
    c.character_maximum_length,
    c.is_nullable,
    c.column_default,
    CASE 
      WHEN pk.column_name IS NOT NULL THEN 'PRIMARY KEY'
      WHEN fk.column_name IS NOT NULL THEN 'FOREIGN KEY → ' || fk.foreign_table_name || '(' || fk.foreign_column_name || ')'
      ELSE ''
    END as constraints,
    c.ordinal_position
  FROM information_schema.tables t
  JOIN information_schema.columns c ON t.table_name = c.table_name 
    AND t.table_schema = c.table_schema
  LEFT JOIN (
    SELECT ku.table_name, ku.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage ku 
      ON tc.constraint_name = ku.constraint_name
    WHERE tc.constraint_type = 'PRIMARY KEY'
      AND tc.table_schema = 'public'
  ) pk ON t.table_name = pk.table_name AND c.column_name = pk.column_name
  LEFT JOIN (
    SELECT 
      ku.table_name,
      ku.column_name,
      ccu.table_name AS foreign_table_name,
      ccu.column_name AS foreign_column_name
    FROM information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS ku
      ON tc.constraint_name = ku.constraint_name
    JOIN information_schema.constraint_column_usage AS ccu
      ON ccu.constraint_name = tc.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_schema = 'public'
  ) fk ON t.table_name = fk.table_name AND c.column_name = fk.column_name
  WHERE t.table_schema = 'public'
    AND t.table_type = 'BASE TABLE'
    AND t.table_name NOT LIKE 'pg_%'
    AND t.table_name NOT LIKE '_prisma%'
  ORDER BY t.table_name, c.ordinal_position
),
index_info AS (
  SELECT 
    tablename as table_name,
    indexname as index_name,
    indexdef as index_definition
  FROM pg_indexes
  WHERE schemaname = 'public'
),
constraint_info AS (
  SELECT
    tc.table_name,
    tc.constraint_name,
    tc.constraint_type,
    CASE 
      WHEN tc.constraint_type = 'UNIQUE' THEN
        string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position)
      WHEN tc.constraint_type = 'CHECK' THEN
        cc.check_clause
      ELSE ''
    END as constraint_details
  FROM information_schema.table_constraints tc
  LEFT JOIN information_schema.key_column_usage kcu 
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
  LEFT JOIN information_schema.check_constraints cc
    ON tc.constraint_name = cc.constraint_name
    AND tc.table_schema = cc.table_schema
  WHERE tc.table_schema = 'public'
    AND tc.constraint_type IN ('UNIQUE', 'CHECK')
  GROUP BY tc.table_name, tc.constraint_name, tc.constraint_type, cc.check_clause
)
SELECT 
  '## Structure des Tables\n\n' ||
  string_agg(
    '### Table: `' || table_name || '`\n\n' ||
    '| Colonne | Type | Nullable | Default | Contraintes |\n' ||
    '|---------|------|----------|---------|-------------|\n' ||
    string_agg(
      '| ' || column_name || ' | ' || 
      COALESCE(data_type, '') || 
      CASE 
        WHEN character_maximum_length IS NOT NULL 
        THEN '(' || character_maximum_length || ')'
        ELSE ''
      END || ' | ' ||
      CASE WHEN is_nullable = 'YES' THEN '✓' ELSE '✗' END || ' | ' ||
      COALESCE(column_default, '') || ' | ' ||
      COALESCE(constraints, '') || ' |',
      E'\n'
      ORDER BY ordinal_position
    ) ||
    '\n\n',
    E'\n---\n\n'
    ORDER BY table_name
  ) ||
  '\n## Indexes\n\n' ||
  COALESCE(
    (SELECT string_agg(
      '- **' || table_name || '**: `' || index_name || '`\n  - ' || index_definition,
      E'\n\n'
      ORDER BY table_name, index_name
    )
    FROM index_info),
    'Aucun index personnalisé'
  ) ||
  '\n\n## Contraintes\n\n' ||
  COALESCE(
    (SELECT string_agg(
      '- **' || table_name || '**: ' || constraint_type || 
      CASE 
        WHEN constraint_details != '' THEN ' (' || constraint_details || ')'
        ELSE ''
      END,
      E'\n'
      ORDER BY table_name, constraint_type
    )
    FROM constraint_info),
    'Aucune contrainte personnalisée'
  ) as markdown_output
FROM (
  SELECT DISTINCT table_name FROM table_info
) tables;
