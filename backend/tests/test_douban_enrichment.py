"""测试豆瓣补齐辅助方法。"""

from anime_spider.utils.douban_enrichment import (
    extract_douban_subject_id,
    parse_douban_frodo_subject_payload,
)


def test_extract_douban_subject_id():
    assert extract_douban_subject_id('https://movie.douban.com/subject/1292052/') == '1292052'
    assert extract_douban_subject_id('https://www.douban.com/movie/subject/30319418/') == '30319418'


def test_parse_frodo_subject_payload():
    payload = {
        'title': '肖申克的救赎',
        'original_title': 'The Shawshank Redemption',
        'year': '1994',
        'directors': [{'name': '弗兰克·德拉邦特'}],
        'actors': [{'name': '蒂姆·罗宾斯'}, {'name': '摩根·弗里曼'}],
        'genres': ['剧情', '犯罪'],
        'intro': '一场谋杀案使银行家安迪蒙冤入狱。',
        'cover_url': 'https://img3.doubanio.com/view/photo/m_ratio_poster/public/p480747492.jpg',
        'rating': {'value': 9.7},
    }

    metadata = parse_douban_frodo_subject_payload(payload)

    assert metadata['title'] == '肖申克的救赎'
    assert metadata['original_title'] == 'The Shawshank Redemption'
    assert metadata['year'] == 1994
    assert metadata['director'] == '弗兰克·德拉邦特'
    assert metadata['voice_actors'] == ['蒂姆·罗宾斯', '摩根·弗里曼']
    assert metadata['genres'] == ['剧情', '犯罪']
    assert metadata['poster_url'] == 'https://img3.doubanio.com/view/photo/m_ratio_poster/public/p480747492.jpg'
    assert metadata['douban_rating'] == 9.7
