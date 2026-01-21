-- COMMANDE SIMPLE POUR EXPORTER LA STRUCTURE EN MARKDOWN
-- Copiez-collez cette requête dans Supabase SQL Editor et exécutez-la

SELECT 
  '## Table: `' || table_name || '`' || E'\n\n' ||
  '| Colonne | Type | Nullable | Default |' || E'\n' ||
  '|---------|------|----------|---------|' || E'\n' ||
  string_agg(
    '| `' || column_name || '` | ' || 
    data_type || 
    CASE 
      WHEN character_maximum_length IS NOT NULL 
      THEN '(' || character_maximum_length || ')'
      WHEN numeric_precision IS NOT NULL 
      THEN '(' || numeric_precision || 
           CASE WHEN numeric_scale > 0 THEN ',' || numeric_scale ELSE '' END || ')'
      ELSE ''
    END || 
    ' | ' || 
    CASE WHEN is_nullable = 'YES' THEN '✓' ELSE '✗' END || 
    ' | ' || 
    COALESCE(column_default, '-') || 
    ' |',
    E'\n'
    ORDER BY ordinal_position
  ) || E'\n\n' as markdown
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN (
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
      AND table_type = 'BASE TABLE'
  )
GROUP BY table_name
ORDER BY table_name;
