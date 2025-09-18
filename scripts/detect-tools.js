#!/usr/bin/env node

// Using built-in fetch available in Node.js 18+
const cheerio = require('cheerio');
const fs = require('fs');
const path = require('path');

// Configuration
const WEB_DEV_FEED_URL = 'https://web.dev/blog/feed.xml';
const README_PATH = path.join(__dirname, '..', 'README.md');
const CACHE_FILE = path.join(__dirname, 'processed-articles.json');

// Load processed articles cache
function loadProcessedArticles() {
  try {
    const cache = fs.readFileSync(CACHE_FILE, 'utf8');
    return new Set(JSON.parse(cache));
  } catch (error) {
    return new Set();
  }
}

// Save processed articles cache
function saveProcessedArticles(processedArticles) {
  fs.writeFileSync(CACHE_FILE, JSON.stringify([...processedArticles], null, 2));
}

// Fetch recent blog posts from web.dev RSS feed
async function fetchBlogPosts() {
  try {
    const response = await fetch(WEB_DEV_FEED_URL);
    const xmlText = await response.text();
    const $ = cheerio.load(xmlText, { xmlMode: true });

    const posts = [];

    // Parse RSS feed items
    $('item').each((index, element) => {
      if (index >= 10) return false; // Limit to 10 posts

      const $item = $(element);
      const title = $item.find('title').text().trim();
      const link = $item.find('link').text().trim();

      if (title && link) {
        posts.push({ title, url: link });
      }
    });

    return posts;
  } catch (error) {
    console.error('Error fetching RSS feed:', error);
    // Fallback to hardcoded recent posts for testing
    return [
      {
        title: "What's new in CSS and UI: I/O 2024 edition",
        url: "https://web.dev/articles/whats-new-css-ui-2024"
      },
      {
        title: "Optimizing Web Fonts Performance",
        url: "https://web.dev/articles/optimize-webfont-loading"
      }
    ];
  }
}

// Fetch content of a specific blog post
async function fetchBlogPost(url) {
  try {
    const response = await fetch(url);
    const html = await response.text();
    const $ = cheerio.load(html);

    // Extract main content
    const content = $('main article, .devsite-article-body, .post-content').text() || $('body').text();

    return content.slice(0, 8000); // Limit content length for API
  } catch (error) {
    console.error(`Error fetching blog post ${url}:`, error);
    return '';
  }
}

// Use OpenAI API to analyze content for new tools
async function analyzeContentForTools(title, content, url) {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    console.log('No OpenAI API key provided, skipping AI analysis');
    return null;
  }

  const prompt = `Analyze this web development blog post and identify any new tools, libraries, frameworks, or services that support Web Platform Baseline and should be added to an awesome list.

Title: ${title}
URL: ${url}
Content: ${content}

Look for:
- Development tools and IDEs
- Build tools and bundlers
- CSS tools and processors
- Testing frameworks
- Performance monitoring tools
- Browser support tools
- AI-powered development tools
- Code quality and linting tools
- Frameworks and libraries

For each tool you identify, provide:
1. Tool name
2. Brief description (one sentence)
3. URL/link
4. Appropriate category from: Development Tools, Code Editors & IDEs, Build Tools & Bundlers, Linting & Code Quality, CSS Tools, Browser Support Tools, Documentation & Resources, AI-Powered Development, Performance & Monitoring, Testing Tools, Frameworks & Libraries

Only include tools that:
- Are mentioned as new, updated, or noteworthy in the post
- Support or relate to Web Platform Baseline features
- Are production-ready tools (not experimental demos)
- Have public availability

Respond with a JSON array of tools, or an empty array if no relevant tools are found.

Example response:
[
  {
    "name": "Example Tool",
    "description": "A tool that does something useful for web developers.",
    "url": "https://example.com",
    "category": "Development Tools"
  }
]`;

  try {
    const response = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        messages: [
          {
            role: 'system',
            content: 'You are an expert web developer who identifies useful tools and libraries for web development. You are very selective and only recommend high-quality, production-ready tools.'
          },
          {
            role: 'user',
            content: prompt
          }
        ],
        temperature: 0.3,
        max_tokens: 2000
      })
    });

    const result = await response.json();

    if (result.error) {
      console.error('OpenAI API error:', result.error);
      return null;
    }

    const content_result = result.choices?.[0]?.message?.content;
    if (!content_result) {
      console.error('No content in OpenAI response');
      return null;
    }

    try {
      return JSON.parse(content_result);
    } catch (parseError) {
      console.error('Error parsing OpenAI JSON response:', parseError);
      console.log('Raw response:', content_result);
      return null;
    }
  } catch (error) {
    console.error('Error calling OpenAI API:', error);
    return null;
  }
}

