import scrapy


class ManheimSpider(scrapy.Spider):
    name = 'manheim'
    allowed_domains = ['manheim.com']
    start_urls = ['http://manheim.com/']

    def parse(self, response):
        pass
