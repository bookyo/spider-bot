"""动画列表查询构造与索引声明测试。"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.routes import anime


class TestAnimeListQuery(unittest.TestCase):
    def test_build_anime_list_query_uses_exact_genre_match(self):
        query = anime.build_anime_list_query(genre=' 奇幻 ')

        self.assertEqual(query['genres'], '奇幻')
        self.assertNotIsInstance(query['genres'], dict)

    def test_build_anime_list_query_combines_year_and_genre(self):
        query = anime.build_anime_list_query(year=2019, genre='奇幻')

        self.assertEqual(query['year'], 2019)
        self.assertEqual(query['genres'], '奇幻')

    def test_anime_list_indexes_include_genres_year_discovered_at(self):
        self.assertIn(
            [('genres', 1), ('year', 1), ('discovered_at', -1)],
            anime.ANIME_LIST_INDEXES,
        )


if __name__ == '__main__':
    unittest.main()
