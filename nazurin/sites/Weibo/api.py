import json
import os
import re
from typing import List, Tuple

from nazurin.models import Caption, Illust, Image
from nazurin.utils import Request
from nazurin.utils.exceptions import NazurinError

class Weibo(object):
    async def getPost(self, post_id: str):
        """Fetch an post."""
        api = f"https://m.weibo.cn/detail/{post_id}"
        async with Request() as request:
            async with request.get(api) as response:
                if not response.status == 200:
                    raise NazurinError('Post not found')
                html = await response.text()
                post = self.parseHtml(html)
                return post

    async def fetch(self, post_id: str) -> Illust:
        post = await self.getPost(post_id)
        imgs = self.getImages(post)
        caption = self.buildCaption(post)
        return Illust(imgs, caption, post)

    def getImages(self, post) -> List[Image]:
        """Get images from post."""
        if 'pics' not in post.keys():
            raise NazurinError('No image found')
        pics = post['pics']
        mid = post['mid']
        imgs = list()
        for pic in pics:
            filename, url, thumbnail, width, height = self.parsePic(pic)
            imgs.append(
                Image(f"Weibo - {mid} - {filename}",
                      url,
                      thumbnail,
                      width=width,
                      height=height))
        return imgs

    def buildCaption(self, post) -> Caption:
        user = post['user']
        tags = self.getTags(post)
        tag_string = str()
        for tag in tags:
            tag_string += '#' + tag + ' '
        return Caption({
            'title': post['status_title'],
            'author': f"#{user['screen_name']}",
            'desktop_url': f"https://weibo.com/{user['id']}/{post['bid']}",
            'mobile_url': f"https://m.weibo.cn/detail/{post['mid']}",
            'tags': tag_string,
        })

    def getTags(self, post) -> List[str]:
        if 'text' not in post.keys() or not post['text']:
            return []
        regex = r"#(\S+)#"
        matches = re.findall(regex, post['text'], re.MULTILINE)
        if not matches:
            return []
        return matches

    def parsePic(self, pic: dict) -> Tuple[str, str, str, int, int]:
        """Get filename, original file url & thumbnail url of the picture

        eg:
            {
                "pid": "001Y6PUIgy1gvre6rshhbj61iv0zmdlw02",
                "url": "https://wx3.sinaimg.cn/orj360/001Y6PUIgy1gvre6rshhbj61iv0zmdlw02.jpg",
                "size": "orj360",
                "geo": {
                    "width": 415,
                    "height": 270,
                    "croped": false
                },
                "large": {
                    "size": "large",
                    "url": "https://wx3.sinaimg.cn/large/001Y6PUIgy1gvre6rshhbj61iv0zmdlw02.jpg",
                    "geo": {
                        "width": "1975",
                        "height": "1282",
                        "croped": false
                    }
                }
            }

            return:
                '001Y6PUIgy1gvre6rshhbj61iv0zmdlw02.jpg',
                'https://wx3.sinaimg.cn/large/001Y6PUIgy1gvre6rshhbj61iv0zmdlw02.jpg',
                'https://wx3.sinaimg.cn/orj360/001Y6PUIgy1gvre6rshhbj61iv0zmdlw02.jpg',
                1975,
                1282

        """
        thumbnail = pic['url']
        basename = os.path.basename(thumbnail)
        url = pic['large']['url']
        width = int(pic['large']['geo']['width'])
        height = int(pic['large']['geo']['height'])
        return basename, url, thumbnail, width, height

    def parseHtml(self, html) -> dict:
        """
        Extract post data from html <script> block as example below.
        We're lucky the JS objects are written in JSON syntax with quotes wrapped property names.

        <script>
        ...
        var $render_data = [{
            "status": {
                ...
            }, ...
        }][0] || {};
        ...
        </script>
        """
        regex = r"\$render_data = \[\{\n([\s\S]+)\}\]\[0\] \|\| \{\};"
        matches = re.search(regex, html, re.MULTILINE)
        if not matches:
            raise NazurinError('Post not found')
        json_str = '[{' + matches.group(1) + '}]'
        try:
            render_data = json.loads(json_str)
            post = render_data[0]['status']
        except json.JSONDecodeError:
            raise NazurinError('Failed to parse post data') from None
        return post
