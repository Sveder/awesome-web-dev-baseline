#!/usr/bin/env python3
"""
Web.dev Blog Scraper for Baseline Tools
Scrapes web.dev/blog for new tools that support Web Platform Baseline
and updates README.md with findings using OpenAI analysis.
"""

import os
import re
import sys
import json
import time
import requests
import feedparser
from typing import List, Dict, Set
from urllib.parse import urljoin, urlparse
from datetime import datetime
from bs4 import BeautifulSoup
from openai import OpenAI


OPENAI_KEY = os.getenv('OPENAI_KEY')

class BaselineToolScraper:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_KEY)
        self.base_url = 'https://web.dev'
        self.rss_url = 'https://web.dev/static/blog/feed.xml'
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def scrape_blog_posts(self, max_posts: int = 20) -> List[Dict]:
        """Get recent blog posts from web.dev RSS feed"""
        print(f"Fetching blog posts from RSS feed: {self.rss_url}...")

        try:
            feed = feedparser.parse(self.rss_url)

            if feed.bozo:
                print(f"Warning: RSS feed may have parsing issues: {feed.bozo_exception}")

            posts = []
            for entry in feed.entries[:max_posts]:
                posts.append({
                    'url': entry.link,
                    'title': entry.title,
                    'summary': getattr(entry, 'summary', ''),
                    'published': getattr(entry, 'published', '')
                })

            print(f"Found {len(posts)} blog posts to analyze")
            return posts

        except Exception as e:
            print(f"Error fetching RSS feed: {e}")
            return []

    def get_post_content(self, url: str) -> str:
        """Get the full content of a blog post"""
        try:
            response = self.session.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Remove navigation, ads, and other non-content elements
            for element in soup.find_all(['nav', 'aside', 'footer', 'header']):
                element.decompose()

            # Try to find the main content
            content_selectors = ['article', 'main', '.post-content', '.content', 'body']
            content = ""

            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content = content_elem.get_text(separator='\n', strip=True)
                    if len(content) > 500:  # Reasonable content length
                        break

            return content[:8000]  # Limit content for API

        except Exception as e:
            print(f"Error getting content from {url}: {e}")
            return ""

    def analyze_posts_batch(self, posts_batch: List[Dict]) -> List[Dict]:
        """Analyze a batch of posts for baseline tools"""

        # Prepare posts data for batch analysis
        posts_data = []
        for i, post in enumerate(posts_batch):
            content = self.get_post_content(post['url'])
            if content:
                content_to_analyze = content
                if post.get('summary') and len(content) < 500:
                    content_to_analyze = f"{post['summary']}\n\n{content}"

                posts_data.append({
                    "id": i,
                    "title": post['title'],
                    "summary": post.get('summary', ''),
                    "content": content_to_analyze[:1000]  # Limit content size
                })

        if not posts_data:
            return []

    def analyze_posts_batch(self, posts_batch: List[Dict], existing_tools: Dict[str, Dict[str, str]]) -> List[Dict]:
        """Analyze a batch of posts for baseline tools"""

        # Prepare posts data for batch analysis
        posts_data = []
        for i, post in enumerate(posts_batch):
            content = self.get_post_content(post['url'])
            if content:
                content_to_analyze = content
                if post.get('summary') and len(content) < 500:
                    content_to_analyze = f"{post['summary']}\n\n{content}"

                posts_data.append({
                    "id": i,
                    "title": post['title'],
                    "summary": post.get('summary', ''),
                    "content": content_to_analyze[:1000]  # Limit content size
                })

        if not posts_data:
            return []

        # Create existing tools summary
        existing_tools_text = ""
        if existing_tools:
            existing_tools_text = "\n\nEXISTING TOOLS (do not add these again):\n"
            for key, tool_data in existing_tools.items():
                existing_tools_text += f"- {tool_data['name']} ({tool_data.get('url', 'no url')}) - {tool_data.get('description', 'no description')}\n"

        # Create batch analysis prompt
        posts_text = ""
        for post_data in posts_data:
            posts_text += f"""
POST {post_data['id']}:
Title: {post_data['title']}
{f"Summary: {post_data['summary']}" if post_data['summary'] else ""}
Content: {post_data['content'][:800]}

---
"""

        prompt = f"""
        Analyze these web development blog posts for NEW tools, libraries, or services that support or use Web Platform Baseline.

        Web Platform Baseline is about browser compatibility and interoperability - tools that help developers ensure their code works across different browsers.

        {posts_text}

        {existing_tools_text}

        Look for NEW tools (not in the existing list above) that fall into these categories:
        1. Development tools (build tools, bundlers, linters)
        2. Code editors and IDEs
        3. CSS tools and processors
        4. Browser support utilities
        5. Testing frameworks
        6. AI-powered development tools
        7. Performance monitoring tools
        8. Frameworks and libraries

        IMPORTANT: Do not include any tools that are already in the existing tools list above, including variations of the same tool or products from the same company.

        Return a JSON object with this structure:
        {{
            "posts": [
                {{
                    "post_id": 0,
                    "has_baseline_tools": true/false,
                    "tools": [
                        {{
                            "name": "Tool Name",
                            "category": "Development Tools|Code Editors & IDEs|Build Tools & Bundlers|Linting & Code Quality|CSS Tools|Browser Support Tools|AI-Powered Development|Performance & Monitoring|Testing Tools|Frameworks & Libraries",
                            "description": "Brief description of how it relates to baseline/browser compatibility",
                            "url": "https://tool-website.com",
                            "confidence": 0.8
                        }}
                    ]
                }}
            ]
        }}

        Only include NEW tools that have clear connections to browser compatibility, cross-browser support, or Web Platform Baseline.
        Set confidence between 0.0 and 1.0 based on how certain you are about the baseline connection.
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )

            result = response.choices[0].message.content.strip()

            # Extract JSON from response
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
                # Extract all tools from all posts
                batch_tools = []
                for post_analysis in analysis.get('posts', []):
                    if post_analysis.get('has_baseline_tools') and post_analysis.get('tools'):
                        batch_tools.extend(post_analysis['tools'])
                return batch_tools
            else:
                return []

        except Exception as e:
            print(f"Error analyzing batch with OpenAI: {e}")
            return []

    def analyze_all_posts_for_baseline_tools(self, posts: List[Dict], existing_tools: Dict[str, Dict[str, str]]) -> List[Dict]:
        """Use OpenAI to analyze posts in batches for baseline-related tools"""
        all_tools = []
        batch_size = 5  # Process 5 posts at a time to avoid token limits

        for i in range(0, len(posts), batch_size):
            batch = posts[i:i + batch_size]
            print(f"  Processing batch {i//batch_size + 1}/{(len(posts) + batch_size - 1)//batch_size} ({len(batch)} posts)")

            batch_tools = self.analyze_posts_batch(batch, existing_tools)
            all_tools.extend(batch_tools)

            # Rate limiting between batches
            if i + batch_size < len(posts):
                time.sleep(3)

        return all_tools

    def get_existing_tools(self) -> Dict[str, Dict[str, str]]:
        """Get list of tools already in README.md with their URLs and descriptions"""
        try:
            with open('README.md', 'r', encoding='utf-8') as f:
                content = f.read()

            # Use AI to extract tool names, URLs, and descriptions
            prompt = f"""
            Extract all tools from this README content with their names, URLs, and descriptions. Focus on actual development tools, libraries, frameworks, and services.

            Return a JSON object where each key is the normalized tool name and the value contains name, url, and description:

            README Content:
            {content[:4000]}  # Limit content for API

            Example format:
            {{
                "webstorm": {{"name": "WebStorm", "url": "https://www.jetbrains.com/webstorm/", "description": "Jetbrain's WebStorm 2025.2+ displays Web Platform Baseline status in documentation popup"}},
                "visual studio code": {{"name": "Visual Studio Code", "url": "https://code.visualstudio.com/", "description": "Ships with native Baseline support for CSS and HTML in version 1.100+"}}
            }}
            """

            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1200
            )

            result = response.choices[0].message.content.strip()

            # Extract JSON object from response
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                tools_data = json.loads(json_match.group())
                return tools_data
            else:
                # Fallback to regex approach
                return self._get_existing_tools_fallback(content)

        except Exception as e:
            print(f"Error analyzing existing tools with AI, falling back to regex: {e}")
            return self._get_existing_tools_fallback(content if 'content' in locals() else "")

    def _get_existing_tools_fallback(self, content: str) -> Dict[str, Dict[str, str]]:
        """Fallback regex-based tool extraction"""
        tool_pattern = r'\[([^\]]+)\]\(([^\)]+)\)\s*-\s*(.+?)(?=\n|$)'
        tools = {}

        for match in re.finditer(tool_pattern, content):
            name = match.group(1).strip()
            url = match.group(2).strip()
            description = match.group(3).strip()

            if len(name) > 3 and not name.startswith(('http', 'www')):
                normalized_name = name.lower()
                tools[normalized_name] = {
                    "name": name,
                    "url": url,
                    "description": description
                }

        return tools

    def is_tool_duplicate(self, new_tool_name: str, new_tool_url: str, existing_tools: Dict[str, Dict[str, str]]) -> bool:
        """Use AI to check if a new tool is a duplicate of existing ones"""
        if not existing_tools:
            return False

        # Quick exact match check first
        if new_tool_name.lower() in existing_tools:
            return True

        # Check URL match (same domain/tool)
        if new_tool_url:
            new_parsed = urlparse(new_tool_url)
            new_domain = new_parsed.netloc.lower().replace('www.', '')

            for tool_data in existing_tools.values():
                if tool_data.get('url'):
                    existing_parsed = urlparse(tool_data['url'])
                    existing_domain = existing_parsed.netloc.lower().replace('www.', '')

                    if new_domain == existing_domain:
                        return True

        # Use AI for similarity check with existing tool details
        existing_details = []
        for key, tool_data in list(existing_tools.items())[:10]:  # Limit for API
            existing_details.append(f"- {tool_data['name']} ({tool_data.get('url', 'no url')}) - {tool_data.get('description', 'no description')}")

        prompt = f"""
        Is "{new_tool_name}" ({new_tool_url}) the same tool as any of these existing tools? Consider variations in naming, company names, and URLs.

        Examples of duplicates:
        - "WebStorm" vs "JetBrains WebStorm" vs "JetBrains IDE"
        - "VS Code" vs "Visual Studio Code"
        - Tools from the same company/domain

        New tool: {new_tool_name} ({new_tool_url})

        Existing tools:
        {chr(10).join(existing_details)}

        Return only "YES" if it's a duplicate, or "NO" if it's a different tool.
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=50
            )

            result = response.choices[0].message.content.strip().upper()
            return result.startswith("YES")

        except Exception as e:
            print(f"Error checking duplicate with AI: {e}")
            # Fallback to simple string matching
            return new_tool_name.lower() in existing_tools

    def update_readme(self, new_tools: List[Dict]):
        """Update README.md with new tools"""
        if not new_tools:
            print("No new tools to add")
            return

        try:
            with open('README.md', 'r', encoding='utf-8') as f:
                content = f.read()

            # Group tools by category
            tools_by_category = {}
            for tool in new_tools:
                category = tool['category']
                if category not in tools_by_category:
                    tools_by_category[category] = []
                tools_by_category[category].append(tool)

            # Find and update each section
            updated_content = content

            for category, tools in tools_by_category.items():
                # Find the category section
                section_pattern = f"## {re.escape(category)}\\n"
                match = re.search(section_pattern, updated_content)

                if match:
                    # Find the end of this section (next ## or end of file)
                    start_pos = match.end()
                    next_section = re.search(r'\n## ', updated_content[start_pos:])

                    if next_section:
                        end_pos = start_pos + next_section.start()
                        section_content = updated_content[start_pos:end_pos]
                    else:
                        section_content = updated_content[start_pos:]
                        end_pos = len(updated_content)

                    # Add new tools to the section
                    new_entries = []
                    for tool in tools:
                        entry = f"- [{tool['name']}]({tool['url']}) - {tool['description']}"
                        new_entries.append(entry)

                    if new_entries:
                        # Insert new entries at the end of existing entries
                        insert_text = '\n' + '\n'.join(new_entries) + '\n'
                        updated_content = updated_content[:end_pos] + insert_text + updated_content[end_pos:]

            # Write updated content
            with open('README.md', 'w', encoding='utf-8') as f:
                f.write(updated_content)

            print(f"Added {len(new_tools)} new tools to README.md")

        except Exception as e:
            print(f"Error updating README.md: {e}")

    def run(self):
        """Main execution function"""
        print("Starting Baseline Tool Scraper...")

        # # Check for OpenAI API key
        # if not os.getenv('OPENAI_KEY'):
        #     print("Error: OPENAI_KEY environment variable not set")
        #     sys.exit(1)

        # Get existing tools to avoid duplicates
        existing_tools = self.get_existing_tools()
        print(f"Found {len(existing_tools)} existing tools in README.md")

        # Scrape blog posts
        posts = self.scrape_blog_posts(max_posts=15)

        if not posts:
            print("No blog posts found")
            return

        # Analyze all posts in a single batch
        print(f"\nAnalyzing all {len(posts)} posts for baseline tools...")
        all_found_tools = self.analyze_all_posts_for_baseline_tools(posts, existing_tools)

        # Check for duplicates and filter by confidence
        new_tools = []
        for tool in all_found_tools:
            if not self.is_tool_duplicate(tool['name'], tool.get('url', ''), existing_tools) and tool['confidence'] >= 0.7:
                new_tools.append(tool)
                existing_tools[tool['name'].lower()] = {
                    'name': tool['name'],
                    'url': tool.get('url', ''),
                    'description': tool.get('description', '')
                }
                print(f"  Found new tool: {tool['name']}")
            else:
                print(f"  Skipping duplicate/low confidence tool: {tool['name']} (confidence: {tool.get('confidence', 0)})")

        # Update README with new tools
        if new_tools:
            print(f"\nFound {len(new_tools)} new tools to add")
            self.update_readme(new_tools)

            # Print summary
            print("\nNew tools added:")
            for tool in new_tools:
                print(f"  - {tool['name']} ({tool['category']})")
        else:
            print("No new tools found")

if __name__ == "__main__":
    scraper = BaselineToolScraper()
    scraper.run()