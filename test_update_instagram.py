import unittest
from unittest.mock import patch
import update_instagram as feed
class FeedTests(unittest.TestCase):
    def row(self,i,t,kind='IMAGE'):
        return {'id':str(i),'timestamp':t,'permalink':'https://www.instagram.com/p/TEST'+str(i)+'/', 'media_type':kind,'media_url':'https://s.cdninstagram.com/image.jpg','thumbnail_url':'https://s.cdninstagram.com/thumbnail.jpg'}
    def test_latest_three(self):
        rows=[self.row(i,'2026-10-0'+str(i)+'T12:00:00+0000') for i in [1,4,2,3]]
        self.assertEqual([r['id'] for r in feed.latest_posts(rows)],['4','3','2'])
    def test_unsafe_link(self):
        r=self.row(1,'2026-10-01T12:00:00+0000');r['permalink']='javascript:alert(1)'
        with self.assertRaises(RuntimeError):feed.latest_posts([r])
    def test_video_thumbnail(self):
        r=self.row(1,'2026-10-01T12:00:00+0000','VIDEO');self.assertEqual(feed.image_url(r),r['thumbnail_url'])
    def test_missing_thumbnail(self):
        with self.assertRaises(RuntimeError):feed.download_image(None)
    def test_untrusted_host(self):
        with self.assertRaises(RuntimeError):feed.download_image('https://example.com/image.jpg')
    def test_no_secrets(self):
        with patch.dict(feed.os.environ,{},clear=True):
            with self.assertRaises(RuntimeError):feed.update()
if __name__=='__main__':unittest.main()
