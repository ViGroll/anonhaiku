import unittest
from scanner import clean_comment, detect, syllables

class ScannerTests(unittest.TestCase):
    def test_syllable_dictionary(self):
        self.assertEqual(syllables('moon'), 1)
        self.assertEqual(syllables('blowing'), 2)
    def test_find_accidental_haiku(self):
        text = 'the moon is so bright and the wind is blowing all night the sun will come'
        self.assertIn(('the moon is so bright','and the wind is blowing all','night the sun will come'), detect(text))
    def test_no_result_for_short_text(self):
        self.assertEqual(detect('hello world'), [])
    def test_html_cleanup(self):
        self.assertEqual(clean_comment('hello<br>world &amp; moon'), 'hello world & moon')

if __name__ == '__main__':
    unittest.main()
