"""
Test script for Firecrawl integration in qlik-py-tools.
Tests scrape, extract, and search against real competitor URLs.
"""
import os
import sys
import json
import time

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Add core to path (same as the SSE does)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'generated'))

from _firecrawl import FirecrawlForQlik

# ============================================================
# Test URLs from the customer's competitor database
# ============================================================
COMPETITOR_URLS = {
    "BestDrive": "https://bestdrive.co.za",
    "Tiger Wheel & Tyre": "https://twt.co.za/tyres-by-size",
    "Hi-Q": "https://www.hiq.co.za",
    "Tyre Box": "https://tyrebox.co.za/collections/truck-bus-tyres",
    "FundiTyres": "https://www.fundityres.co.za/tyre-brands/tyre-size/315-80r22-5",
    "Shortys Group": "https://shortysgroup.co.za",
}

# Social media URLs (may have limited scraping due to auth walls)
SOCIAL_URLS = {
    "3G Tyres FB": "https://www.facebook.com/3Gtyres",
    "Supa Quick IG": "https://instagram.com/supaquick",
}


def print_header(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(name, content, max_chars=500):
    print(f"\n--- {name} ---")
    if content:
        preview = content[:max_chars]
        if len(content) > max_chars:
            preview += f"\n... [{len(content)} total chars]"
        print(preview)
    else:
        print("(empty response)")


def test_direct_firecrawl_sdk():
    """Test 1: Direct Firecrawl SDK — verify the API key works."""
    print_header("TEST 1: Direct Firecrawl SDK Connection")

    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        print("SKIP: FIRECRAWL_API_KEY not found in .env")
        return False

    print(f"API key found: {api_key[:8]}...{api_key[-4:]}")

    from firecrawl import Firecrawl
    client = Firecrawl(api_key=api_key)

    # Simple scrape test
    print("\nScraping https://bestdrive.co.za ...")
    try:
        result = client.scrape("https://bestdrive.co.za", formats=["markdown"])
        if hasattr(result, 'markdown'):
            content = result.markdown
        elif isinstance(result, dict):
            content = result.get('markdown', str(result))
        else:
            content = str(result)

        print_result("BestDrive (direct SDK)", content)
        print("\n✅ Direct SDK test PASSED")
        return True
    except Exception as e:
        print(f"\n❌ Direct SDK test FAILED: {e}")
        return False


def test_scrape_websites():
    """Test 2: Scrape competitor websites using FirecrawlForQlik._scrape_url()."""
    print_header("TEST 2: Scrape Competitor Websites")

    # Create a minimal FirecrawlForQlik instance (bypassing gRPC request parsing)
    fc = FirecrawlForQlik.__new__(FirecrawlForQlik)
    fc.debug = False
    fc.logfile = None
    fc.kwargs = {}

    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if api_key:
        from firecrawl import Firecrawl
        fc.client = Firecrawl(api_key=api_key)
    else:
        print("SKIP: No API key")
        return

    # Set default params
    fc.format = 'markdown'
    fc.only_main_content = True
    fc.timeout = None
    fc.pdf_mode = None
    fc.pdf_max_pages = None

    results = {}
    for name, url in COMPETITOR_URLS.items():
        print(f"\nScraping {name}: {url}")
        try:
            start = time.time()
            content = fc._scrape_url(url)
            elapsed = time.time() - start
            results[name] = content
            print_result(name, content, max_chars=300)
            print(f"  ⏱  {elapsed:.1f}s | {len(content)} chars")
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results[name] = None

    passed = sum(1 for v in results.values() if v and len(v) > 50)
    print(f"\n{'✅' if passed > 0 else '❌'} Scraped {passed}/{len(COMPETITOR_URLS)} websites successfully")
    return results


def test_extract_pricing():
    """Test 3: Extract structured pricing data from a website with pricing."""
    print_header("TEST 3: Extract Structured Pricing Data")

    fc = FirecrawlForQlik.__new__(FirecrawlForQlik)
    fc.debug = False
    fc.logfile = None
    fc.kwargs = {}

    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if api_key:
        from firecrawl import Firecrawl
        fc.client = Firecrawl(api_key=api_key)
    else:
        print("SKIP: No API key")
        return

    fc.schema = None
    fc.enable_web_search = False
    fc.pdf_mode = None
    fc.pdf_max_pages = None

    # Test URLs with known pricing data
    test_cases = [
        (
            "FundiTyres",
            "https://www.fundityres.co.za/tyre-brands/tyre-size/315-80r22-5",
            "Extract all tyre product names, brands, sizes, and prices listed on this page."
        ),
        (
            "Tyre Box",
            "https://tyrebox.co.za/collections/truck-bus-tyres",
            "Extract all tyre product names, sizes, and prices listed on this page."
        ),
    ]

    for name, url, prompt in test_cases:
        print(f"\nExtracting from {name}: {url}")
        print(f"Prompt: {prompt}")

        try:
            start = time.time()
            result = fc._extract_from_url(url, prompt)
            elapsed = time.time() - start
            print_result(f"{name} Extract", result, max_chars=1500)
            print(f"  ⏱  {elapsed:.1f}s")

            # Try parsing as JSON
            try:
                data = json.loads(result)
                if isinstance(data, list):
                    print(f"  ✅ Valid JSON array with {len(data)} items")
                elif isinstance(data, dict):
                    print(f"  ✅ Valid JSON object with keys: {list(data.keys())[:5]}")
                else:
                    print(f"  ✅ Valid JSON")
            except json.JSONDecodeError:
                print(f"  ⚠️  Response is not valid JSON")
        except Exception as e:
            print(f"  ❌ Extract failed: {e}")


def test_search():
    """Test 4: Web search for competitor pricing."""
    print_header("TEST 4: Web Search")

    fc = FirecrawlForQlik.__new__(FirecrawlForQlik)
    fc.debug = False
    fc.logfile = None
    fc.kwargs = {}

    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if api_key:
        from firecrawl import Firecrawl
        fc.client = Firecrawl(api_key=api_key)
    else:
        print("SKIP: No API key")
        return

    fc.search_limit = 5
    fc.location = 'South Africa'
    fc.tbs = None
    fc.scrape_content = False

    query = "truck tyre prices South Africa 315/80R22.5"
    print(f"\nSearching: '{query}'")

    try:
        start = time.time()
        result = fc._search_web(query)
        elapsed = time.time() - start
        print_result("Search Results", result, max_chars=1500)
        print(f"  ⏱  {elapsed:.1f}s")

        try:
            data = json.loads(result)
            if isinstance(data, list):
                print(f"  ✅ Got {len(data)} search results")
            else:
                print(f"  ✅ Got search results (object)")
        except json.JSONDecodeError:
            print(f"  ⚠️  Response not JSON")
    except Exception as e:
        print(f"  ❌ Search failed: {e}")


def test_social_media():
    """Test 5: Try scraping social media (may be limited)."""
    print_header("TEST 5: Social Media Scraping (may be limited)")

    fc = FirecrawlForQlik.__new__(FirecrawlForQlik)
    fc.debug = False
    fc.logfile = None
    fc.kwargs = {}

    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if api_key:
        from firecrawl import Firecrawl
        fc.client = Firecrawl(api_key=api_key)
    else:
        print("SKIP: No API key")
        return

    fc.format = 'markdown'
    fc.only_main_content = True
    fc.timeout = None
    fc.pdf_mode = None
    fc.pdf_max_pages = None

    for name, url in SOCIAL_URLS.items():
        print(f"\nScraping {name}: {url}")
        try:
            start = time.time()
            content = fc._scrape_url(url)
            elapsed = time.time() - start
            print_result(name, content, max_chars=300)
            print(f"  ⏱  {elapsed:.1f}s | {len(content)} chars")
        except Exception as e:
            print(f"  ⚠️  {e} (social media often requires auth)")


if __name__ == "__main__":
    print("=" * 70)
    print("  Firecrawl Integration Test Suite")
    print("  qlik-py-tools SSE")
    print("=" * 70)

    # Run tests sequentially
    sdk_ok = test_direct_firecrawl_sdk()

    if sdk_ok:
        test_scrape_websites()
        test_extract_pricing()
        test_search()
        test_social_media()
    else:
        print("\n⚠️  Skipping remaining tests — SDK connection failed")

    print("\n" + "=" * 70)
    print("  Tests Complete")
    print("=" * 70)
