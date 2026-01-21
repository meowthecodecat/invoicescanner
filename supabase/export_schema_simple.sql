-- Version simplifiée pour obtenir rapidement la structure des tables
-- À exécuter dans l'éditeur SQL de Supabase

SELECT 
  '## Table: ' || t.table_name || E'\n\n' ||
  '| Colonne | Type | Nullable | Default | Description |\n' ||
  '|---------|------|----------|---------|-------------|\n' ||
  string_agg(
    '| ' || c.column_name || ' | ' || 
    c.data_type || 
    COALESCE('(' || c.character_maximum_length::text || ')', '') || ' | ' ||
    CASE WHEN c.is_nullable = 'YES' THEN 'Oui' ELSE 'Non' END || ' | ' ||
    COALESCE(c.column_default, '-') || ' | ' ||
    COALESCE(col_description((t.table_schema||'.'||t.table_name)::regclass::oid, c.ordinal_position), '-') || ' |',
    E'\n'
    ORDER BY c.ordinal_position
  ) || E'\n\n'
FROM information_schema.tables t
JOIN information_schema.columns c 
  ON t.table_name = c.table_name 
  AND t.table_schema = c.table_schema
WHERE t.table_schema = 'public'
  AND t.table_type = 'BASE TABLE'
  AND t.table_name NOT LIKE 'pg_%'
GROUP BY t.table_name
ORDER BY t.table_name;
