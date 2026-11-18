from pathlib import Path

from nlp_research_method_result_links.desk_cli import load_case


def test_two_papers_from_one_trial_count_once():
    fixture = Path(__file__).parents[1] / 'fixtures'
    output = load_case(fixture / 'work.json', fixture / 'business.json')
    assert output['independent_direct_studies'] == 1
    assert [row['status'] for row in output['claims']] == ['直接相关', '直接相关', '范围不同']
