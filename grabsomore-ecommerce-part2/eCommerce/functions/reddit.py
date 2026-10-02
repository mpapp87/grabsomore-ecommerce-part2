"""Retrieve public Reddit discussions without interrupting the shop on failure."""

import requests


def get_reddit_posts(subreddit="BuyItForLife", limit=10):
    """Return titles, authors and original discussion URLs from Reddit JSON.

    Return an empty list for HTTP/network errors or malformed payloads. Use the
    discussion permalink rather than the external article/image linked by a post.
    """
    url = f"https://www.reddit.com/r/{subreddit}/.json"
    headers = {"User-Agent": "DjangoEcommerceStudentApp/1.0"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return []

    if not isinstance(data, dict) or not isinstance(data.get('data'), dict):
        return []
    children = data['data'].get('children', [])
    if not isinstance(children, list):
        return []
    posts = []
    for item in children[:max(0, limit)]:
        if not isinstance(item, dict) or not isinstance(item.get('data'), dict):
            continue
        post = item['data']
        permalink = post.get('permalink', '')
        if isinstance(permalink, str) and permalink.startswith(('/r/', '/comments/')):
            discussion_url = 'https://www.reddit.com' + permalink
        elif isinstance(post.get('id'), str) and post['id'].isalnum():
            discussion_url = 'https://www.reddit.com/comments/' + post['id'] + '/'
        else:
            continue
        posts.append({
            'title': post.get('title') or 'Untitled',
            'author': post.get('author') or 'unknown',
            'url': discussion_url,
        })
    return posts
