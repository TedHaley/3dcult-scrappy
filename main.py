import requests
import json
from bson import json_util
from bs4 import BeautifulSoup
import re
import datetime
import logging
import hashlib
import os

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)


def error_handler(func):
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            raise e
    return inner


def get_most_liked_links(most_liked_stl_url):
    logging.info(f'Getting item links from: {most_liked_stl_url}')
    most_liked_stl_res = requests.get(most_liked_stl_url)
    most_liked_stl_xml = most_liked_stl_res.text
    soup = BeautifulSoup(most_liked_stl_xml, 'html.parser')
    links_soup = soup.find_all('guid')
    links = [i.contents[0] for i in links_soup]
    return links


def get_item_downloads(soup, d):
    spans = soup.find_all("span")
    for parent_span in spans:
        text_spans = parent_span.find_all("span", {'data-counter-target': 'text'})
        for text_span in text_spans:
            if 'downloads' == text_span.get_text(strip=True) or 'download' == text_span.get_text(strip=True):
                number_span = parent_span.find("span", {'data-counter-target': 'number'})
                downloads = int(number_span.get_text(strip=True))
                d['item_downloads'] = downloads
                break
    return d


def get_item_price(soup, d):
    raw_price = soup.find('span', class_='btn--breathing btn-group-end btn-third').get_text(strip=True)
    d['item_price_raw'] = raw_price

    if raw_price == 'Free':
        d['item_price'] = 0
        d['item_currency'] = None
        return d

    item_price_str = re.findall("[-+]?[.]?[\d]+(?:,\d\d\d)*[\.]?\d*(?:[eE][-+]?\d+)?", raw_price)[0]
    item_price_float = float(item_price_str)
    item_currency = raw_price.replace(item_price_str, '')

    d['item_price'] = item_price_float
    d['item_currency'] = item_currency

    return d


def get_text(soup, d):
    title = soup.find("meta", property="og:title")["content"]
    tags = soup.find_all('a', class_="btn btn-second btn--max-size")
    tag_names = [i.contents[0] for i in tags]
    d['title'] = title
    d['tags'] = tag_names
    return d


def total_item_revenue(item_downloads, item_price):
    return {'total_item_revenue': item_downloads['item_downloads'] * item_price['item_price']}


@error_handler
def link_data(link):
    logging.info(f'Processing link: {link}')
    link_res = requests.get(link)
    item_text = link_res.text
    soup = BeautifulSoup(item_text, 'html.parser')
    item_record = {'item_url': link}
    item_text = get_text(soup=soup, d={'title': '', 'tags': []})
    item_downloads = get_item_downloads(soup=soup, d={'item_downloads': 0})
    item_price = get_item_price(soup=soup, d={'item_price_raw': '', 'item_price': 0, 'item_currency': ''})
    item_revenue = total_item_revenue(item_downloads, item_price)
    record_time = {'record_time': datetime.datetime.utcnow()}
    full_record = {**item_record, **item_text, **item_downloads, **item_price, **record_time, **item_revenue}
    return full_record


def record_name(link):
    encoded_link = link.encode('utf-8')
    hash_object = hashlib.md5(encoded_link)
    hash_str = hash_object.hexdigest()
    year_month = datetime.datetime.now().strftime("%Y_%m")
    file_name = f'{hash_str}_{year_month}.json'
    return file_name


def check_record_exists(record_path):
    if bool(os.path.exists(record_path)):
        logging.info(f'{record_path} already exists. Skipping...')
        return True
    return False


def save_record(record_dict, record_path):
    logging.info(f'Saving record: {record_path}')
    with open(record_path, 'w') as outfile:
        json.dump(record_dict, outfile, indent=4, default=json_util.default)


def iterate_items_on_page(page_url):
    logging.info(f"Parsing items on page: {page_url}")
    item_links = get_most_liked_links(page_url)
    for link in item_links:
        name = record_name(link=link)
        record_path = f'./data/{name}'
        if not check_record_exists(record_path):
            record = link_data(link=link)
            save_record(record_dict=record, record_path=record_path)


def verify_page(url):
    res = requests.get(url)
    if 200 <= res.status_code < 300:
        return True
    return False


def iterate_pages():
    root = 'https://cults3d.com/en/creations/popular/page/'
    page_number = 1
    while True:
        page = root + str(page_number)
        if verify_page(page):
            iterate_items_on_page(page)
            page_number += 1
            continue
        break


if __name__ == "__main__":
    iterate_pages()
