import requests
from bs4 import BeautifulSoup
import json
import time
import os
import argparse
from datetime import datetime
import sys
import signal
from tqdm import tqdm

class LessWrongScraper:
    def __init__(self, output_dir=".", delay=2, verbose=True, 
                 output_file="lesswrong_all_data.json", log_file="scraper_progress.json",
                 show_progress=True):
        """Initialize the scraper with configurable parameters
        
        Args:
            output_dir: Directory to save scraped data (default: current directory)
            delay: Delay between requests in seconds
            verbose: Whether to print verbose output
            output_file: File to save all data to
            log_file: File to save progress information
            show_progress: Whether to show progress bar
        """
        self.base_url = "https://www.greaterwrong.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.output_dir = output_dir
        self.delay = delay
        self.verbose = verbose
        self.output_file = os.path.join(output_dir, output_file)
        self.log_file = os.path.join(output_dir, log_file)
        self.all_data = {"posts": []}
        self.scraped_urls = set()
        self.show_progress = show_progress
        self.progress_bar = None
        
        # Create a directory to store scraped data if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Setup signal handling for graceful exit
        signal.signal(signal.SIGINT, self.handle_exit)
        signal.signal(signal.SIGTERM, self.handle_exit)
        
        # Load existing data if available
        self.load_existing_data()
    
    def handle_exit(self, signum, frame):
        """Handle exit signals by saving progress"""
        self.log("Received exit signal. Saving progress...")
        self.save_all_data()
        self.save_progress()
        
        # Close progress bar if active
        if self.progress_bar is not None:
            self.progress_bar.close()
            
        print("\nScraping interrupted. Progress has been saved.")
        sys.exit(0)
    
    def load_existing_data(self):
        """Load existing data and progress if available"""
        # Load all data
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, 'r', encoding='utf-8') as f:
                    self.all_data = json.load(f)
                    self.log(f"Loaded {len(self.all_data['posts'])} existing posts from {self.output_file}")
                    # Build a set of already scraped URLs
                    self.scraped_urls = {post['url'] for post in self.all_data['posts']}
            except json.JSONDecodeError:
                self.log(f"Error loading {self.output_file}. Starting with empty data.")
                self.all_data = {"posts": []}
        
        # Load progress information
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    progress = json.load(f)
                    self.log(f"Loaded progress information. Last offset: {progress.get('last_offset', 0)}")
                    return progress
            except json.JSONDecodeError:
                self.log(f"Error loading {self.log_file}. Starting from the beginning.")
        
        return {"last_offset": 0, "last_scraped_time": None}
    
    def save_progress(self):
        """Save progress information to log file"""
        progress = {
            "last_offset": getattr(self, "current_offset", 0),
            "last_scraped_time": datetime.now().isoformat(),
            "total_posts_scraped": len(self.all_data["posts"]),
            "scraped_urls": list(self.scraped_urls)
        }
        
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
        
        self.log(f"Saved progress information to {self.log_file}")
    
    def save_all_data(self):
        """Save all scraped data to a single JSON file"""
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(self.all_data, f, ensure_ascii=False, indent=2)
        
        self.log(f"Saved {len(self.all_data['posts'])} posts to {self.output_file}")
        
        # Update progress bar if active
        if self.progress_bar is not None:
            self.progress_bar.set_description(f"Posts saved: {len(self.all_data['posts'])}")
    
    def log(self, message):
        """Print a log message if verbose mode is enabled"""
        if self.verbose:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Only print log if progress bar is not active or is disabled
            if not self.show_progress or self.progress_bar is None:
                print(f"[{timestamp}] {message}")
            else:
                # Write above the progress bar
                self.progress_bar.write(f"[{timestamp}] {message}")
    
    def get_page(self, url):
        """Fetch a page and return its soup"""
        try:
            self.log(f"Fetching: {url}")
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except requests.exceptions.RequestException as e:
            error_msg = f"Error fetching {url}: {e}"
            if self.show_progress and self.progress_bar is not None:
                self.progress_bar.write(error_msg)
            else:
                print(error_msg, file=sys.stderr)
            return None
    
    def get_posts_from_list(self, list_url):
        """Get posts from a list page"""
        self.log(f"Fetching posts list from: {list_url}")
        soup = self.get_page(list_url)
        if not soup:
            return []
        
        posts = []
        already_scraped = 0
        total_posts_found = 0
        
        # Find post blocks
        post_blocks = soup.select("h1, h2")
        for post_title in post_blocks:
            link = post_title.select_one("a")
            if link and "/posts/" in link.get('href', ''):
                post_url = link.get('href')
                if not post_url.startswith("http"):
                    post_url = self.base_url + post_url
                
                total_posts_found += 1
                
                # Skip already scraped URLs
                if post_url in self.scraped_urls:
                    self.log(f"Skipping already scraped post: {post_url}")
                    already_scraped += 1
                    continue
                
                posts.append({
                    "title": link.text.strip(),
                    "url": post_url
                })
        
        self.log(f"Found {len(posts)} new posts (skipped {already_scraped} already scraped posts, total on page: {total_posts_found})")
        return posts, total_posts_found
    
    def scrape_post(self, post_url):
        """Scrape a single post and its comments"""
        if post_url in self.scraped_urls:
            self.log(f"Skipping already scraped post: {post_url}")
            return None
            
        self.log(f"Scraping post: {post_url}")
        soup = self.get_page(post_url)
        if not soup:
            return None
        
        # Extract post content
        post_data = {
            "url": post_url,
            "title": "",
            "author": "",
            "date": "",
            "content": "",
            "comments": [],
            "scraped_at": datetime.now().isoformat()
        }
        
        # Get title
        title_tag = soup.select_one("h1.post-title")
        if title_tag:
            post_data["title"] = title_tag.text.strip()
        
        # Get author
        author_tag = soup.select_one("div.post-meta a.author")
        if author_tag:
            post_data["author"] = author_tag.text.strip()
        
        # Get date
        date_tag = soup.select_one("div.post-meta span.date")
        if date_tag:
            date_text = date_tag.text.strip()
            post_data["date"] = date_text
        
        # Get post content
        content_div = soup.select_one("div.body-text.post-body")
        if content_div:
            post_data["content"] = content_div.text.strip()
        
        # Get comments
        comments = []
        comment_items = soup.select("li.comment-item")
        for comment in comment_items:
            # Skip deleted comments
            if comment.select_one(".deleted-comment"):
                continue
                
            comment_author = comment.select_one("a.author")
            comment_date = comment.select_one("a.date")
            comment_body = comment.select_one("div.comment-body")
            comment_karma = comment.select_one("div.karma span.karma-value")
            
            if comment_body:
                comment_data = {
                    "author": comment_author.text.strip() if comment_author else "Unknown Commenter",
                    "date": comment_date.text.strip() if comment_date else "Unknown Date",
                    "text": comment_body.text.strip(),
                    "points": comment_karma.text.strip() if comment_karma else "0"
                }
                comments.append(comment_data)
        
        post_data["comments"] = comments
        self.log(f"Scraped post with {len(post_data['comments'])} comments")
        
        # Add to scraped URLs
        self.scraped_urls.add(post_url)
        
        # Update progress bar with title if active
        if self.progress_bar is not None:
            self.progress_bar.set_postfix_str(f"Last: {post_data['title'][:30]}...")
        
        return post_data
    
    def run_unlimited(self, batch_save=20, start_offset=None, max_offset=None):
        """Run the scraper for unlimited posts with automatic pagination
        
        Args:
            batch_save: Save progress after every N posts
            start_offset: Override the starting offset
            max_offset: Maximum offset to scrape (optional, for testing)
        """
        # Determine starting offset
        progress = self.load_existing_data()
        offset = start_offset if start_offset is not None else progress.get("last_offset", 0)
        self.current_offset = offset
        
        posts_since_last_save = 0
        total_new_posts = 0
        empty_pages_count = 0
        max_empty_pages = 3  # Stop after 3 consecutive empty pages
        
        try:
            # Initialize progress bar (unknown total)
            if self.show_progress:
                self.progress_bar = tqdm(
                    desc=f"Posts saved: {len(self.all_data['posts'])}",
                    unit="post",
                    bar_format="{desc} |{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
                    dynamic_ncols=True  # Adjust to terminal width
                )
            
            while True:
                # Check if we've reached the maximum offset (if specified)
                if max_offset is not None and offset >= max_offset:
                    self.log(f"Reached maximum offset {max_offset}. Stopping.")
                    break
                
                # Get posts from current offset
                list_url = f"{self.base_url}/?offset={offset}"
                posts_result = self.get_posts_from_list(list_url)
                
                # Unpack the result tuple
                posts, total_posts_on_page = posts_result
                
                # If truly no posts were found on the page, count as empty page
                if total_posts_on_page == 0:
                    empty_pages_count += 1
                    self.log(f"No posts found at offset {offset}. Empty page count: {empty_pages_count}")
                    
                    # If we've seen multiple empty pages in a row, we're probably at the end
                    if empty_pages_count >= max_empty_pages:
                        self.log(f"Found {max_empty_pages} consecutive empty pages. Scraping complete.")
                        break
                        
                    # Try the next page even if this one was empty
                    offset += 10  # Increment by a reasonable default number
                    self.current_offset = offset
                    continue
                else:
                    # Reset empty pages counter if we found posts
                    empty_pages_count = 0
                
                # Scrape each post
                for post in posts:
                    post_data = self.scrape_post(post["url"])
                    if post_data:
                        self.all_data["posts"].append(post_data)
                        posts_since_last_save += 1
                        total_new_posts += 1
                        
                        # Update progress bar
                        if self.progress_bar is not None:
                            self.progress_bar.update(1)
                        
                        # Save progress periodically
                        if posts_since_last_save >= batch_save:
                            self.save_all_data()
                            self.save_progress()
                            posts_since_last_save = 0
                            self.log(f"Progress saved. Total posts: {len(self.all_data['posts'])}")
                    
                    # Be nice to the server
                    time.sleep(self.delay)
                
                # Even if all posts were already scraped, move to the next page
                # Determine how much to increment offset based on total_posts_on_page
                # If we found posts on this page, increment by that amount
                if total_posts_on_page > 0:
                    offset += total_posts_on_page
                else:
                    # Default increment if no posts were found
                    offset += 10
                    
                self.current_offset = offset
                self.log(f"Moving to offset {offset}")
                
                # Save progress after each page
                self.save_progress()
                
        except Exception as e:
            error_msg = f"Error during unlimited scraping: {e}"
            if self.show_progress and self.progress_bar is not None:
                self.progress_bar.write(error_msg)
            else:
                self.log(error_msg)
            
        finally:
            # Save all data and progress before exiting
            self.save_all_data()
            self.save_progress()
            
            # Close progress bar if active
            if self.progress_bar is not None:
                self.progress_bar.close()
                self.progress_bar = None
            
        self.log(f"Scraping complete. Added {total_new_posts} new posts. Total posts: {len(self.all_data['posts'])}")
        return len(self.all_data["posts"])
    
    def scrape_specific_post(self, post_url):
        """Scrape a specific post URL and add to the all_data collection"""
        post_data = self.scrape_post(post_url)
        if post_data:
            self.all_data["posts"].append(post_data)
            self.save_all_data()
            self.save_progress()
            return True
        return False

