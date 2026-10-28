import unittest
import sqlite3
from datetime import datetime,timezone,timedelta
from scanner import eligible,setup
from selection import overlaps,score_comment
from publisher import slot_for,legacy_import,maybe_publish
from site_builder import formatted,post_timestamp,render_poem
class CoreTests(unittest.TestCase):
    def test_digit_attachment(self):
        self.assertFalse(eligible({'com':'I have 7 apples'}))
        self.assertFalse(eligible({'com':'The wind is cold','tim':123}))
        self.assertTrue(eligible({'com':'The wind is cold'}))
    def test_overlap(self):
        self.assertTrue(overlaps(('the moon is bright','a quiet river at night','the earth is asleep'),('the moon is bright','a quiet river at night','a new day begins')))
    def test_display(self):
        self.assertEqual(formatted(('I Am Here','AND THIS IS A TEST','THE END')),['I am here','and this is a test','the end.'])
    def test_publication_timestamp_european(self):
        item={'line1':'ONE TWO','line2':'THREE FOUR','line3':'FIVE SIX',
              'slot':'2026-10-28T17:00:00+00:00','original':'source'}
        output=render_poem(item,show_original=True)
        self.assertIn('18:00 (28/10/26)',output)
        self.assertIn('Original post',output)
        self.assertNotIn('https://boards.4chan.org',output)
    def test_archive_has_no_original_post(self):
        item={'line1':'ONE TWO','line2':'THREE FOUR','line3':'FIVE SIX',
              'slot':'2026-10-28T17:00:00+00:00','original':'source'}
        self.assertNotIn('Original post',render_poem(item,show_original=False))
    def test_european_time_display(self):
        self.assertEqual(post_timestamp({'published_utc':'2026-10-28T17:05:00+00:00'}), '18:05 28/10/26')
        self.assertEqual(post_timestamp({'published_utc':'2026-06-01T05:00:00+00:00'}), '06:00 01/06/26')
    def test_fixed_zone(self):
        self.assertEqual(slot_for(datetime(2026,10,28,16,30,tzinfo=timezone.utc)).hour,5)
        self.assertEqual(slot_for(datetime(2026,10,28,17,30,tzinfo=timezone.utc)).hour,17)
    def test_database(self):
        with sqlite3.connect(':memory:') as conn:
            setup(conn)
            self.assertTrue(conn.execute("SELECT 1 FROM sqlite_master WHERE name='ah_publications'").fetchone())
    def test_no_old_pool(self):
        with sqlite3.connect(':memory:') as conn:
            setup(conn)
            conn.execute('INSERT INTO ah_batches VALUES(1,?,?)',('2020-01-01T00:00:00+00:00',10))
            self.assertFalse(maybe_publish(conn,datetime(2026,10,28,17,30,tzinfo=timezone.utc)))
if __name__=='__main__': unittest.main()
