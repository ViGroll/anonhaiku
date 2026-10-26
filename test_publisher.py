import sqlite3
from pathlib import Path
import unittest
from datetime import datetime, timezone, timedelta
from publisher import setup, publish, current_slot, category_scores, safe_to_publish, render, SITE

class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:')
        setup(self.conn)
        self.conn.execute('''INSERT INTO haikus(post_id,thread_id,posted_utc,line1,line2,line3,source_url,start_boundary,end_boundary)
        VALUES (1,1,'2026-10-26T00:00:00Z','the dark night is cold','and my friend has gone away','i am all alone','https://example.test/1',1,1),
        (2,1,'2026-10-26T00:01:00Z','make your hard cock pulse','in my mouth and hands and shoot','cum all over me','https://example.test/2',1,1),
        (3,1,'2026-10-26T00:02:00Z','i moved for a job','fairly far away and got','a dog for safety','https://example.test/3',1,1)''')
        self.conn.commit()
    def tearDown(self): self.conn.close()
    def test_fixed_gmt_plus_one_slots(self):
        utc=timezone.utc
        self.assertEqual(current_slot(datetime(2026,10,26,4,59,tzinfo=utc))[0],'2026-10-25-18')
        self.assertEqual(current_slot(datetime(2026,10,26,5,0,tzinfo=utc))[0],'2026-10-26-06')
        self.assertEqual(current_slot(datetime(2026,10,26,16,59,tzinfo=utc))[0],'2026-10-26-06')
        self.assertEqual(current_slot(datetime(2026,10,26,17,0,tzinfo=utc))[0],'2026-10-26-18')
        # In July Brussels is UTC+2, but publication stays fixed at UTC+1.
        self.assertEqual(current_slot(datetime(2027,7,1,5,0,tzinfo=utc))[0],'2027-07-01-06')
    def test_unique_publication_and_rotation(self):
        z=timezone(timedelta(hours=1))
        for hour,day in ((7,26),(19,26),(7,27)):
            self.assertTrue(publish(self.conn,datetime(2026,10,day,hour,tzinfo=z)))
        self.assertFalse(publish(self.conn,datetime(2026,10,27,7,tzinfo=z)))
        categories=[row[0] for row in self.conn.execute('SELECT category FROM publications ORDER BY slot')]
        self.assertEqual(categories,['vulgar','poetic','unexpected'])
        ids=[row[0] for row in self.conn.execute('SELECT haiku_id FROM publications')]
        self.assertEqual(len(set(ids)),3)
    def test_public_site_hides_category_and_has_footer(self):
        # Rendering after publication must not expose editorial categories.
        from tempfile import TemporaryDirectory
        import publisher
        old_site = publisher.SITE
        with TemporaryDirectory() as temp:
            publisher.SITE = Path(temp)
            try:
                publish(self.conn, datetime(2026,10,26,7,tzinfo=timezone.utc))
                render(self.conn)
                for name in ('index.html', 'archive.html'):
                    html = (Path(temp)/name).read_text(encoding='utf-8')
                    self.assertNotIn('&bull; Vulgar', html)
                    self.assertNotIn('&bull; Poetic', html)
                    self.assertNotIn('&bull; Unexpected', html)
                    self.assertIn("A new haiku every 12 hours. Sorry if it's offensive, blame /b/. Independent project, not affiliated with 4chan.", html)
            finally:
                publisher.SITE = old_site
    def test_explicit_guard(self):
        self.assertFalse(safe_to_publish({'line1':'racial nigger slur','line2':'test','line3':'test'}))

if __name__ == '__main__':unittest.main()
