#!/bin/bash

# Export extracted exam data to CSV files

echo "=========================================="
echo "Exporting Exam Data from Database"
echo "=========================================="
echo ""

# Export all exam-related data
echo "Exporting exam dates and details..."
docker exec nuq-postgres psql -U postgres -d postgres -c "
COPY (
    SELECT 
        r.page_url,
        r.page_title,
        r.data_key,
        r.data_value,
        r.created_at,
        j.input_url as original_url,
        j.keyword
    FROM crawl_results r
    JOIN crawl_jobs j ON r.job_id = j.id
    WHERE r.created_at > NOW() - INTERVAL '1 hour'
    AND r.data_key IN ('Date', 'Exam', 'Advertisement Number', 'Post', 'Year Range')
    ORDER BY r.created_at DESC
) TO STDOUT WITH CSV HEADER
" > exam_data_export.csv

echo "✓ Exported to: exam_data_export.csv"
echo ""

# Export summary statistics
echo "Exporting summary statistics..."
docker exec nuq-postgres psql -U postgres -d postgres -c "
COPY (
    SELECT 
        data_key,
        COUNT(*) as count,
        COUNT(DISTINCT page_url) as unique_pages
    FROM crawl_results
    WHERE created_at > NOW() - INTERVAL '1 hour'
    GROUP BY data_key
    ORDER BY count DESC
) TO STDOUT WITH CSV HEADER
" > exam_data_summary.csv

echo "✓ Exported to: exam_data_summary.csv"
echo ""

# Export document extraction results
echo "Exporting document extraction results..."
docker exec nuq-postgres psql -U postgres -d postgres -c "
COPY (
    SELECT 
        r.page_url,
        r.data_key,
        r.data_value,
        r.created_at
    FROM crawl_results r
    WHERE r.created_at > NOW() - INTERVAL '1 hour'
    AND r.page_url LIKE '%.pdf'
    ORDER BY r.created_at DESC
) TO STDOUT WITH CSV HEADER
" > document_extractions.csv

echo "✓ Exported to: document_extractions.csv"
echo ""

# Show file sizes
echo "=========================================="
echo "Export Summary"
echo "=========================================="
echo ""
ls -lh exam_data_export.csv exam_data_summary.csv document_extractions.csv 2>/dev/null || echo "Some files may be empty"
echo ""

# Show preview
echo "=========================================="
echo "Preview: Exam Data (first 10 rows)"
echo "=========================================="
echo ""
head -11 exam_data_export.csv | column -t -s ','
echo ""

echo "=========================================="
echo "Preview: Summary Statistics"
echo "=========================================="
echo ""
cat exam_data_summary.csv | column -t -s ','
echo ""

# Count records
EXAM_COUNT=$(wc -l < exam_data_export.csv)
DOC_COUNT=$(wc -l < document_extractions.csv)

echo "=========================================="
echo "Total Records"
echo "=========================================="
echo "Exam data records: $((EXAM_COUNT - 1))"
echo "Document extractions: $((DOC_COUNT - 1))"
echo ""
echo "Files ready for analysis!"
echo "=========================================="
