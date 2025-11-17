"""
Nested URL Scraping Module

Handles automatic nested scraping of URLs found in regex patterns.
Supports both regular web pages and document extraction.
"""
import logging
import re
from typing import List, Set, Dict, Optional
from urllib.parse import urlparse, urljoin
from sqlalchemy.ext.asyncio import AsyncSession

from document_extractor import get_document_extractor
from regex_extractor import get_extractor

logger = logging.getLogger(__name__)


class NestedScraper:
    """
    Manages nested scraping of URLs found in content.
    
    Features:
    - Extracts URLs from regex pattern matches
    - Identifies document URLs (.pdf, .xlsx, etc.)
    - Prevents duplicate scraping
    - Respects depth limits
    """
    
    def __init__(self):
        """Initialize nested scraper."""
        self.document_extractor = get_document_extractor()
        self.regex_extractor = get_extractor()
        self.scraped_urls = set()  # Track scraped URLs to avoid duplicates
        logger.info("NestedScraper initialized")
    
    def extract_urls_from_regex_matches(
        self, 
        matches: List[Dict[str, any]], 
        base_url: str
    ) -> Dict[str, List[str]]:
        """
        Extract URLs from regex pattern matches.
        
        Categorizes URLs into:
        - web_pages: Regular HTML pages
        - documents: PDF, Excel, Word, etc.
        
        Args:
            matches: List of regex matches from regex_extractor
            base_url: Base URL for resolving relative URLs
            
        Returns:
            Dictionary with 'web_pages' and 'documents' lists
        """
        web_pages = set()
        documents = set()
        
        base_parsed = urlparse(base_url)
        base_domain = base_parsed.netloc
        
        for match in matches:
            value = match.get('value', '')
            context = match.get('context', '')
            
            # Look for URLs in both value and context
            urls_found = self._extract_urls_from_text(value + " " + context)
            
            for url in urls_found:
                # Resolve relative URLs
                if not url.startswith('http'):
                    url = urljoin(base_url, url)
                
                # Parse URL
                parsed = urlparse(url)
                
                # Only process URLs from same domain (avoid external links)
                if parsed.netloc != base_domain:
                    continue
                
                # Skip if already scraped
                if url in self.scraped_urls:
                    continue
                
                # Categorize URL
                if self.document_extractor.is_document_url(url):
                    documents.add(url)
                else:
                    web_pages.add(url)
        
        logger.info(f"Extracted {len(web_pages)} web pages and {len(documents)} documents from regex matches")
        
        return {
            'web_pages': list(web_pages),
            'documents': list(documents)
        }
    
    def _extract_urls_from_text(self, text: str) -> List[str]:
        """
        Extract URLs from text using multiple patterns.
        
        Args:
            text: Text to extract URLs from
            
        Returns:
            List of URLs found
        """
        urls = set()
        
        # Pattern 1: Markdown links [text](url)
        markdown_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        for match in re.finditer(markdown_pattern, text):
            url = match.group(2)
            if not url.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                urls.add(url)
        
        # Pattern 2: Direct HTTP(S) URLs
        url_pattern = r'https?://[^\s\)\]\"\'\<\>]+'
        for match in re.finditer(url_pattern, text):
            url = match.group(0)
            urls.add(url)
        
        # Pattern 3: Relative URLs starting with /
        relative_pattern = r'(?:href|src)=["\']?(/[^\s\"\'\>]+)["\']?'
        for match in re.finditer(relative_pattern, text, re.IGNORECASE):
            url = match.group(1)
            urls.add(url)
        
        return list(urls)
    
    def mark_url_scraped(self, url: str):
        """
        Mark URL as scraped to avoid duplicates.
        
        Args:
            url: URL to mark
        """
        self.scraped_urls.add(url)
    
    def is_url_scraped(self, url: str) -> bool:
        """
        Check if URL has been scraped.
        
        Args:
            url: URL to check
            
        Returns:
            True if already scraped, False otherwise
        """
        return url in self.scraped_urls
    
    async def process_document_url(
        self,
        db: AsyncSession,
        job_id: str,
        document_url: str,
        keyword: str,
        parent_page_url: str
    ) -> bool:
        """
        Process a document URL - download and extract content.
        
        Args:
            db: Database session
            job_id: Current job ID
            document_url: URL of document to process
            keyword: Keyword to search for
            parent_page_url: URL of page that linked to this document
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Processing document: {document_url}")
            
            # Extract text from document
            extracted_text, error = await self.document_extractor.extract_text(document_url)
            
            if not extracted_text:
                logger.error(f"Failed to extract document: {error}")
                return False
            
            # Mark as scraped
            self.mark_url_scraped(document_url)
            
            # Search for keyword in extracted text
            if keyword.lower() in extracted_text.lower():
                logger.info(f"✓ Keyword '{keyword}' found in document: {document_url}")
                
                # Extract structured data using regex patterns
                from regex_extractor import extract_with_regex
                extracted_data = extract_with_regex(extracted_text, output_format='keyvalue')
                
                # Store results
                from database import create_result
                
                if extracted_data.get('enabled') and extracted_data.get('data'):
                    # Store extracted patterns
                    for item in extracted_data['data']:
                        data_key = item['key']
                        data_value = item['value']
                        pattern_type = item.get('pattern_type', 'unknown')
                        context = item.get('context', '')
                        
                        content_snippet = f"[DOCUMENT] {document_url}\nKEY: {data_key}\nVALUE: {data_value}\nTYPE: {pattern_type}"
                        if context:
                            content_snippet += f"\nCONTEXT: {context}"
                        
                        await create_result(
                            db,
                            job_id=job_id,
                            page_url=document_url,
                            page_title=f"Document: {document_url.split('/')[-1]}",
                            content_snippet=content_snippet,
                            data_key=data_key,
                            data_value=data_value
                        )
                    
                    logger.info(f"  → Extracted {len(extracted_data['data'])} patterns from document")
                else:
                    # No patterns matched, store keyword context
                    data_key = f"Document Keyword Match: {keyword}"
                    # Get context around keyword
                    keyword_pos = extracted_text.lower().find(keyword.lower())
                    start = max(0, keyword_pos - 300)
                    end = min(len(extracted_text), keyword_pos + len(keyword) + 300)
                    data_value = extracted_text[start:end]
                    
                    content_snippet = f"[DOCUMENT] {document_url}\nKEY: {data_key}\nVALUE: {data_value}"
                    
                    await create_result(
                        db,
                        job_id=job_id,
                        page_url=document_url,
                        page_title=f"Document: {document_url.split('/')[-1]}",
                        content_snippet=content_snippet,
                        data_key=data_key,
                        data_value=data_value
                    )
                
                return True
            else:
                logger.info(f"Keyword '{keyword}' not found in document: {document_url}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing document {document_url}: {e}", exc_info=True)
            return False
    
    def reset_scraped_urls(self):
        """Reset the set of scraped URLs (for new jobs)."""
        self.scraped_urls.clear()
        logger.info("Reset scraped URLs tracker")


# Global nested scraper instance
_nested_scraper_instance = None


def get_nested_scraper() -> NestedScraper:
    """
    Get global NestedScraper instance (singleton).
    
    Returns:
        NestedScraper instance
    """
    global _nested_scraper_instance
    if _nested_scraper_instance is None:
        _nested_scraper_instance = NestedScraper()
    return _nested_scraper_instance
