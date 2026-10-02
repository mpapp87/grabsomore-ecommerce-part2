"""Keep Part 2's original Reddit integration covered by offline tests."""

from unittest.mock import Mock, patch

from django.test import TestCase
from django.urls import reverse

from .functions.reddit import get_reddit_posts


class RedditIntegrationTests(TestCase):
    """Verify the external community feed using mocked network responses."""

    @patch('eCommerce.functions.reddit.requests.get')
    def test_reddit_json_is_parsed(self, mock_get):
        """Verify that reddit json is parsed."""
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            'data': {'children': [{'data': {
                'title': 'Useful product', 'author': 'tester',
                'url': 'https://example.com/external-article',
                'permalink': '/r/test/comments/abc123/useful_product/',
            }}]}
        }
        mock_get.return_value = response
        posts = get_reddit_posts('test', limit=1)
        self.assertEqual(posts[0]['title'], 'Useful product')
        self.assertEqual(posts[0]['author'], 'tester')
        self.assertEqual(posts[0]['url'], 'https://www.reddit.com/r/test/comments/abc123/useful_product/')
        self.assertIn('User-Agent', mock_get.call_args.kwargs['headers'])

    @patch('eCommerce.views.get_reddit_posts')
    def test_reddit_page_renders_posts(self, mock_posts):
        """Verify that reddit page renders posts."""
        mock_posts.return_value = [{
            'title': 'A post', 'author': 'user',
            'url': 'https://example.com',
        }]
        response = self.client.get(reverse('eCommerce:reddit_feed'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'A post')


    @patch('eCommerce.functions.reddit.requests.get')
    def test_http_failure_and_malformed_payload_are_safe(self, mock_get):
        """Handle blocked Reddit requests and unexpected JSON without a server error."""
        import requests
        mock_get.side_effect = requests.HTTPError('403 Forbidden')
        self.assertEqual(get_reddit_posts(), [])
        mock_get.side_effect = None
        for payload in ([], None, {'data': []}, {'data': {'children': None}}, {'data': {'children': [None, {'data': []}]}}):
            mock_get.return_value.json.return_value = payload
            self.assertEqual(get_reddit_posts(), [])

    @patch('eCommerce.functions.reddit.requests.get')
    def test_missing_permalink_uses_discussion_id_not_external_url(self, mock_get):
        """Build a Reddit discussion link from the post ID when necessary."""
        mock_get.return_value.json.return_value = {'data': {'children': [{'data': {'id': 'abc123', 'title': 'Story', 'url': 'https://example.com'}}]}}
        self.assertEqual(get_reddit_posts()[0]['url'], 'https://www.reddit.com/comments/abc123/')
