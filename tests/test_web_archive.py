"""Tests for web archive generation."""

from __future__ import annotations

import hashlib
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from great_work.models import (
    Memory,
    MemoryFact,
    PressRecord,
    PressRelease,
    Scholar,
    ScholarStats,
)
from great_work.state import GameState
from great_work.web_archive import ArchivePage, WebArchive


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        yield Path(f.name)


@pytest.fixture
def state(temp_db):
    """Create a test GameState."""
    return GameState(temp_db, start_year=1850)


@pytest.fixture
def sample_press():
    """Create sample press releases for testing."""
    releases = []

    # Academic bulletin
    releases.append(
        PressRecord(
            timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
            release=PressRelease(
                type="academic_bulletin",
                headline="Academic Bulletin No. 1",
                body="Dr. Smith submits 'Theory of Everything' with high confidence. Counter-claims invited.",
                metadata={"bulletin_number": 1},
            ),
        )
    )

    # Discovery report
    releases.append(
        PressRecord(
            timestamp=datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc),
            release=PressRelease(
                type="discovery_report",
                headline="Discovery Report: Expedition ALPHA (Field Work)",
                body="Outcome: triumph. Roll 90 + 15 = 105. Reputation change: +10. Major breakthrough achieved!",
                metadata={"outcome": "triumph", "expedition_code": "ALPHA"},
            ),
        )
    )

    # Retraction notice
    releases.append(
        PressRecord(
            timestamp=datetime(2024, 1, 3, 9, 15, tzinfo=timezone.utc),
            release=PressRelease(
                type="retraction_notice",
                headline="Retraction Notice: Expedition BETA",
                body="Outcome: disaster. Roll 5 + 0 = 5. Reputation change: -5. Complete failure of methodology.",
                metadata={"outcome": "disaster"},
            ),
        )
    )

    return releases


@pytest.fixture
def sample_scholar():
    """Create a sample scholar for testing."""
    return Scholar(
        id="newton",
        name="Sir Isaac Newton",
        seed=42,
        archetype="Sage",
        disciplines=["Physics", "Mathematics"],
        methods=["Mathematical Proof", "Experimentation"],
        drives=["Truth", "Recognition"],
        virtues=["Brilliant", "Methodical"],
        vices=["Arrogant", "Reclusive"],
        stats=ScholarStats(
            talent=9, reliability=8, integrity=7, theatrics=4, loyalty=8, risk=5
        ),
        politics={"academic": 1, "government": 0, "industry": -1},
        catchphrase="Hypotheses non fingo",
        taboos=["Alchemy"],
        memory=Memory(),
        career={"location": "Cambridge", "patron": "Royal Society"},
    )


