from scrapy.selector import Selector
from scrapy.http import Request
from time import sleep
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.proxy import Proxy, ProxyType
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.wait import WebDriverWait
from fake_useragent import UserAgent
from jsonpath_ng import jsonpath, parse
import time
import re
import json
import scrapy
import zipfile


class CopartSpider(scrapy.Spider):
    
    name = 'copart'
    # allowed_domains = ['copart.com']
    # start_urls = ['http://copart.com/']

    def __init__(self,*args, **kwargs):
        self.result = dict()
        self.url = 'https://www.copart.com'

    def get_driver(self):
        PROXY_HOST = 'x.botproxy.net'  # rotating proxy or host
        PROXY_PORT = 8080 # port
        PROXY_USER = 'pxu21186-1' # username
        PROXY_PASS = 'okJNkzLyAhrWoqMo9Nfi' # password

        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Chrome Proxy",
            "permissions": [
                "proxy",
                "tabs",
                "unlimitedStorage",
                "storage",
                "<all_urls>",
                "webRequest",
                "webRequestBlocking"
            ],
            "background": {
                "scripts": ["background.js"]
            },
            "minimum_chrome_version":"22.0.0"
        }
        """

        background_js = """
        var config = {
                mode: "fixed_servers",
                rules: {
                singleProxy: {
                    scheme: "http",
                    host: "%s",
                    port: parseInt(%s)
                },
                bypassList: ["localhost"]
                }
            };

        chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});

        function callbackFn(details) {
            return {
                authCredentials: {
                    username: "%s",
                    password: "%s"
                }
            };
        }

        chrome.webRequest.onAuthRequired.addListener(
                    callbackFn,
                    {urls: ["<all_urls>"]},
                    ['blocking']
        );
        """ % (PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS)

        chrome_options = webdriver.ChromeOptions()
        
        pluginfile = 'proxy_auth_plugin.zip'
        with zipfile.ZipFile(pluginfile, 'w') as zp:
            zp.writestr("manifest.json", manifest_json)
            zp.writestr("background.js", background_js)
        chrome_options.add_extension(pluginfile)

        user_agent = UserAgent()        
        chrome_options.add_argument('--user-agent=%s' % user_agent.random)

        driver = webdriver.Chrome(options=chrome_options)
        driver.implicitly_wait(30)

        return driver
        
    def start_requests(self):
        yield Request('https://www.copart.com', callback=self.parse)

    def parse(self, response):
        self.driver = self.get_driver()
        self.driver.get('https://www.copart.com/lotSearchResults/?free=true&query=prius&searchCriteria=%7B%22query%22:%5B%22prius%22%5D,%22filter%22:%7B%22YEAR%22:%5B%22lot_year:%5C%222017%5C%22%22,%22lot_year:%5C%222018%5C%22%22,%22lot_year:%5C%222019%5C%22%22%5D%7D,%22watchListOnly%22:false,%22searchName%22:%22%22,%22freeFormSearch%22:true%7D')

        pagination_count = self.driver.find_element_by_xpath('(//li[@class="paginate_button next"])[1]/preceding-sibling::li[1]')
        result = []
        for i in range(int(pagination_count.text)):
            rows = self.driver.find_elements_by_css_selector('#serverSideDataTable tbody>tr')
            for r in rows:
                r.location_once_scrolled_into_view
                topr = r.find_element_by_css_selector('td:nth-child(2)>div:nth-child(1)')
                if float(''.join(re.findall(r'\d+\.?', topr.get_attribute('bid-string')))) < 15001:
                    result.append({
                        "description": topr.get_attribute('lot-desc').strip(),
                        "bid": topr.get_attribute('bid-string'),
                        "lot_number": topr.get_attribute('lot-id'),
                        "img_url": topr.find_element_by_css_selector('a>img').get_attribute('src'),
                        "sale_date": u' '.join(r.find_element_by_css_selector('td>[data-uname="lotsearchLotauctiondate"]').text.split('\n')),
                        "location": r.find_element_by_css_selector('td [data-uname="lotsearchLotyardname"]').text,
                        "odometer": r.find_element_by_css_selector('td>[data-uname="lotsearchLotodometerreading"]').text,
                        "doc_type": r.find_element_by_css_selector('td>[data-uname="lotsearchSaletitletype"]').text,
                        "damage": r.find_element_by_css_selector('td>[data-uname="lotsearchLotdamagedescription"]').text,
                        "est_retail_value": r.find_element_by_css_selector('td>[data-uname="lotsearchLotestimatedretailvalue"]').text,
                        })
            next_button = self.driver.find_element_by_css_selector('#serverSideDataTable_next>a')
            next_button.click()
            sleep(2)

        with open('json_result.json', 'w') as f:
            json.dump(result, f, indent=4)

        for lot_number in parse('$..lot_number').find(result):
            self.driver.get(f'https://www.copart.com/lot/{lot_number.value}')
            keys = [k.text for k in self.driver.find_elements_by_css_selector('label.left.bold')]
            values = [v.text for v in self.driver.find_elements_by_css_selector('span.lot-details-desc.right')]

            # with open(f'{lot_number.value}.json', 'w') as f:
            #     json.dump(dict(zip(keys, values)), f, indent=4)
            self.logger(json.dumps(dict(zip(keys, values))))

    def close(self, reason):
        self.driver.quit()