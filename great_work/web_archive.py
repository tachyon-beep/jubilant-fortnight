"""Web archive generation for game history with permalinks and static HTML."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Dict, List

from .models import Event, PressRecord, Scholar
from .state import GameState


@dataclass
class ArchivePage:
    """Represents a single page in the web archive."""

    path: Path
    title: str
    content: str
    permalink: str
    metadata: Dict[str, str]


class WebArchive:
    """Generate static HTML archive of game history."""

    def __init__(
        self, state: GameState, output_dir: Path, *, base_url: str | None = None
    ):
        self.state = state
        self.output_dir = output_dir
        configured_base = (
            base_url
            if base_url is not None
            else os.getenv("GREAT_WORK_ARCHIVE_BASE_URL", "/archive")
        )
        if configured_base not in {"", "/"}:
            configured_base = configured_base.rstrip("/")
        self.base_url = configured_base or "/archive"

        # Create directory structure
        self.press_dir = output_dir / "press"
        self.scholars_dir = output_dir / "scholars"
        self.assets_dir = output_dir / "assets"

        # Ensure directories exist
        for dir_path in [self.press_dir, self.scholars_dir, self.assets_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def generate_permalink(self, press: PressRecord) -> str:
        """Generate stable permalink for citation."""
        # Use hash of content for stability
        content_hash = hashlib.md5(
            f"{press.timestamp.isoformat()}{press.release.headline}".encode()
        ).hexdigest()[:8]

        date_str = press.timestamp.strftime("%Y-%m-%d")
        return f"{self.base_url}/press/{date_str}-{content_hash}.html"

    def get_base_template(self) -> str:
        """Base HTML template with navigation and styling."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="{description}">
    <title>{title} - The Great Work Archive</title>
    <style>
        :root {{
            --primary: #2c3e50;
            --secondary: #34495e;
            --accent: #3498db;
            --text: #2c3e50;
            --bg: #ecf0f1;
            --card-bg: #ffffff;
            --border: #bdc3c7;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Georgia', serif;
            line-height: 1.6;
            color: var(--text);
            background: var(--bg);
            min-height: 100vh;
        }}

        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
        }}

        header {{
            background: var(--primary);
            color: white;
            padding: 30px 0;
            margin-bottom: 30px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}

        header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: normal;
        }}

        nav {{
            background: var(--secondary);
            padding: 15px 0;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}

        nav ul {{
            list-style: none;
            display: flex;
            gap: 30px;
            flex-wrap: wrap;
        }}

        nav a {{
            color: white;
            text-decoration: none;
            font-size: 1.1em;
            transition: opacity 0.3s;
        }}

        nav a:hover {{
            opacity: 0.8;
        }}

        .press-card, .scholar-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        .press-card h2, .scholar-card h2 {{
            color: var(--primary);
            margin-bottom: 10px;
            font-size: 1.5em;
        }}

        .metadata {{
            color: #7f8c8d;
            font-size: 0.9em;
            margin-bottom: 15px;
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }}

        .metadata span {{
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }}

        .press-body {{
            line-height: 1.8;
            color: var(--text);
        }}

        .permalink {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid var(--border);
            font-size: 0.9em;
            color: #7f8c8d;
        }}

        .permalink a {{
            color: var(--accent);
            text-decoration: none;
        }}

        .permalink a:hover {{
            text-decoration: underline;
        }}

        .search-box {{
            margin-bottom: 30px;
            padding: 15px;
            background: var(--card-bg);
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        .search-box input {{
            width: 100%;
            padding: 10px;
            font-size: 1.1em;
            border: 2px solid var(--border);
            border-radius: 4px;
            font-family: inherit;
        }}

        .search-box input:focus {{
            outline: none;
            border-color: var(--accent);
        }}

        .filter-buttons {{
            margin-bottom: 20px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}

        .filter-btn {{
            padding: 8px 16px;
            background: var(--card-bg);
            border: 2px solid var(--border);
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.3s;
            font-family: inherit;
        }}

        .filter-btn:hover {{
            border-color: var(--accent);
        }}

        .filter-btn.active {{
            background: var(--accent);
            color: white;
            border-color: var(--accent);
        }}

        .timeline {{
            position: relative;
            padding-left: 40px;
        }}

        .timeline::before {{
            content: '';
            position: absolute;
            left: 10px;
            top: 0;
            bottom: 0;
            width: 2px;
            background: var(--border);
        }}

        .timeline-item {{
            position: relative;
            margin-bottom: 30px;
        }}

        .timeline-item::before {{
            content: '';
            position: absolute;
            left: -35px;
            top: 5px;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: var(--accent);
            border: 3px solid var(--card-bg);
        }}

        .pagination {{
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-top: 40px;
        }}

        .pagination a {{
            padding: 8px 12px;
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 4px;
            text-decoration: none;
            color: var(--text);
            transition: all 0.3s;
        }}

        .pagination a:hover {{
            background: var(--accent);
            color: white;
            border-color: var(--accent);
        }}

        .pagination .current {{
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }}

        footer {{
            margin-top: 60px;
            padding-top: 30px;
            border-top: 1px solid var(--border);
            text-align: center;
            color: #7f8c8d;
            font-size: 0.9em;
        }}

        @media (max-width: 768px) {{
            header h1 {{
                font-size: 1.8em;
            }}

            nav ul {{
                gap: 15px;
            }}

            .container {{
                padding: 15px;
            }}
        }}
    </style>
    {extra_head}
</head>
<body>
    <header>
        <div class="container">
            <h1>The Great Work</h1>
            <p>A Chronicle of Academic Discovery and Rivalry</p>
        </div>
    </header>

    <nav>
        <div class="container">
            <ul>
                <li><a href="{base_url}/index.html">Home</a></li>
                <li><a href="{base_url}/timeline.html">Timeline</a></li>
                <li><a href="{base_url}/scholars.html">Scholars</a></li>
                <li><a href="{base_url}/theories.html">Theories</a></li>
                <li><a href="{base_url}/expeditions.html">Expeditions</a></li>
            </ul>
        </div>
    </nav>

    <main class="container">
        {content}
    </main>

    <footer>
        <div class="container">
            <p>Generated {timestamp} | The Great Work Academic Archive</p>
            <p><small>Permanent archive of game events for citation and reference</small></p>
        </div>
    </footer>

    {extra_scripts}
</body>
</html>"""

    def generate_press_html(self, press: PressRecord, press_id: int) -> str:
        """Convert single press release to HTML with permalink."""
        permalink = self.generate_permalink(press)

        # Format metadata
        metadata_items = []
        metadata_items.append(
            f'<span>📅 {press.timestamp.strftime("%Y-%m-%d %H:%M UTC")}</span>'
        )
        metadata_items.append(
            f'<span>📰 {press.release.type.replace("_", " ").title()}</span>'
        )

        if press.release.metadata:
            for key, value in press.release.metadata.items():
                metadata_items.append(f"<span>{key}: {value}</span>")

        content = f"""
        <article class="press-card">
            <h2>{escape(press.release.headline)}</h2>
            <div class="metadata">
                {"".join(metadata_items)}
            </div>
            <div class="press-body">
                {self._format_body_paragraphs(press.release.body)}
            </div>
            <div class="permalink">
                <strong>Permalink:</strong>
                <a href="{permalink}" title="Permanent link for citation">
                    {permalink}
                </a>
                <br>
                <strong>Press ID:</strong> #{press_id}
            </div>
        </article>

        <div style="margin-top: 30px;">
            <a href="{self.base_url}/index.html">← Back to Archive</a>
        </div>
        """

        return self.get_base_template().format(
            title=escape(press.release.headline),
            description=escape(
                f"Press release from The Great Work: {press.release.headline}"
            ),
            base_url=self.base_url,
            content=content,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
            extra_head="",
            extra_scripts="",
        )

    def _format_body_paragraphs(self, body: str) -> str:
        """Format body text with proper paragraphs."""
        # Split on double newlines or sentence boundaries for better formatting
        paragraphs = body.split("\n\n") if "\n\n" in body else [body]
        formatted = []

        for para in paragraphs:
            # Escape HTML and preserve line breaks within paragraphs
            para = escape(para).replace("\n", "<br>")
            formatted.append(f"<p>{para}</p>")

        return "\n".join(formatted)

    def generate_index(
        self, press_records: List[PressRecord], page: int = 1, per_page: int = 20
    ) -> str:
        """Create index page with navigation and search."""
        total_pages = (len(press_records) + per_page - 1) // per_page
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_records = press_records[start_idx:end_idx]

        # Search box
        search_html = """
        <div class="search-box">
            <input type="text" id="searchInput" placeholder="Search press releases..."
                   onkeyup="filterPress()">
        </div>

        <div class="filter-buttons">
            <button class="filter-btn active" onclick="filterByType('all')">All</button>
            <button class="filter-btn" onclick="filterByType('academic_bulletin')">Academic Bulletins</button>
            <button class="filter-btn" onclick="filterByType('discovery_report')">Discovery Reports</button>
            <button class="filter-btn" onclick="filterByType('retraction_notice')">Retractions</button>
            <button class="filter-btn" onclick="filterByType('research_manifesto')">Research Manifestos</button>
            <button class="filter-btn" onclick="filterByType('timeline_update')">Timeline Updates</button>
        </div>
        """

        # Press cards
        cards_html = []
        for i, record in enumerate(page_records, start=start_idx + 1):
            permalink = self.generate_permalink(record)
            filename = permalink.split("/")[-1]

            card = f"""
            <article class="press-card" data-type="{record.release.type}"
                     data-search="{escape(record.release.headline.lower() + ' ' + record.release.body.lower())}">
                <h2><a href="{self.base_url}/press/{filename}" style="color: inherit; text-decoration: none;">
                    {escape(record.release.headline)}
                </a></h2>
                <div class="metadata">
                    <span>📅 {record.timestamp.strftime("%Y-%m-%d %H:%M")}</span>
                    <span>📰 {record.release.type.replace("_", " ").title()}</span>
                </div>
                <div class="press-body">
                    <p>{escape(record.release.body[:300])}{"..." if len(record.release.body) > 300 else ""}</p>
                </div>
                <div class="permalink">
                    <a href="{self.base_url}/press/{filename}">Read full release →</a>
                </div>
            </article>
            """
            cards_html.append(card)

        # Pagination
        pagination_html = self._generate_pagination(page, total_pages)

        content = f"""
        <h1>Press Archive</h1>
        <p style="margin-bottom: 30px; color: #7f8c8d;">
            Browse the complete archive of {len(press_records)} press releases from The Great Work.
            All entries are permanently archived for citation and reference.
        </p>

        {search_html}

        <div id="pressContainer">
            {''.join(cards_html)}
        </div>

        {pagination_html}
        """

        search_script = """
        <script>
        function filterPress() {{
            const input = document.getElementById('searchInput');
            const filter = input.value.toLowerCase();
            const cards = document.querySelectorAll('.press-card');

            cards.forEach(card => {{
                const searchText = card.dataset.search;
                if (searchText.indexOf(filter) > -1) {{
                    card.style.display = '';
                }} else {{
                    card.style.display = 'none';
                }}
            }});
        }}

        function filterByType(type) {{
            const buttons = document.querySelectorAll('.filter-btn');
            const cards = document.querySelectorAll('.press-card');

            // Update button states
            buttons.forEach(btn => {{
                btn.classList.remove('active');
                if (btn.onclick.toString().includes(type)) {{
                    btn.classList.add('active');
                }}
            }});

            // Filter cards
            cards.forEach(card => {{
                if (type === 'all' || card.dataset.type === type) {{
                    card.style.display = '';
                }} else {{
                    card.style.display = 'none';
                }}
            }});
        }}
        </script>
        """

        return self.get_base_template().format(
            title="Press Archive",
            description="Complete archive of press releases from The Great Work academic game",
            base_url=self.base_url,
            content=content,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
            extra_head="",
            extra_scripts=search_script,
        )

    def _generate_pagination(self, current_page: int, total_pages: int) -> str:
        """Generate pagination HTML."""
        if total_pages <= 1:
            return ""

        links = []

        # Previous link
        if current_page > 1:
            links.append(
                f'<a href="{self.base_url}/index.html?page={current_page-1}">← Previous</a>'
            )

        # Page numbers (show max 5 pages)
        start_page = max(1, current_page - 2)
        end_page = min(total_pages, current_page + 2)

        for page in range(start_page, end_page + 1):
            if page == current_page:
                links.append(f'<span class="current">{page}</span>')
            else:
                links.append(
                    f'<a href="{self.base_url}/index.html?page={page}">{page}</a>'
                )

        # Next link
        if current_page < total_pages:
            links.append(
                f'<a href="{self.base_url}/index.html?page={current_page+1}">Next →</a>'
            )

        return f'<div class="pagination">{"".join(links)}</div>'

    def generate_timeline(
        self, events: List[Event], press_records: List[PressRecord]
    ) -> str:
        """Create timeline view of all game events."""
        # Combine events and press into timeline items
        timeline_items = []

        # Add press releases to timeline
        for record in press_records[:50]:  # Limit to recent 50 for performance
            permalink = self.generate_permalink(record)
            filename = permalink.split("/")[-1]

            item = {
                "timestamp": record.timestamp,
                "type": "press",
                "title": record.release.headline,
                "content": record.release.body[:200] + "...",
                "link": f"{self.base_url}/press/{filename}",
            }
            timeline_items.append(item)

        # Sort by timestamp
        timeline_items.sort(key=lambda x: x["timestamp"], reverse=True)

        # Generate HTML
        items_html = []
        for item in timeline_items:
            item_html = f"""
            <div class="timeline-item">
                <div class="press-card">
                    <h3><a href="{item['link']}" style="color: inherit; text-decoration: none;">
                        {escape(item['title'])}
                    </a></h3>
                    <div class="metadata">
                        <span>📅 {item['timestamp'].strftime("%Y-%m-%d %H:%M")}</span>
                    </div>
                    <p>{escape(item['content'])}</p>
                    <a href="{item['link']}">Read more →</a>
                </div>
            </div>
            """
            items_html.append(item_html)

        content = f"""
        <h1>Game Timeline</h1>
        <p style="margin-bottom: 30px; color: #7f8c8d;">
            A chronological view of major events in The Great Work.
        </p>

        <div class="timeline">
            {''.join(items_html)}
        </div>
        """

        return self.get_base_template().format(
            title="Timeline",
            description="Timeline of events in The Great Work academic game",
            base_url=self.base_url,
            content=content,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
            extra_head="",
            extra_scripts="",
        )

    def generate_scholar_page(self, scholar: Scholar) -> str:
        """Create individual scholar profile page."""
        # Format memories
        memories_html = []
        for fact in scholar.memory.facts[-10:]:  # Show last 10 facts
            fact_text = f"{fact.type}: {fact.subject}"
            if fact.details:
                fact_text += (
                    f" - {', '.join(f'{k}: {v}' for k, v in fact.details.items())}"
                )
            memories_html.append(f"<li>{escape(fact_text)}</li>")

        # Format feelings
        feelings_html = []
        for key, intensity in scholar.memory.feelings.items():
            feelings_html.append(
                f"<li>{escape(key)} "
                f"<small>(intensity: {intensity:.1f})</small></li>"
            )

        # Format scars
        scars_html = []
        for scar in scholar.memory.scars:
            scars_html.append(f"<li>{escape(scar)}</li>")

        content = f"""
        <article class="scholar-card">
            <h1>{escape(scholar.name)}</h1>
            <div class="metadata">
                <span>🎭 {escape(scholar.archetype)}</span>
                <span>📚 {escape(', '.join(scholar.disciplines))}</span>
                <span>🔬 {escape(', '.join(scholar.methods))}</span>
            </div>

            <section style="margin-top: 30px;">
                <h2>Personality</h2>
                <p><strong>Drives:</strong> {escape(', '.join(scholar.drives))}</p>
                <p><strong>Virtues:</strong> {escape(', '.join(scholar.virtues))}</p>
                <p><strong>Vices:</strong> {escape(', '.join(scholar.vices))}</p>
                <p><strong>Catchphrase:</strong> "{escape(scholar.catchphrase)}"</p>
                {f'<p><strong>Taboos:</strong> {escape(", ".join(scholar.taboos))}</p>' if scholar.taboos else ''}
            </section>

            <section style="margin-top: 30px;">
                <h2>Current Status</h2>
                <p><strong>Location:</strong> {escape(scholar.career.get("location", "Unknown"))}</p>
                <p><strong>Patron:</strong> {escape(scholar.career.get("patron", "Independent"))}</p>
                <p><strong>Loyalty Score:</strong> {scholar.loyalty_score():.1f}</p>
                <p><strong>Integrity Score:</strong> {scholar.integrity_score():.1f}</p>
            </section>

            <section style="margin-top: 30px;">
                <h2>Recent Memories</h2>
                <ul>
                    {''.join(memories_html) if memories_html else '<li>No recorded memories</li>'}
                </ul>
            </section>

            <section style="margin-top: 30px;">
                <h2>Current Feelings</h2>
                <ul>
                    {''.join(feelings_html) if feelings_html else '<li>No current feelings</li>'}
                </ul>
            </section>

            {f'''<section style="margin-top: 30px;">
                <h2>Permanent Scars</h2>
                <ul>
                    {"".join(scars_html)}
                </ul>
            </section>''' if scars_html else ''}
        </article>

        <div style="margin-top: 30px;">
            <a href="{self.base_url}/scholars.html">← Back to Scholars</a>
        </div>
        """

        return self.get_base_template().format(
            title=escape(f"{scholar.name} - Scholar Profile"),
            description=escape(f"Profile of {scholar.name}, {scholar.archetype}"),
            base_url=self.base_url,
            content=content,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
            extra_head="",
            extra_scripts="",
        )

    def generate_scholars_index(self, scholars: List[Scholar]) -> str:
        """Create index of all scholars."""
        cards_html = []

        for scholar in sorted(scholars, key=lambda s: s.name):
            # Create a brief bio from archetype and disciplines
            bio = f"{scholar.archetype} specializing in {', '.join(scholar.disciplines[:2])}"

            card = f"""
            <article class="scholar-card">
                <h2><a href="{self.base_url}/scholars/{scholar.id}.html"
                       style="color: inherit; text-decoration: none;">
                    {escape(scholar.name)}
                </a></h2>
                <div class="metadata">
                    <span>🎭 {escape(scholar.archetype)}</span>
                    <span>📚 {escape(', '.join(scholar.disciplines[:2]))}</span>
                    <span>🔬 {escape(', '.join(scholar.methods[:2]))}</span>
                    <span>📍 {escape(scholar.career.get("location", "Unknown"))}</span>
                </div>
                <p>{escape(bio)}</p>
                <p style="font-style: italic;">"{escape(scholar.catchphrase)}"</p>
                <a href="{self.base_url}/scholars/{scholar.id}.html">View profile →</a>
            </article>
            """
            cards_html.append(card)

        content = f"""
        <h1>Scholar Directory</h1>
        <p style="margin-bottom: 30px; color: #7f8c8d;">
            Browse profiles of {len(scholars)} scholars participating in The Great Work.
        </p>

        {''.join(cards_html)}
        """

        return self.get_base_template().format(
            title="Scholars",
            description="Directory of scholars in The Great Work academic game",
            base_url=self.base_url,
            content=content,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
            extra_head="",
            extra_scripts="",
        )

    def export_full_archive(self) -> Path:
        """Export complete archive with all pages."""
        print(f"Exporting web archive to {self.output_dir}")

        # Get all data
        press_records = list(reversed(self.state.list_press_releases()))  # Oldest first
        scholars = list(self.state.all_scholars())
        events = self.state.export_events()

        # Generate index pages
        index_path = self.output_dir / "index.html"
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(self.generate_index(press_records))

        # Generate individual press releases
        for i, record in enumerate(press_records, start=1):
            permalink = self.generate_permalink(record)
            filename = permalink.split("/")[-1]
            press_path = self.press_dir / filename

            with open(press_path, "w", encoding="utf-8") as f:
                f.write(self.generate_press_html(record, i))

        # Generate timeline
        timeline_path = self.output_dir / "timeline.html"
        with open(timeline_path, "w", encoding="utf-8") as f:
            f.write(self.generate_timeline(events, press_records))

        # Generate scholars index
        scholars_index_path = self.output_dir / "scholars.html"
        with open(scholars_index_path, "w", encoding="utf-8") as f:
            f.write(self.generate_scholars_index(scholars))

        # Generate individual scholar pages
        for scholar in scholars:
            scholar_path = self.scholars_dir / f"{scholar.id}.html"
            with open(scholar_path, "w", encoding="utf-8") as f:
                f.write(self.generate_scholar_page(scholar))

        # Create placeholder pages for theories and expeditions
        for page_name in ["theories", "expeditions"]:
            page_path = self.output_dir / f"{page_name}.html"
            with open(page_path, "w", encoding="utf-8") as f:
                content = f"""
                <h1>{page_name.title()}</h1>
                <p style="color: #7f8c8d;">This section is coming soon.</p>
                """
                f.write(
                    self.get_base_template().format(
                        title=page_name.title(),
                        description=f"{page_name.title()} in The Great Work",
                        base_url=self.base_url,
                        content=content,
                        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
                        extra_head="",
                        extra_scripts="",
                    )
                )

        print(f"Archive exported successfully to {self.output_dir}")
        print(f"  - {len(press_records)} press releases")
        print(f"  - {len(scholars)} scholar profiles")
        print(f"  - Timeline with {len(events)} events")

        return self.output_dir


__all__ = ["WebArchive", "ArchivePage"]
