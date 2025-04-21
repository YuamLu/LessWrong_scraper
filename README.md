# 🔍 LessWrong Scraper

> 📚 A powerful tool to collect and analyze LessWrong posts with progress tracking!

## ✨ Key Features

- 🚀 **Unlimited Scraping** - Automatically collect endless posts with progress bar
- 💾 **Smart Storage** - Save data to easily accessible JSON in current directory
- ⏯️ **Resume Capability** - Continue from where you left off if interrupted
- 📝 **Complete Data** - Get posts, authors, dates, comments and more

## 🔧 Quick Start

```bash
# Install required packages
pip install requests beautifulsoup4 tqdm

# Run the scraper
python lesswrong_scraper.py
```

## 📋 Common Commands

```bash
# Scrape specific post
python lesswrong_scraper.py --url "https://www.greaterwrong.com/posts/FGqfdJmB8MSH5LKGc/training-agi-in-secret-would-be-unsafe-and-unethical-1"

# Start from post #100
python lesswrong_scraper.py --start-offset 100

# Set 5s delay between requests
python lesswrong_scraper.py --delay 5
```

## 🎛️ Options

| Option | Description |
|--------|-------------|
| `--url URL` | Specific post URL to scrape |
| `--output-dir DIR` | Save directory (default: current) |
| `--output-file FILE` | Data filename |
| `--delay SECONDS` | Delay between requests |
| `--batch-save N` | Save every N posts |
| `--start-offset N` | Start from offset N |
| `--no-progress` | Disable progress bar |
| `--max-offset N` | Stop at offset N |

## 📁 Output Format

```json
{
  "posts": [
    {
      "url": "post_url",
      "title": "post_title",
      "author": "author_name",
      "date": "post_date",
      "content": "post_content",
      "comments": [...]
    }
  ]
}
```

## ⚠️ Notes

- 🕸️ Uses configurable delays to respect server resources
- 💿 Consider database storage for extremely large collections
- 📜 For educational purposes - please respect website terms of service

## 📜 License

MIT License