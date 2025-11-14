"""
Database Models for Web Scraping Backend

Defines SQLAlchemy ORM models for crawl jobs and results.
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, BigInteger, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import uuid

# Create base class for declarative models
Base = declarative_base()


class CrawlJob(Base):
    """
    Model for tracking crawl jobs.
    
    Stores metadata about each crawl request including the URL, keyword,
    status, and timing information.
    """
    __tablename__ = 'crawl_jobs'
    
    # Primary key - UUID for better distribution and security
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique identifier for the crawl job"
    )
    
    # Input parameters
    input_url = Column(
        Text,
        nullable=False,
        comment="The base URL that was crawled"
    )
    
    keyword = Column(
        Text,
        nullable=False,
        comment="The search keyword to find in crawled content"
    )
    
    # Status tracking
    status = Column(
        String(20),
        nullable=False,
        default='pending',
        comment="Current status of the crawl job"
    )
    
    # Firecrawl integration
    firecrawl_job_id = Column(
        Text,
        nullable=True,
        comment="The job ID returned by Firecrawl for tracking"
    )
    
    # Timestamps
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="When the job was created"
    )
    
    completed_at = Column(
        DateTime,
        nullable=True,
        comment="When the job completed (success or failure)"
    )
    
    # Error tracking
    error = Column(
        Text,
        nullable=True,
        comment="Error message if the job failed"
    )
    
    # Relationship to results
    results = relationship(
        "CrawlResult",
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    # Add check constraint for valid status values
    __table_args__ = (
        CheckConstraint(
            status.in_(['pending', 'in_progress', 'completed', 'failed']),
            name='valid_status'
        ),
    )
    
    def __repr__(self):
        return f"<CrawlJob(id={self.id}, url={self.input_url}, status={self.status})>"
    
    def to_dict(self):
        """Convert model to dictionary for JSON serialization"""
        return {
            'id': str(self.id),
            'input_url': self.input_url,
            'keyword': self.keyword,
            'status': self.status,
            'firecrawl_job_id': self.firecrawl_job_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error': self.error
        }


class CrawlResult(Base):
    """
    Model for storing crawl results.
    
    Stores individual pages that contain the search keyword,
    including the page URL, title, and content snippet.
    """
    __tablename__ = 'crawl_results'
    
    # Primary key - auto-incrementing integer
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="Unique identifier for the result"
    )
    
    # Foreign key to crawl job
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey('crawl_jobs.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment="Reference to the parent crawl job"
    )
    
    # Page information
    page_url = Column(
        Text,
        nullable=False,
        comment="URL of the page where keyword was found"
    )
    
    page_title = Column(
        Text,
        nullable=True,
        comment="Title of the page (from metadata)"
    )
    
    # Content
    content_snippet = Column(
        Text,
        nullable=False,
        comment="Content snippet or full markdown containing the keyword"
    )
    
    # Timestamp
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="When this result was stored"
    )
    
    # Relationship to job
    job = relationship(
        "CrawlJob",
        back_populates="results"
    )
    
    def __repr__(self):
        return f"<CrawlResult(id={self.id}, job_id={self.job_id}, page_url={self.page_url})>"
    
    def to_dict(self):
        """Convert model to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'job_id': str(self.job_id),
            'page_url': self.page_url,
            'page_title': self.page_title,
            'content_snippet': self.content_snippet,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
