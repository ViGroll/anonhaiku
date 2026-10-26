import unittest
from quality import evaluate, best_candidates

class QualityTests(unittest.TestCase):
    def test_bad_ending(self):
        self.assertIsNone(evaluate(('want the lights off so', "he's terrified or if I", 'want them right on the'))[0])
    def test_good_candidate(self):
        self.assertIsNotNone(evaluate(('the old cat is here','and the rain is falling on us','it is a cold day'))[0])
    def test_one_per_post(self):
        r=[dict(id=1,post_id=123,line1='the old cat is here',line2='and the rain is falling on us',line3='it is a cold day'),dict(id=2,post_id=123,line1='the moon is so bright',line2='and the wind is blowing all',line3='night the sun will come')]
        self.assertLessEqual(len(best_candidates(r,10)),1)

if __name__=='__main__': unittest.main()
