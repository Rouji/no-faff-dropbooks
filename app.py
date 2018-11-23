#!/usr/bin/env python3
# coding=utf-8

from flask import Flask, jsonify, abort, make_response, request, render_template
from flask_cache import Cache
import requests
import re
from bs4 import BeautifulSoup

user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X x.y; rv:10.0) Gecko/20100101 Firefox/10.0'
url_re = re.compile(r'http://.*\.(drop|dl|x)books\.to/.*\.jpe?g')

app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

@app.route('/api/page/<int:page>', defaults={'search': None})
@app.route('/api/page/<int:page>/<search>')
@cache.memoize(timeout=600)
def api_page(page, search):
    url = 'http://xbooks.to/tops/index/term:no/page:{page}'
    if search:
        url = 'http://xbooks.to/search/index/word:{search}/term:no/option_word:/search_type:and/page:{page}'
    url = url.format(page=page, search=search)

    req = requests.get(url, headers={'Referer': 'https://xbooks.to/', 'User-Agent': user_agent})
    soup = BeautifulSoup(req.text, 'lxml')
    books = []
    for link in soup('a'):
        if 'detail' not in link['href']:
            continue
        book_id = link['href'].split('/')[-1]
        book_img = link('img')
        if not book_id or len(book_img) < 1:
            continue

        books.append({'id': book_id, 'thumb': book_img[0]['src'], 'title': book_img[0]['alt']})
    return jsonify(books)

@app.route('/api/detail/<book_id>')
@cache.memoize(timeout=3600)
def api_detail(book_id):
    url = 'http://xbooks.to/detail/{book_id}'.format(book_id=book_id)
    req = requests.get(url, headers={'Referer': 'https://xbooks.to/', 'User-Agent': user_agent})
    soup = BeautifulSoup(req.text, 'lxml')
    title = soup('h2')
    title = title[0] if len(title) > 0 else None
    if title:
        try:
            title('span')[0].extract()
        except:
            pass
        title = title.text.strip()
    dl_link = next((l['href'] for l in soup('a') if 'download_zip' in l['href']), None)
    if dl_link:
        dl_link = 'http://xbooks.to' + dl_link

    thumb1 = soup.select('img#thumbnail1')[0]['src']
    img_base = thumb1.rsplit('/', 1)[0] + '/'
    images = [
        {'idx': i, 'img': img_base + str(i).zfill(5) + '.jpg', 'thumb': thumb}
        for i, thumb in enumerate([t['src'] for t in soup.select('img.lazy')],start=1)
    ]
    return jsonify({'title': title, 'dl_link': dl_link, 'images': images})

def img_key():
    url = request.values.get('url')
    if '/thumb' in url:
        return url.split('/')[-1]
    elif '/img/' in url:
        return '/'.join(url.split('/')[-2:])

@app.route('/api/img')
@cache.cached(timeout=1800, key_prefix=img_key)
def api_img():
    img_url = request.values.get('url')
    if not img_url or not url_re.match(img_url):
        abort(403)
    req = requests.get(img_url, headers={'Referer': 'https://xbooks.to/', 'User-Agent': user_agent})
    resp = make_response(req.content)
    resp.headers.set('Content-Type', 'image/jpeg')
    return resp


@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/detail/<book_id>')
def detail(book_id):
    return render_template('detail.html', book_id=book_id)

if __name__ == '__main__':
    app.run()