// Add tools to README
function addToolsToReadme(tools) {
  if (!tools || tools.length === 0) {
    return false;
  }

  let readme = fs.readFileSync(README_PATH, 'utf8');
  let hasChanges = false;

  // Category mapping to README sections
  const categoryMapping = {
    'Development Tools': '## Development Tools',
    'Code Editors & IDEs': '## Code Editors & IDEs',
    'Build Tools & Bundlers': '## Build Tools & Bundlers',
    'Linting & Code Quality': '## Linting & Code Quality',
    'CSS Tools': '## CSS Tools',
    'Browser Support Tools': '## Browser Support Tools',
    'Documentation & Resources': '## Documentation & Resources',
    'AI-Powered Development': '## AI-Powered Development',
    'Performance & Monitoring': '## Performance & Monitoring',
    'Testing Tools': '## Testing Tools',
    'Frameworks & Libraries': '## Frameworks & Libraries'
  };

  for (const tool of tools) {
    const sectionHeader = categoryMapping[tool.category];
    if (!sectionHeader) {
      console.log(`Unknown category: ${tool.category}, skipping tool: ${tool.name}`);
      continue;
    }

    // Check if tool is already in README
    if (readme.includes(tool.name) || readme.includes(tool.url)) {
      console.log(`Tool ${tool.name} already exists in README, skipping`);
      continue;
    }

    // Find the section and add the tool
    const sectionIndex = readme.indexOf(sectionHeader);
    if (sectionIndex === -1) {
      console.log(`Section ${sectionHeader} not found in README`);
      continue;
    }

    // Find the end of the current section (next ## or end of file)
    const nextSectionIndex = readme.indexOf('\n## ', sectionIndex + sectionHeader.length);
    const insertIndex = nextSectionIndex === -1 ? readme.length : nextSectionIndex;

    // Create the tool entry
    const toolEntry = `- [${tool.name}](${tool.url}) - ${tool.description}\n`;

    // Insert the tool entry at the end of the section
    const beforeSection = readme.slice(0, insertIndex);
    const afterSection = readme.slice(insertIndex);

    readme = beforeSection + toolEntry + afterSection;
    hasChanges = true;

    console.log(`Added tool: ${tool.name} to ${tool.category}`);
  }

  if (hasChanges) {
    fs.writeFileSync(README_PATH, readme);
  }

  return hasChanges;
}

// Main function
async function main() {
  console.log('Starting tool detection from web.dev blog...');

  const processedArticles = loadProcessedArticles();
  const blogPosts = await fetchBlogPosts();

  if (blogPosts.length === 0) {
    console.log('No blog posts found');
    return;
  }

  console.log(`Found ${blogPosts.length} blog posts`);

  let allTools = [];

  for (const post of blogPosts) {
    if (processedArticles.has(post.url)) {
      console.log(`Skipping already processed article: ${post.title}`);
      continue;
    }

    console.log(`Processing: ${post.title}`);

    const content = await fetchBlogPost(post.url);
    if (!content) {
      console.log(`No content found for: ${post.title}`);
      continue;
    }

    const tools = await analyzeContentForTools(post.title, content, post.url);

    if (tools && tools.length > 0) {
      console.log(`Found ${tools.length} tools in: ${post.title}`);
      allTools.push(...tools);
    } else {
      console.log(`No tools found in: ${post.title}`);
    }

    processedArticles.add(post.url);

    // Add delay to be respectful to the API
    await new Promise(resolve => setTimeout(resolve, 1000));
  }

  // Add tools to README
  if (allTools.length > 0) {
    console.log(`Adding ${allTools.length} tools to README`);
    const hasChanges = addToolsToReadme(allTools);

    if (hasChanges) {
      console.log('README updated successfully');
    } else {
      console.log('No new tools to add to README');
    }
  } else {
    console.log('No new tools found');
  }

  // Save processed articles
  saveProcessedArticles(processedArticles);

  console.log('Tool detection completed');
}

// Run the script
if (require.main === module) {
  main().catch(console.error);
}