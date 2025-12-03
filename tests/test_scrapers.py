"""
Tests for Council News Bot scrapers.
"""

import pytest
from core.scrapers import BaseScraper, CardScraper, NewsArticle
from datetime import datetime


class TestNewsArticle:
    """Tests for NewsArticle dataclass."""
    
    def test_create_article(self):
        """Test creating a news article."""
        article = NewsArticle(
            council_id='test-council',
            council_name='Test Council',
            title='Test Article',
            url='https://example.com/news/test'
        )
        
        assert article.council_id == 'test-council'
        assert article.council_name == 'Test Council'
        assert article.title == 'Test Article'
        assert article.url == 'https://example.com/news/test'
    
    def test_unique_id(self):
        """Test unique ID generation."""
        article = NewsArticle(
            council_id='test',
            council_name='Test',
            title='Test',
            url='https://example.com/unique'
        )
        
        assert article.unique_id == 'https://example.com/unique'
    
    def test_to_dict(self):
        """Test dictionary serialization."""
        article = NewsArticle(
            council_id='test',
            council_name='Test Council',
            title='Test Article',
            url='https://example.com/test',
            date=datetime(2025, 11, 28),
            excerpt='Test excerpt'
        )
        
        d = article.to_dict()
        
        assert d['council_id'] == 'test'
        assert d['title'] == 'Test Article'
        assert d['date'] == '2025-11-28T00:00:00'
        assert d['excerpt'] == 'Test excerpt'


class TestBaseScraper:
    """Tests for BaseScraper functionality."""
    
    def test_make_absolute_url_already_absolute(self):
        """Test URL that is already absolute."""
        scraper = CardScraper(
            council_id='test',
            council_name='Test',
            news_url='https://example.com/news'
        )
        
        url = scraper.make_absolute_url('https://other.com/article')
        assert url == 'https://other.com/article'
    
    def test_make_absolute_url_relative(self):
        """Test converting relative URL to absolute."""
        scraper = CardScraper(
            council_id='test',
            council_name='Test',
            news_url='https://example.com/news'
        )
        
        url = scraper.make_absolute_url('/article/test')
        assert url == 'https://example.com/article/test'
    
    def test_parse_date_simple(self):
        """Test parsing simple date format."""
        scraper = CardScraper(
            council_id='test',
            council_name='Test',
            news_url='https://example.com'
        )
        
        date = scraper.parse_date('28 Nov 2025')
        assert date is not None
        assert date.day == 28
        assert date.month == 11
        assert date.year == 2025
    
    def test_parse_date_with_prefix(self):
        """Test parsing date with Published prefix."""
        scraper = CardScraper(
            council_id='test',
            council_name='Test',
            news_url='https://example.com'
        )
        
        date = scraper.parse_date('Published 28 Nov 2025')
        assert date is not None
        assert date.day == 28
    
    def test_parse_date_with_weekday(self):
        """Test parsing date with weekday."""
        scraper = CardScraper(
            council_id='test',
            council_name='Test',
            news_url='https://example.com'
        )
        
        date = scraper.parse_date('Thu 28 Nov 2025')
        assert date is not None
        assert date.day == 28
    
    def test_parse_date_invalid(self):
        """Test parsing invalid date returns None."""
        scraper = CardScraper(
            council_id='test',
            council_name='Test',
            news_url='https://example.com'
        )
        
        date = scraper.parse_date('not a date')
        assert date is None
    
    def test_clean_text(self):
        """Test text cleaning."""
        scraper = CardScraper(
            council_id='test',
            council_name='Test',
            news_url='https://example.com'
        )
        
        text = scraper.clean_text('  Multiple   spaces   and\nnewlines  ')
        assert text == 'Multiple spaces and newlines'
    
    def test_create_article(self):
        """Test article creation helper."""
        scraper = CardScraper(
            council_id='test-council',
            council_name='Test Council',
            news_url='https://example.com/news'
        )
        
        article = scraper.create_article(
            title='  Test Article  ',
            url='/news/test',
            excerpt='Test excerpt'
        )
        
        assert article.council_id == 'test-council'
        assert article.council_name == 'Test Council'
        assert article.title == 'Test Article'
        assert article.url == 'https://example.com/news/test'
        assert article.excerpt == 'Test excerpt'


class TestCardScraper:
    """Tests for CardScraper."""
    
    def test_parse_article_basic_html(self):
        """Test parsing article from basic HTML."""
        scraper = CardScraper(
            council_id='test',
            council_name='Test Council',
            news_url='https://example.com/news'
        )
        
        html = '''
        <article class="news-item">
            <h3><a href="/news/test-article">Test Article Title</a></h3>
            <span class="date">28 Nov 2025</span>
            <p class="excerpt">This is a test excerpt.</p>
        </article>
        '''
        
        soup = scraper.parse_html(html)
        item = soup.find('article')
        article = scraper._parse_article(item)
        
        assert article is not None
        assert article.title == 'Test Article Title'
        assert article.url == 'https://example.com/news/test-article'
        assert article.date.day == 28
        assert article.excerpt == 'This is a test excerpt.'
    
    def test_parse_article_no_title_returns_none(self):
        """Test that missing title returns None."""
        scraper = CardScraper(
            council_id='test',
            council_name='Test',
            news_url='https://example.com'
        )
        
        html = '<article><p>No title here</p></article>'
        soup = scraper.parse_html(html)
        item = soup.find('article')
        article = scraper._parse_article(item)
        
        assert article is None