class TestWebArchive:
    """Test web archive generation functionality."""

    def test_init(self, state):
        """Test WebArchive initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            archive = WebArchive(state, output_dir)

            assert archive.state == state
            assert archive.output_dir == output_dir
            assert archive.base_url == "/archive"

            # Check directory creation
            assert (output_dir / "press").exists()
            assert (output_dir / "scholars").exists()
            assert (output_dir / "assets").exists()

    def test_generate_permalink(self, state, sample_press):
        """Test permalink generation for press releases."""
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = WebArchive(state, Path(tmpdir))

            # Test permalink generation
            permalink = archive.generate_permalink(sample_press[0])

            # Verify format
            assert permalink.startswith("/archive/press/")
            assert "2024-01-01" in permalink
            assert permalink.endswith(".html")

            # Verify stability (same input produces same output)
            permalink2 = archive.generate_permalink(sample_press[0])
            assert permalink == permalink2

            # Verify uniqueness (different inputs produce different outputs)
            permalink3 = archive.generate_permalink(sample_press[1])
            assert permalink != permalink3

    def test_generate_permalink_with_custom_base_url(self, state, sample_press):
        """Custom base URLs should be respected when generating permalinks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = WebArchive(state, Path(tmpdir), base_url="/gazette/archive/")

            permalink = archive.generate_permalink(sample_press[0])

            assert permalink.startswith("/gazette/archive/press/")
            assert permalink.endswith(".html")

        with tempfile.TemporaryDirectory() as tmpdir:
            archive = WebArchive(
                state, Path(tmpdir), base_url="https://example.com/great-work"
            )
            permalink = archive.generate_permalink(sample_press[0])
            assert permalink.startswith("https://example.com/great-work/press/")

    def test_permalink_stability(self, state):
        """Test that permalinks remain stable over time."""
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = WebArchive(state, Path(tmpdir))

            # Create a press record
            press = PressRecord(
                timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
                release=PressRelease(
                    type="test", headline="Test Headline", body="Test body content."
                ),
            )

            # Generate expected hash
            content = f"{press.timestamp.isoformat()}{press.release.headline}"
            expected_hash = hashlib.md5(content.encode()).hexdigest()[:8]
            expected_permalink = f"/archive/press/2024-01-01-{expected_hash}.html"

            # Verify generated permalink matches expected
            actual_permalink = archive.generate_permalink(press)
            assert actual_permalink == expected_permalink

    def test_generate_press_html(self, state, sample_press):
        """Test HTML generation for individual press releases."""
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = WebArchive(state, Path(tmpdir))

            # Generate HTML for first press release
            html = archive.generate_press_html(sample_press[0], press_id=1)

            # Verify HTML structure
            assert "<!DOCTYPE html>" in html
            assert "Academic Bulletin No. 1" in html
            assert "2024-01-01" in html
            assert "Dr. Smith" in html
            assert "Theory of Everything" in html
            assert "Permalink:" in html
            assert "Press ID:</strong> #1" in html

            # Check for proper escaping with dangerous HTML
            press_with_html = PressRecord(
                timestamp=datetime.now(timezone.utc),
                release=PressRelease(
                    type="test",
                    headline="Dangerous <img src=x onerror=alert(1)> Content",
                    body="Body with <b>HTML</b> tags",
                ),
            )
            html_escaped = archive.generate_press_html(press_with_html, press_id=2)
            # Check that dangerous HTML is escaped
            assert "&lt;img" in html_escaped  # Image tag should be escaped
            assert (
                "<img src=x" not in html_escaped
            )  # Unescaped image tag should not be present
            assert "<b>HTML</b>" not in html_escaped  # Unescaped bold tag
            assert (
                "&lt;b&gt;HTML&lt;/b&gt;" in html_escaped
            )  # Properly escaped bold tag

    def test_generate_index(self, state, sample_press):
        """Test index page generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = WebArchive(state, Path(tmpdir))

            # Save press releases to state
            for press in sample_press:
                state.record_press_release(press)

            # Generate index
            html = archive.generate_index(sample_press)

            # Verify index structure
            assert "<!DOCTYPE html>" in html
            assert "Press Archive" in html
            assert "Browse the complete archive" in html

            # Check all press releases are included
            for press in sample_press:
                assert press.release.headline in html

            # Check search box
            assert 'id="searchInput"' in html
            assert "filterPress()" in html

            # Check filter buttons
            assert "filter-btn" in html
            assert "Academic Bulletins" in html
            assert "Discovery Reports" in html

    def test_pagination(self, state):
        """Test pagination in index pages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = WebArchive(state, Path(tmpdir))

            # Create many press releases
            many_press = []
            for i in range(50):
                # Use a valid date range (spread across months if needed)
                month = (i // 30) + 1
                day = (i % 30) + 1
                many_press.append(
                    PressRecord(
                        timestamp=datetime(
                            2024, month, day, 12, 0, tzinfo=timezone.utc
                        ),
                        release=PressRelease(
                            type="test",
                            headline=f"Press Release {i+1}",
                            body=f"Content for release {i+1}",
                        ),
                    )
                )

            # Generate index with pagination
            html_page1 = archive.generate_index(many_press, page=1, per_page=20)
            html_page2 = archive.generate_index(many_press, page=2, per_page=20)

            # Verify pagination links
            assert "pagination" in html_page1
            assert "Next" in html_page1
            assert "Previous" in html_page2

            # Verify different content on different pages
            assert "Press Release 1" in html_page1
            assert "Press Release 21" in html_page2
            assert "Press Release 21" not in html_page1

    def test_generate_timeline(self, state, sample_press):
        """Test timeline generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = WebArchive(state, Path(tmpdir))

            # Save press releases
            for press in sample_press:
                state.record_press_release(press)

            # Get events
            events = state.export_events()

            # Generate timeline
            html = archive.generate_timeline(events, sample_press)

            # Verify timeline structure
            assert "Game Timeline" in html
            assert "timeline-item" in html

            # Check that releases are included
            for press in sample_press:
                assert press.release.headline in html

    def test_generate_scholar_page(self, state, sample_scholar):
        """Test scholar profile page generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = WebArchive(state, Path(tmpdir))

            # Add some memories to the scholar
            fact = MemoryFact(
                timestamp=datetime.now(timezone.utc),
                type="discovery",
                subject="gravity",
                details={"description": "Discovered gravity", "year": "1687"},
            )
            sample_scholar.memory.record_fact(fact)
            sample_scholar.memory.adjust_feeling("pride", 0.9)
            sample_scholar.memory.add_scar("Betrayed by Hooke")

            # Generate scholar page
            html = archive.generate_scholar_page(sample_scholar)

            # Verify scholar information
            assert "Sir Isaac Newton" in html
            assert "Physics" in html
            assert "Mathematical Proof" in html
            assert "Cambridge" in html

            # Check memories section
            assert "gravity" in html  # Subject from the fact

            # Check feelings section
            assert "pride" in html

            # Check scars section
            assert "Betrayed by Hooke" in html

    def test_generate_scholars_index(self, state):
        """Test scholars index page generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = WebArchive(state, Path(tmpdir))

            # Create multiple scholars
            scholars = [
                Scholar(
                    id=f"scholar{i}",
                    name=f"Scholar {i}",
                    seed=i,
                    archetype="Sage",
                    disciplines=[f"Field {i}"],
                    methods=[f"Method {i}"],
                    drives=["Truth"],
                    virtues=["Brilliant"],
                    vices=["Arrogant"],
                    stats=ScholarStats(
                        talent=7,
                        reliability=7,
                        integrity=7,
                        theatrics=5,
                        loyalty=6,
                        risk=5,
                    ),
                    politics={},
                    catchphrase=f"Phrase {i}",
                    taboos=[],
                    memory=Memory(),
                )
                for i in range(5)
            ]

            # Generate index
            html = archive.generate_scholars_index(scholars)

            # Verify all scholars are included
            assert "Scholar Directory" in html
            for scholar in scholars:
                assert scholar.name in html
                assert scholar.disciplines[0] in html
                assert scholar.methods[0] in html

    def test_export_full_archive(self, state, sample_press, sample_scholar):
        """Test full archive export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            archive = WebArchive(state, output_dir)

            # Add data to state
            for press in sample_press:
                state.record_press_release(press)
            state.save_scholar(sample_scholar)

            # Export full archive
            result_path = archive.export_full_archive()

            # Verify export path
            assert result_path == output_dir

            # Check generated files
            assert (output_dir / "index.html").exists()
            assert (output_dir / "timeline.html").exists()
            assert (output_dir / "scholars.html").exists()
            assert (output_dir / "theories.html").exists()
            assert (output_dir / "expeditions.html").exists()

            # Check individual press releases
            press_files = list((output_dir / "press").glob("*.html"))
            assert len(press_files) == len(sample_press)

            # Check scholar profile
            assert (output_dir / "scholars" / f"{sample_scholar.id}.html").exists()

            # Verify index content
            with open(output_dir / "index.html", "r") as f:
                index_html = f.read()
                for press in sample_press:
                    assert press.release.headline in index_html

    def test_format_body_paragraphs(self, state):
        """Test body text formatting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = WebArchive(state, Path(tmpdir))

            # Test single paragraph
            body1 = "This is a single paragraph."
            formatted1 = archive._format_body_paragraphs(body1)
            assert "<p>This is a single paragraph.</p>" in formatted1

            # Test multiple paragraphs
            body2 = "First paragraph.\n\nSecond paragraph."
            formatted2 = archive._format_body_paragraphs(body2)
            assert "<p>First paragraph.</p>" in formatted2
            assert "<p>Second paragraph.</p>" in formatted2

            # Test line breaks within paragraph
            body3 = "Line one\nLine two"
            formatted3 = archive._format_body_paragraphs(body3)
            assert "Line one<br>Line two" in formatted3

            # Test HTML escaping
            body4 = "Text with <html> & special chars"
            formatted4 = archive._format_body_paragraphs(body4)
            assert "&lt;html&gt;" in formatted4
            assert "&amp;" in formatted4

    def test_responsive_design(self, state):
        """Test that generated HTML includes responsive design elements."""
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = WebArchive(state, Path(tmpdir))

            template = archive.get_base_template()

            # Check viewport meta tag
            assert 'name="viewport"' in template
            assert "width=device-width" in template

            # Check media queries
            assert "@media" in template
            assert "max-width: 768px" in template

            # Check mobile-friendly classes
            assert "container" in template
            assert "flex-wrap" in template

    def test_search_functionality(self, state, sample_press):
        """Test client-side search implementation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = WebArchive(state, Path(tmpdir))

            html = archive.generate_index(sample_press)

            # Check search input
            assert 'id="searchInput"' in html
            assert 'onkeyup="filterPress()"' in html

            # Check search JavaScript
            assert "function filterPress()" in html
            assert "toLowerCase()" in html
            assert "dataset.search" in html

            # Check filter buttons JavaScript
            assert "function filterByType" in html
            assert "dataset.type" in html

    def test_permalink_in_discord_integration(self, state, sample_press):
        """Test that permalinks work with Discord integration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = WebArchive(state, Path(tmpdir))

            # Generate permalink
            permalink = archive.generate_permalink(sample_press[0])

            # Verify permalink format is Discord-friendly
            assert permalink.startswith("/archive/")
            assert " " not in permalink  # No spaces
            assert all(
                c.isalnum() or c in "-/.:" for c in permalink
            )  # URL-safe characters


class TestArchivePage:
    """Test ArchivePage dataclass."""

    def test_archive_page_creation(self):
        """Test creating an ArchivePage instance."""
        page = ArchivePage(
            path=Path("/test/page.html"),
            title="Test Page",
            content="<p>Content</p>",
            permalink="/archive/test.html",
            metadata={"type": "test", "date": "2024-01-01"},
        )

        assert page.path == Path("/test/page.html")
        assert page.title == "Test Page"
        assert page.content == "<p>Content</p>"
        assert page.permalink == "/archive/test.html"
        assert page.metadata["type"] == "test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
