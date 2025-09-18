# Auto Tool Detection

This repository includes an automated system that scans the web.dev blog daily to discover new tools and libraries that support Web Platform Baseline.

## How it works

1. **Daily Scan**: A GitHub Action runs daily at 9 AM UTC to check the web.dev blog for new posts
2. **Content Analysis**: New blog posts are analyzed using AI to identify tools that:
   - Support Web Platform Baseline features
   - Are production-ready and publicly available
   - Fit into one of the existing categories in the awesome list
3. **Automatic Updates**: When new tools are found, they're automatically added to the appropriate sections of the README
4. **Pull Request Creation**: Changes are submitted as pull requests for human review before merging

## Setup Requirements

To enable the auto tool detection feature, you need to:

1. **OpenAI API Key**: Add an `OPENAI_API_KEY` secret to your GitHub repository settings
   - Go to repository Settings → Secrets and variables → Actions
   - Add a new repository secret named `OPENAI_API_KEY`
   - Use an OpenAI API key with access to GPT-4

2. **GitHub Permissions**: The workflow already has the necessary permissions configured

## Manual Trigger

You can manually trigger the tool detection workflow:
- Go to the Actions tab in your repository
- Select "Auto Tool Detection from web.dev"
- Click "Run workflow"

## Categories

The system can automatically add tools to these categories:
- Development Tools
- Code Editors & IDEs
- Build Tools & Bundlers
- Linting & Code Quality
- CSS Tools
- Browser Support Tools
- Documentation & Resources
- AI-Powered Development
- Performance & Monitoring
- Testing Tools
- Frameworks & Libraries

## Customization

You can modify the detection logic by editing `scripts/detect-tools.js`:
- Adjust the AI prompt for different tool selection criteria
- Add new categories
- Change the web.dev blog scanning logic
- Modify the README insertion format