def main():
    parser = argparse.ArgumentParser(description='Scrape LessWrong posts from GreaterWrong')
    parser.add_argument('--url', type=str, help='Specific post URL to scrape')
    parser.add_argument('--output-dir', type=str, default='.', help='Directory to save scraped data (default: current directory)')
    parser.add_argument('--output-file', type=str, default='lesswrong_all_data.json', help='File to save all data to')
    parser.add_argument('--log-file', type=str, default='scraper_progress.json', help='File to save progress information')
    parser.add_argument('--delay', type=float, default=2, help='Delay between requests in seconds')
    parser.add_argument('--quiet', action='store_true', help='Disable verbose output')
    parser.add_argument('--batch-save', type=int, default=20, help='Save progress after every N posts')
    parser.add_argument('--start-offset', type=int, help='Override the starting offset')
    parser.add_argument('--no-progress', action='store_true', help='Disable progress bar')
    parser.add_argument('--max-offset', type=int, help='Maximum offset to scrape (optional, for testing)')
    
    args = parser.parse_args()
    
    scraper = LessWrongScraper(
        output_dir=args.output_dir,
        delay=args.delay,
        verbose=not args.quiet,
        output_file=args.output_file,
        log_file=args.log_file,
        show_progress=not args.no_progress
    )
    
    # Detect if URL is a specific post
    if args.url and "/posts/" in args.url:
        result = scraper.scrape_specific_post(args.url)
        if result:
            print(f"Successfully scraped post and added to {args.output_file}")
        else:
            print("Failed to scrape post")
    else:
        # Run unlimited scraping
        total_posts = scraper.run_unlimited(
            batch_save=args.batch_save, 
            start_offset=args.start_offset,
            max_offset=args.max_offset
        )
        print(f"Successfully scraped {total_posts} total posts to {args.output_file}")

if __name__ == "__main__":
    main() 