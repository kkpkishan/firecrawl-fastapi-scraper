"""
Dynamic Regex-Based Data Extraction Module

This module provides flexible regex-based extraction that reads patterns
from environment variables, allowing users to customize extraction logic
without modifying code.
"""
import re
import logging
from typing import List, Dict, Optional, Tuple
from config import settings

logger = logging.getLogger(__name__)


class RegexExtractor:
    """
    Dynamic regex extractor that uses patterns from environment configuration.
    
    Features:
    - Reads regex patterns from .env file
    - Supports multiple patterns simultaneously
    - Extracts context around matches
    - No hardcoded patterns - fully configurable
    """
    
    def __init__(self):
        """Initialize extractor with patterns from settings."""
        self.patterns = settings.get_all_regex_patterns()
        self.context_chars = settings.regex_context_chars
        self.enabled = settings.enable_regex_extraction
        
        if self.enabled:
            logger.info(f"RegexExtractor initialized with {len(self.patterns)} patterns")
            for name, pattern in self.patterns.items():
                logger.debug(f"  Pattern '{name}': {pattern[:50]}...")
        else:
            logger.info("RegexExtractor disabled in configuration")
    
    def extract_patterns(self, text: str) -> List[Dict[str, any]]:
        """
        Extract all configured patterns from text.
        
        Args:
            text: Text content to extract from
            
        Returns:
            List of dictionaries with pattern matches:
            {
                'pattern_name': str,
                'pattern_type': str,
                'value': str,
                'context': str,
                'position': int,
                'groups': tuple (if pattern has capture groups)
            }
        """
        if not self.enabled or not text:
            return []
        
        all_matches = []
        
        for pattern_name, pattern_regex in self.patterns.items():
            try:
                matches = self._extract_single_pattern(
                    text, 
                    pattern_name, 
                    pattern_regex
                )
                all_matches.extend(matches)
            except re.error as e:
                logger.error(f"Invalid regex pattern '{pattern_name}': {e}")
                continue
            except Exception as e:
                logger.error(f"Error extracting pattern '{pattern_name}': {e}")
                continue
        
        # Sort by position and remove duplicates
        all_matches.sort(key=lambda x: x['position'])
        unique_matches = self._remove_duplicates(all_matches)
        
        logger.debug(f"Extracted {len(unique_matches)} unique matches from {len(all_matches)} total")
        
        return unique_matches
    
    def _extract_single_pattern(
        self, 
        text: str, 
        pattern_name: str, 
        pattern_regex: str
    ) -> List[Dict[str, any]]:
        """
        Extract a single pattern from text.
        
        Args:
            text: Text to search
            pattern_name: Name of the pattern
            pattern_regex: Regex pattern string
            
        Returns:
            List of match dictionaries
        """
        matches = []
        
        # Compile pattern with case-insensitive flag
        try:
            compiled_pattern = re.compile(pattern_regex, re.IGNORECASE)
        except re.error as e:
            logger.error(f"Failed to compile pattern '{pattern_name}': {e}")
            return matches
        
        # Find all matches
        for match in compiled_pattern.finditer(text):
            # Extract matched value
            if match.groups():
                # If pattern has capture groups, use first group
                value = match.group(1) if len(match.groups()) >= 1 else match.group(0)
                groups = match.groups()
            else:
                # No capture groups, use full match
                value = match.group(0)
                groups = ()
            
            # Extract context around match
            context = self._extract_context(text, match.start(), match.end())
            
            matches.append({
                'pattern_name': pattern_name,
                'pattern_type': self._categorize_pattern(pattern_name),
                'value': value.strip(),
                'context': context,
                'position': match.start(),
                'groups': groups
            })
        
        return matches
    
    def _extract_context(self, text: str, start: int, end: int) -> str:
        """
        Extract context around a match.
        
        Args:
            text: Full text
            start: Match start position
            end: Match end position
            
        Returns:
            Context string
        """
        context_start = max(0, start - self.context_chars)
        context_end = min(len(text), end + self.context_chars)
        
        context = text[context_start:context_end].strip()
        
        # Add ellipsis if truncated
        if context_start > 0:
            context = "..." + context
        if context_end < len(text):
            context = context + "..."
        
        return context
    
    def _categorize_pattern(self, pattern_name: str) -> str:
        """
        Categorize pattern based on its name.
        
        Args:
            pattern_name: Name of the pattern
            
        Returns:
            Category string
        """
        name_lower = pattern_name.lower()
        
        if 'date' in name_lower:
            return 'date'
        elif 'exam' in name_lower or 'test' in name_lower:
            return 'exam'
        elif 'post' in name_lower or 'position' in name_lower:
            return 'post'
        elif 'advt' in name_lower or 'notification' in name_lower:
            return 'advertisement'
        elif 'keyvalue' in name_lower or 'key' in name_lower:
            return 'keyvalue'
        else:
            return 'general'
    
    def _remove_duplicates(self, matches: List[Dict[str, any]]) -> List[Dict[str, any]]:
        """
        Remove duplicate matches based on value and position proximity.
        
        Args:
            matches: List of match dictionaries
            
        Returns:
            List with duplicates removed
        """
        if not matches:
            return []
        
        unique = []
        seen_values = set()
        
        for match in matches:
            value = match['value']
            
            # Check if we've seen this exact value
            if value in seen_values:
                # Check if it's at a different position (allow same value at different locations)
                is_duplicate = False
                for existing in unique:
                    if existing['value'] == value:
                        # If positions are close (within 50 chars), consider it duplicate
                        if abs(existing['position'] - match['position']) < 50:
                            is_duplicate = True
                            break
                
                if is_duplicate:
                    continue
            
            seen_values.add(value)
            unique.append(match)
        
        return unique
    
    def extract_key_value_pairs(self, matches: List[Dict[str, any]]) -> List[Dict[str, str]]:
        """
        Convert matches to key-value pairs for structured output.
        
        Args:
            matches: List of match dictionaries from extract_patterns()
            
        Returns:
            List of dictionaries with 'key' and 'value' fields
        """
        key_value_pairs = []
        
        for match in matches:
            pattern_name = match['pattern_name']
            pattern_type = match['pattern_type']
            value = match['value']
            context = match['context']
            
            # For keyvalue patterns, try to extract both key and value
            if pattern_type == 'keyvalue' and match.get('groups'):
                groups = match['groups']
                if len(groups) >= 2:
                    key = groups[0].strip()
                    val = groups[1].strip()
                    key_value_pairs.append({
                        'key': key,
                        'value': val,
                        'pattern_type': pattern_type,
                        'context': context[:150]
                    })
                    continue
            
            # For other patterns, create key from pattern name and value
            key = self._generate_key_from_pattern(pattern_name, pattern_type, value)
            
            key_value_pairs.append({
                'key': key,
                'value': value,
                'pattern_type': pattern_type,
                'context': context[:150]
            })
        
        return key_value_pairs
    
    def _generate_key_from_pattern(
        self, 
        pattern_name: str, 
        pattern_type: str, 
        value: str
    ) -> str:
        """
        Generate a descriptive key from pattern information.
        
        Args:
            pattern_name: Name of the pattern
            pattern_type: Type/category of pattern
            value: Matched value
            
        Returns:
            Generated key string
        """
        # Try to extract a meaningful key from context or pattern name
        if pattern_type == 'date':
            return "Date"
        elif pattern_type == 'exam':
            return "Exam"
        elif pattern_type == 'post':
            return "Post"
        elif pattern_type == 'advertisement':
            return "Advertisement Number"
        else:
            # Use pattern name as key
            return pattern_name.replace('_', ' ').title()
    
    def extract_structured_data(
        self, 
        text: str, 
        output_format: str = 'keyvalue'
    ) -> Dict[str, any]:
        """
        Extract structured data from text using configured patterns.
        
        Args:
            text: Text to extract from
            output_format: Output format ('keyvalue', 'raw', 'grouped')
            
        Returns:
            Dictionary with extracted data in requested format
        """
        if not self.enabled:
            return {
                'enabled': False,
                'message': 'Regex extraction is disabled'
            }
        
        # Extract all patterns
        matches = self.extract_patterns(text)
        
        if output_format == 'raw':
            return {
                'enabled': True,
                'total_matches': len(matches),
                'matches': matches
            }
        
        elif output_format == 'keyvalue':
            key_value_pairs = self.extract_key_value_pairs(matches)
            return {
                'enabled': True,
                'total_matches': len(matches),
                'data': key_value_pairs
            }
        
        elif output_format == 'grouped':
            # Group matches by pattern type
            grouped = {}
            for match in matches:
                pattern_type = match['pattern_type']
                if pattern_type not in grouped:
                    grouped[pattern_type] = []
                grouped[pattern_type].append({
                    'value': match['value'],
                    'context': match['context'][:100]
                })
            
            return {
                'enabled': True,
                'total_matches': len(matches),
                'grouped_data': grouped
            }
        
        else:
            return {
                'enabled': True,
                'error': f'Unknown output format: {output_format}'
            }


# Global extractor instance
_extractor_instance = None


def get_extractor() -> RegexExtractor:
    """
    Get global RegexExtractor instance (singleton pattern).
    
    Returns:
        RegexExtractor instance
    """
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = RegexExtractor()
    return _extractor_instance


def extract_with_regex(text: str, output_format: str = 'keyvalue') -> Dict[str, any]:
    """
    Convenience function to extract data using regex patterns.
    
    Args:
        text: Text to extract from
        output_format: Output format ('keyvalue', 'raw', 'grouped')
        
    Returns:
        Extracted data dictionary
    """
    extractor = get_extractor()
    return extractor.extract_structured_data(text, output_format)
