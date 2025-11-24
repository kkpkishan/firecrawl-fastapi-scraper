-- Migration: Add Bedrock LLM extraction fields to crawl_results table
-- Date: 2025-11-22
-- Description: Adds columns for storing raw LLM output, normalized data, and extraction method

-- Add raw_llm_output column for storing unprocessed LLM JSON response
ALTER TABLE crawl_results
ADD COLUMN IF NOT EXISTS raw_llm_output TEXT;

-- Add normalized_data column for storing cleaned and validated JSON data
ALTER TABLE crawl_results
ADD COLUMN IF NOT EXISTS normalized_data TEXT;

-- Add extraction_method column to track which extraction method was used
ALTER TABLE crawl_results
ADD COLUMN IF NOT EXISTS extraction_method VARCHAR(20) DEFAULT 'bedrock';

-- Add index on extraction_method for efficient filtering
CREATE INDEX IF NOT EXISTS idx_crawl_results_extraction_method 
ON crawl_results(extraction_method);

-- Add column comments for documentation
COMMENT ON COLUMN crawl_results.raw_llm_output IS 
'Raw JSON output from LLM before normalization';

COMMENT ON COLUMN crawl_results.normalized_data IS 
'Normalized JSON data matching schema after validation and cleaning';

COMMENT ON COLUMN crawl_results.extraction_method IS 
'Method used for extraction: bedrock (LLM), regex (pattern matching), or keyword (simple search)';

-- Verify migration
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'crawl_results'
AND column_name IN ('raw_llm_output', 'normalized_data', 'extraction_method')
ORDER BY column_name;
