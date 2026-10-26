import unittest
from quality import evaluate
from site_builder import display_lines

FAVORITES = [
 ('Reminds me of a', 'girl i paid to cuddle with', 'sad times beautiful'),
 ("Isn't attractive", 'the people at nude beaches', 'are the last people'),
 ('Same gender spaces', 'like locker rooms and showers', 'you hear a lot more'),
 ('Awkward for the first', 'few minutes once you are there', 'the awkwardness falls'),
 ('Think many people', "go to the sauna and don't", 'even really think'),
 ('Wrong with opium', 'ending slavery also', "doesn't seem that bad"),
 ('Yeah i feel like that', 'with partial nudity too', 'i do theatre'),
 ('Bullshit i dated', 'a gal and we fucked and i', 'accidentally'),
 ('Bun in her oven', 'and thwart her nefarious', 'plan hell abortion'),
 ('That i had a friend', 'once though who dated a guy', 'with a massive dong'),
 ('Retarded i sound', "when i'm mad and i can't help", 'but stumble over'),
]

class PreferenceTests(unittest.TestCase):
    def test_all_editorial_favorites_are_eligible(self):
        for lines in FAVORITES:
            with self.subTest(lines=lines):
                score, _ = evaluate(lines)
                self.assertIsNotNone(score)
                self.assertGreaterEqual(score, 40)

    def test_ends_on_article_rejected(self):
        self.assertIsNone(evaluate(('x y', 'a b', 'through the'))[0])

    def test_lowercase_and_full_stop(self):
        self.assertEqual(display_lines(dict(line1='BULLSHIT I DATED', line2='A GAL', line3='ACCIDENTALLY')),
                         ['Bullshit i dated', 'a gal', 'accidentally.'])

if __name__ == '__main__':
    unittest.main()
