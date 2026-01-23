from typing import Optional
import logging
import httpx
import re
from bs4 import BeautifulSoup
from app.domain.models.tool_result import ToolResult
from app.domain.models.search import SearchResults, SearchResultItem
from app.domain.external.search import SearchEngine

logger = logging.getLogger(__name__)

class BingSearchEngine(SearchEngine):
    """Bing web search engine implementation using web scraping"""
    
    def __init__(self):
        """Initialize Bing search engine"""
        self.base_url = "https://cn.bing.com/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        # Initialize cookies to maintain session state
        self.cookies = httpx.Cookies()
        
    async def search(
        self, 
        query: str, 
        date_range: Optional[str] = None
    ) -> ToolResult[SearchResults]:
        """Search web pages using Bing web search
        
        Args:
            query: Search query, using 3-5 keywords
            date_range: (Optional) Time range filter for search results
            
        Returns:
            Search results
        """
        params = {
            "q": query,
            "rdr": "1",
        }
        
        # Add time range filter
        # NOTE: Bing's query filters are fragile and vary by region. Avoid sending
        # the previously used incorrect URL-encoded strings. If a supported
        # mapping is known, it can be added here. For now we log and ignore
        # unsupported date_range values to avoid malformed queries.
        # if date_range and date_range != "all":
        #     date_mapping = {
        #         # Placeholder mappings — keep conservative and do not inject
        #         # malformed encoded strings. These entries are informational
        #         # and currently not appended to the request to avoid errors.
        #         "past_hour": None,
        #         "past_day": None,
        #         "past_week": None,
        #         "past_month": None,
        #         "past_year": None,
        #     }
        #     if date_range in date_mapping and date_mapping[date_range] is not None:
        #         params.update(date_mapping[date_range])
        #     else:
        #         logger.debug(f"Date range filter '{date_range}' not applied — unsupported or unsafe to add to params")
        
        try:
            async with httpx.AsyncClient(headers=self.headers, cookies=self.cookies, timeout=30.0, follow_redirects=True) as client:
                # Log request for debugging (safe: do not log full query text in prod)
                logger.info(f"Bing search request params: {params}")
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                
                # Update cookies with response cookies in memory
                self.cookies.update(response.cookies)
                
                # logger.info(f"===>Bing search response: \n\n{response.text}\n\n")
                
                # Parse HTML content
                soup = BeautifulSoup(response.text, 'html.parser')

                # Detect potential anti-bot / captcha pages and return a clear error
                page_text = soup.get_text(separator=" ", strip=True)
                anti_bot_indicators = [
                    'unusual traffic',
                    'detected unusual traffic',
                    "please verify you're a human",
                    '验证码',
                    '检测到异常',
                    '访问受限',
                ]
                if any(indicator.lower() in page_text.lower() for indicator in anti_bot_indicators):
                    logger.error('Bing returned anti-bot or captcha page; aborting search')
                    error_results = SearchResults(query=query, date_range=date_range, total_results=0, results=[])
                    return ToolResult(success=False, message='Bing blocked the request or returned a captcha page', data=error_results)

                # Debug: record status, final URL and small snippet of HTML for troubleshooting
                logger.info(f"Bing response status: {response.status_code}; url: {response.url}; content length: {len(response.text)}")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Bing response snippet: {response.text[:2000]}")
                
                # Extract search results
                search_results = []
                
                # Bing search results commonly appear in `li.b_algo`, but DOM
                # varies. Try several fallbacks to increase robustness.
                result_items = soup.find_all('li', class_='b_algo')
                if not result_items:
                    # try div with b_algo class
                    result_items = soup.find_all('div', class_=re.compile(r'b_algo'))
                if not result_items:
                    # broader fallback: any element whose class contains 'algo' or 'result'
                    result_items = soup.find_all(lambda tag: tag.get('class') and any(re.search(r'(algo|result|b_algo)', c) for c in tag.get('class')))
                
                for item in result_items:
                    try:
                        # Extract title and link
                        title = ""
                        link = ""
                        
                        # Title is usually in h2 > a
                        title_tag = item.find('h2')
                        if title_tag:
                            title_a = title_tag.find('a')
                            if title_a:
                                title = title_a.get_text(strip=True)
                                link = title_a.get('href', '')
                        
                        # If not found, try other structures — accept shorter titles
                        if not title:
                            title_links = item.find_all('a')
                            for a in title_links:
                                text = a.get_text(strip=True)
                                # Accept reasonable-length text as title
                                if len(text) > 6:
                                    title = text
                                    link = a.get('href', '')
                                    break
                        
                        if not title:
                            continue
                        
                        # Extract snippet
                        snippet = ""
                        
                        # Look for description in p/div with known classes first
                        snippet_tags = item.find_all(['p', 'div'], class_=re.compile(r'b_lineclamp|b_descript|b_caption'))
                        if snippet_tags:
                            snippet = snippet_tags[0].get_text(strip=True)

                        # If not found, look for any p tag with reasonable text
                        if not snippet:
                            all_p_tags = item.find_all('p')
                            for p in all_p_tags:
                                text = p.get_text(strip=True)
                                if len(text) > 10:
                                    snippet = text
                                    break
                        
                        # If still not found, get any substantial text from the item
                        if not snippet:
                            all_text = item.get_text(strip=True)
                            # Extract first sentence-like text that's not the title
                            sentences = re.split(r'[.!?\n]', all_text)
                            for sentence in sentences:
                                clean_sentence = sentence.strip()
                                if len(clean_sentence) > 10 and clean_sentence != title:
                                    snippet = clean_sentence
                                    break
                        
                        # Clean up link if needed
                        if link and not link.startswith('http'):
                            if link.startswith('//'):
                                link = 'https:' + link
                            elif link.startswith('/'):
                                link = 'https://www.bing.com' + link
                        
                        if title and link:
                            search_results.append(SearchResultItem(
                                title=title,
                                link=link,
                                snippet=snippet
                            ))
                    except Exception as e:
                        logger.warning(f"Failed to parse Bing search result: {e}")
                        continue
                
                # Extract total results count (support multiple locales)
                total_results = 0
                # Common English patterns
                result_stats = soup.find_all(string=re.compile(r'\d+[,\d]*\s*results?', re.I))
                if result_stats:
                    for stat in result_stats:
                        match = re.search(r'([\d,]+)\s*results?', stat, re.I)
                        if match:
                            try:
                                total_results = int(match.group(1).replace(',', ''))
                                break
                            except ValueError:
                                continue

                # Chinese / other locale patterns (e.g., "约 1,234 条结果", "1,234 条")
                if total_results == 0:
                    count_strings = soup.find_all(string=re.compile(r'(约\s*)?[\d,，]+\s*(条|条结果|结果)', re.I))
                    for stat in count_strings:
                        match = re.search(r'([\d,，]+)', stat)
                        if match:
                            num = match.group(1).replace('，', '').replace(',', '')
                            try:
                                total_results = int(num)
                                break
                            except ValueError:
                                continue

                # Also try looking in elements with specific count classes
                if total_results == 0:
                    count_elements = soup.find_all(['span', 'div'], class_=re.compile(r'sb_count|b_focusTextMedium', re.I))
                    for elem in count_elements:
                        text = elem.get_text()
                        match = re.search(r'([\d,，]+)', text)
                        if match:
                            num = match.group(1).replace('，', '').replace(',', '')
                            try:
                                total_results = int(num)
                                break
                            except ValueError:
                                continue
                
                # Build return result
                results = SearchResults(
                    query=query,
                    date_range=date_range,
                    total_results=total_results,
                    results=search_results
                )
                
                logger.info(f"===>Bing Search completed: found {len(search_results)} results for query '{query}'")
                logger.info(f"===>Search Results: {results.json()}")
                
                return ToolResult(success=True, data=results)
                
        except Exception as e:
            logger.error(f"Bing Search failed: {e}")
            error_results = SearchResults(
                query=query,
                date_range=date_range,
                total_results=0,
                results=[]
            )
            
            return ToolResult(
                success=False,
                message=f"Bing Search failed: {e}",
                data=error_results
            )


# Simple test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        search_engine = BingSearchEngine()
        result = await search_engine.search("Python programming")
        
        if result.success:
            print(f"Search successful! Found {len(result.data.results)} results")
            for i, item in enumerate(result.data.results[:3]):
                print(f"{i+1}. {item.title}")
                print(f"   {item.link}")
                print(f"   {item.snippet}")
                print()
        else:
            print(f"Search failed: {result.message}")
    
    asyncio.run(test())
