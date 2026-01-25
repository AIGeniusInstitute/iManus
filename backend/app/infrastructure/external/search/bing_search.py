from typing import Optional
import logging
import httpx
import re
from urllib.parse import quote
from bs4 import BeautifulSoup
from app.domain.models.tool_result import ToolResult
from app.domain.models.search import SearchResults, SearchResultItem
from app.domain.external.search import SearchEngine

logger = logging.getLogger(__name__)




# --- Implementation ---

class BingSearchEngine(SearchEngine):
    """Bing web search engine implementation using web scraping"""

    def __init__(self):
        """Initialize Bing search engine with Chinese settings"""
        self.base_url = "https://www.bing.com/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            # 增强中文语境标识
            'Referer': 'https://www.bing.com/',
            'DNT': '1'
        }
        # Initialize cookies to maintain session state
        self.cookies = httpx.Cookies()

    async def search(
            self,
            query: str,
            date_range: Optional[str] = None
    ) -> ToolResult[SearchResults]:
        """Search web pages using Bing web search (optimized for Chinese)

        Args:
            query: Search query, using 3-5 keywords (support Chinese with space separator)
            date_range: (Optional) Time range filter for search results

        Returns:
            Search results
        """
        # BUGFIX 修复核心:
        # 移除了 quote(query)，直接使用原始 query。
        # httpx 会自动处理 UTF-8 编码和 URL 特殊字符转义。
        # 如果手动 quote 会导致双重编码 (如 %E5 -> %25E5)，导致 Bing 收到乱码搜索词。

        params = {
            "q": query,  # 直接传入原始字符串，httpx 会负责编码
            "count": "20",  # Number of results per page
            "first": "1",  # Starting position (1-based)
            "mkt": "zh-CN",  # 关键：指定中文（中国）市场
            "setlang": "zh-CN",  # 关键：指定搜索语言为中文
            "form": "QBRE",  # 模拟Bing常规搜索表单类型
        }

        # Add time range filter
        if date_range and date_range != "all":
            # Convert date_range to time range parameters supported by Bing
            date_mapping = {
                "past_hour": "interval%3d%22Hour%22",
                "past_day": "interval%3d%22Day%22",
                "past_week": "interval%3d%22Week%22",
                "past_month": "interval%3d%22Month%22",
                "past_year": "interval%3d%22Year%22"
            }
            if date_range in date_mapping:
                params["filters"] = date_mapping[date_range]

        try:
            async with httpx.AsyncClient(
                    headers=self.headers,
                    cookies=self.cookies,
                    timeout=30.0,
                    follow_redirects=True,

            ) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()

                # Update cookies with response cookies in memory
                self.cookies.update(response.cookies)

                # Parse HTML content
                soup = BeautifulSoup(response.text, 'html.parser')

                # Extract search results
                search_results = []

                # Bing search results are in li elements with class 'b_algo' (兼容中文结果的class)
                result_items = soup.find_all('li', class_=['b_algo', 'b_algoGroup'])

                for item in result_items:
                    try:
                        # Extract title and link
                        title = ""
                        link = ""

                        # Title is usually in h2 > a (兼容中文结果的结构)
                        title_tag = item.find('h2')
                        if title_tag:
                            title_a = title_tag.find('a')
                            if title_a:
                                title = title_a.get_text(strip=True)
                                link = title_a.get('href', '')

                        # If not found, try other structures (增强中文结果的解析)
                        if not title:
                            title_links = item.find_all('a', href=re.compile(r'^https?'))
                            for a in title_links:
                                text = a.get_text(strip=True)
                                if len(text) > 10 and not text.startswith('http'):
                                    title = text
                                    link = a.get('href', '')
                                    break

                        if not title:
                            continue

                        # Extract snippet (优化中文摘要解析)
                        snippet = ""

                        # Look for description in p tag with class 'b_lineclamp*' or 'b_descript'
                        snippet_tags = item.find_all(
                            ['p', 'div'],
                            class_=re.compile(r'b_lineclamp\d+|b_descript|b_caption|b_snippet')
                        )
                        if snippet_tags:
                            snippet = snippet_tags[0].get_text(strip=True)

                        # If not found, look for any p tag with substantial text
                        if not snippet:
                            all_p_tags = item.find_all('p')
                            for p in all_p_tags:
                                text = p.get_text(strip=True)
                                if len(text) > 20:
                                    snippet = text
                                    break

                        # If still not found, get any substantial text from the item
                        if not snippet:
                            all_text = item.get_text(strip=True)
                            # Extract first sentence-like text that's not the title (兼容中文标点)
                            sentences = re.split(r'[。！？\n]', all_text)
                            for sentence in sentences:
                                clean_sentence = sentence.strip()
                                if len(clean_sentence) > 20 and clean_sentence != title:
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

                # Extract total results count (优化中文结果数解析)
                total_results = 0
                # Bing shows result count in various places, try to find it
                result_stats = soup.find_all(string=re.compile(r'(\d+[,\d]*)\s*(结果|results?)'))
                if result_stats:
                    for stat in result_stats:
                        match = re.search(r'([\d,]+)\s*(结果|results?)', stat)
                        if match:
                            try:
                                total_results = int(match.group(1).replace(',', ''))
                                break
                            except ValueError:
                                continue

                # Also try looking in the search results count area
                if total_results == 0:
                    count_elements = soup.find_all(['span', 'div'],
                                                   class_=re.compile(r'sb_count|b_focusTextMedium|sb_count_separator'))
                    for elem in count_elements:
                        text = elem.get_text()
                        match = re.search(r'([\d,]+)\s*(结果|results?)', text)
                        if match:
                            try:
                                total_results = int(match.group(1).replace(',', ''))
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