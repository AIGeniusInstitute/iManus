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
            # 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            # 增强中文语境标识
            'Referer': 'https://www.bing.com/',
            'DNT': '1',
            "Cookie": "MUID=1FEFFAC1218D606613B4E86E258D6609; MUIDB=1FEFFAC1218D606613B4E86E258D6609; SRCHD=AF=CHROMN; SRCHUID=V=2&GUID=2F3595FAE88E440599D6689FF0ECE3D1&dmnchg=1; _Rwho=u=d&ts=2026-01-23; _FP=hta=on; _UR=QS=0&TQS=0&Pn=0; BFBUSR=BFBHP=0; BFPRResults=FirstPageUrls=DEA1E832374B86232FB7C40343F01C2C%2CEF905FAA8FBD8FB13A8BB9950FE3B583%2C790117C36F5F5C884BA0CF0B62A8A6A8%2C1E0E1B75C7D962CE4A0D21C83ADD66CD%2C41B90746D8C64D5158E18F82F50FB6A9%2CD136822584726EFF8E29B5829E89C729%2C3873E9956AC618D38415AEEC29F2B748%2C39621F5FB96DDFB0E0B6806D79C959C7%2C0E3356509729D58E327E1FCAE4251FC1%2C5D28199CB763A1AB830C82C1E721607F&FPIG=7EC6E997E658457A8E4EFBBF65E83DC2; MMCASM=ID=6AA5C31AA98A4003AE28BDCC8C023BF0; _U=1-2V_JzakDtqSztKgLEECO1R9XHMEhoueEqgelpBoUxyrFTLpFIIK9obxBl-i04TqP-60evkhkvf60JI8h5kEreizgaAgBacwj1H6XWw-VHAsQWIHiD2Y9sJvJSDbbwQdYYRXPA7nHVy13EH0JYAqKSSMUAKS2c27QPNbpyDUsEz5l1Rr2AKt9u-PHZhLvfSEbHpp7ZmqaB56aJ3QofaFxM9jtloFbu2S4bHU9H2eisI; ANON=A=2603708484E3666768D4DC41FFFFFFFF; WLS=C=abb4c32f1ce99e87&N=guangjian; SRCHUSR=DOB=20260123&DS=1&POEX=W; _EDGE_S=ui=zh-cn&SID=375BDA801D906A443A5FCC6C1CD36BDB; ENSEARCH=BENVER=0; _SS=PC=U316&SID=2CACFEE2B1B66C020D7EE808B0FC6DCE&R=432&RB=432&GB=0&RG=0&RP=432; ipv6=hit=1769377950331&t=4; SNRHOP=I=&TS=; _HPVN=CS=eyJQbiI6eyJDbiI6MywiU3QiOjAsIlFzIjowLCJQcm9kIjoiUCJ9LCJTYyI6eyJDbiI6MywiU3QiOjAsIlFzIjowLCJQcm9kIjoiSCJ9LCJReiI6eyJDbiI6MywiU3QiOjAsIlFzIjowLCJQcm9kIjoiVCJ9LCJBcCI6dHJ1ZSwiTXV0ZSI6dHJ1ZSwiTGFkIjoiMjAyNi0wMS0yNVQwMDowMDowMFoiLCJJb3RkIjowLCJHd2IiOjAsIlRucyI6MCwiRGZ0IjpudWxsLCJNdnMiOjAsIkZsdCI6MCwiSW1wIjoxMDgsIlRvYm4iOjB9; USRLOC=HS=1&ELOC=LAT=30.23801040649414|LON=119.92857360839844|N=%E4%BD%99%E6%9D%AD%E5%8C%BA%EF%BC%8C%E6%B5%99%E6%B1%9F%E7%9C%81|ELT=6|; _C_ETH=1; _RwBf=r=0&ilt=79&ihpd=2&ispd=34&rc=432&rb=432&rg=0&pc=432&mtu=0&rbb=0.0&clo=0&v=68&l=2026-01-25T08:00:00.0000000Z&lft=0001-01-01T00:00:00.0000000&aof=0&ard=0001-01-01T00:00:00.0000000&rwdbt=1683274769&rwflt=1683274288&rwaul2=0&g=newLevel1&o=0&p=bingcopilotwaitlist&c=MY00IA&t=2102&s=2023-02-12T13:07:18.3502621+00:00&ts=2026-01-25T20:54:54.2530659+00:00&rwred=0&wls=0&wlb=0&wle=1&ccp=2&cpt=0&lka=0&lkt=0&aad=0&TH=&cid=0&gb=2025w20_c&mta=0&e=vmMRZeYHvkXLbGV2i6YakK3tqRW-UQY-2Ojm-eR6fAa3wlPK-QrQOkC7GQVyK_FV5lmb4fjGXvOuyW6o1fxzMSVpjTuTIEMu0dXYlQ1DOnA; dsc=order=BingPages; SRCHHPGUSR=SRCHLANG=zh-Hans&BZA=0&PREFCOL=0&BRW=N&BRH=T&CW=1185&CH=1292&SCW=1170&SCH=3358&DPR=1.0&UTC=480&B=0&HV=1769374496&HVE=CfDJ8HAK7eZCYw5BifHFeUHnkJFJevRMUHRpgd1-jy5mkCDTmPyYlBzOtcXIjbUv0X8ScuoQJvUwUl-Kria0wOUeqyDSF14NrY74pPaTiLBhYlieaLVLrTRLazwz6_5XXIuAtpIWvlFRePnIAmEhgzrJMGQsLnck2d7WHRbbHw7PX3Ls8Qbu7gSWA7BIE4jt88jCJA&PRVCW=1185&PRVCH=1292&IG=CE7D0BEA21DC4D3299626E841E7EE4AA&EXLTT=13"
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
            query: Search query, using 1-3 keywords (support Chinese with space separator)
            date_range: (Optional) Time range filter for search results

        Returns:
            Search results
        """

        # Prepare query parameters
        
        # query 中的空格替换为加号，符合Bing搜索习惯
        query = query.replace(' ', '+')
         
        params = {
            "q": query,  # 直接传入原始字符串，httpx 会负责编码
            "FORM": "QBLH",  # 模拟Bing常规搜索表单类型
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