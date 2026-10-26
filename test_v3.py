import unittest
from scanner import detect_with_boundaries
from quality import evaluate
from site_builder import display_lines

class V3Tests(unittest.TestCase):
    def test_sentence_boundaries(self):
        t='The moon is so bright and the wind is blowing all night the sun will come.'
        c = detect_with_boundaries(t)
        self.assertTrue(any(start and end for _,start,end in c))
    def test_upper_and_period(self):
        row={'line1':'I moved for a job','line2':'fairly far away and got','line3':'a dog for safety'}
        self.assertEqual(display_lines(row),['I moved for a job','fairly far away and got','a dog for safety.'])
    def test_vulgar_not_auto_rejected(self):
        self.assertIsNotNone(evaluate(('make your hard cock pulse','in my mouth and hands and shoot','cum all over me'))[0])
    def test_incomplete_end_rejected(self):
        self.assertIsNone(evaluate(('want the lights off so','he is terrified or if I','want them right on the'))[0])

if __name__=='__main__': unittest.main()
