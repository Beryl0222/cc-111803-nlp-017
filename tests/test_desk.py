from copy import deepcopy
from pathlib import Path

import pytest

from nlp_research_method_result_links.desk import (
    CorrectionIndex,
    EvidenceSelection,
    ScopeFit,
    StudyRegister,
    assess,
    derive_limitations,
)
from nlp_research_method_result_links.desk_cli import load_case

FIXTURE = Path(__file__).parents[1] / 'fixtures'


@pytest.fixture()
def case():
    import json
    return json.loads((FIXTURE / 'work.json').read_text(encoding='utf-8'))


@pytest.fixture()
def registry():
    import json
    return json.loads((FIXTURE / 'business.json').read_text(encoding='utf-8'))


def by_id(output):
    return {row['claim']: row for row in output['claims']}


def test_fixture_end_to_end_statuses_and_independent_count(case, registry):
    output = assess(case, registry)
    rows = by_id(output)
    # 四种核对结论必须可区分
    assert rows['statement-1']['status'] == '直接回答'
    assert rows['statement-3']['status'] == '探索性依据'
    assert rows['statement-4']['status'] == '范围不同'
    assert rows['statement-6']['status'] == '资料未报告'
    # TR-8 的两个文献属同一试验且该结局已被勘误，只有独立试验 TR-9 计数
    assert output['independent_direct_studies'] == 1
    assert output['direct_study_basis'] == ['TR-9']


def test_two_versions_of_one_trial_count_once(registry):
    case = {
        'query': {'population': 'P', 'comparison': 'C', 'outcome': 'O',
                  'include_exploratory': False},
        'findings': [
            {'id': 'a', 'paper': 'ABS-1', 'population': 'P', 'comparison': 'C',
             'outcome': 'O', 'analysis': '主要', 'population_scope': 'overall'},
            {'id': 'b', 'paper': 'PAPER-1', 'population': 'P', 'comparison': 'C',
             'outcome': 'O', 'analysis': '主要', 'population_scope': 'overall'},
        ],
    }
    # 两份文献同属 TR-8，即使各自有陈述也只算一项独立研究
    output = assess(case, registry)
    assert output['independent_direct_studies'] == 1
    assert output['direct_study_basis'] == ['TR-8']
    assert {row['registry'] for row in output['claims']} == {'NCT-SYN-8'}


def test_limitations_bind_only_to_their_own_claim(case, registry):
    rows = by_id(assess(case, registry))
    kinds = {item['kind'] for item in rows['statement-3']['limitations']}
    assert kinds == {'亚组限制', '探索性分析', '校正口径', '样本限制'}
    for item in rows['statement-3']['limitations']:
        assert item['constrains_claim'] == 'statement-3'
    # 安全性陈述是全人群总体分析，不带亚组/探索性限制
    assert rows['statement-4']['limitations'] == []
    # 功效陈述不会继承安全性陈述的人群限制
    assert rows['statement-1']['limitations'] == []


def test_two_subgroup_statements_do_not_make_an_overall_result(registry):
    local_registry = deepcopy(registry)
    case = {
        'query': {'population': '总体', 'comparison': 'C', 'outcome': 'O',
                  'include_exploratory': False},
        'findings': [
            {'id': 'sg1', 'paper': 'PAPER-2', 'population': '40-60', 'comparison': 'C',
             'outcome': 'O', 'analysis': '探索性', 'population_scope': 'subgroup'},
            {'id': 'sg2', 'paper': 'PAPER-2', 'population': '61-80', 'comparison': 'C',
             'outcome': 'O', 'analysis': '探索性', 'population_scope': 'subgroup'},
        ],
    }
    output = assess(case, local_registry)
    assert {row['status'] for row in output['claims']} == {'范围不同'}
    assert output['independent_direct_studies'] == 0
    assert all(row['usable_as'] == '仅作旁证' for row in output['claims'])


def test_correction_links_only_same_trial_and_outcome(case, registry):
    rows = by_id(assess(case, registry))
    # 期刊陈述被勘误显式点名
    assert rows['statement-2']['corrections'][0]['match'] == 'explicit'
    # 会议摘要谈同一试验的同一结局，按试验+结局联动，但不是显式点名
    assert rows['statement-1']['corrections'][0]['match'] == 'trial-outcome'
    # 勘误自身的重述不再被同一份勘误标记
    assert rows['statement-3']['corrections'] == []
    # 安全性结局未被勘误触及，独立保留
    assert rows['statement-4']['corrections'] == []
    # 被更正的陈述只能作旁证，勘误后的探索性重述也只是旁证
    assert rows['statement-1']['usable_as'] == '仅作旁证'
    assert rows['statement-2']['usable_as'] == '仅作旁证'
    assert rows['statement-3']['usable_as'] == '仅作旁证'
    # 未被触及的独立试验陈述可直接使用
    assert rows['statement-5']['usable_as'] == '可直接使用'


def test_suspected_attribution_is_excluded_and_flagged(case, registry):
    rows = by_id(assess(case, registry))
    row = rows['statement-6']
    assert row['trial_attribution'] == 'suspected'
    assert row['usable_as'] == '归属待确认'
    unconfirmed = assess(case, registry)['unconfirmed_links']
    assert len(unconfirmed) == 1
    assert unconfirmed[0]['claim'] == 'statement-6'
    assert unconfirmed[0]['trial'] == 'TR-12'
    # 归属存疑的试验不得进入独立证据数
    assert 'TR-12' not in assess(case, registry)['direct_study_basis']


def test_unreported_requires_fulltext_when_attribution_confirmed(registry):
    case = {
        'query': {'population': 'P', 'comparison': 'C', 'outcome': 'O',
                  'include_exploratory': False},
        'findings': [
            {'id': 'x', 'paper': 'PAPER-2', 'population': 'P',
             'outcome': 'O', 'analysis': '主要', 'population_scope': 'overall'},
        ],
    }
    row = assess(case, registry)['claims'][0]
    assert row['status'] == '资料未报告'
    assert row['usable_as'] == '需查阅全文'


def test_exploratory_can_be_included_per_query(case, registry):
    inclusive = deepcopy(case)
    inclusive['query']['include_exploratory'] = True
    rows = by_id(assess(inclusive, registry))
    # 查询显式接受探索性证据时可直接回答，但限制仍然保留在该陈述上
    assert rows['statement-3']['status'] == '直接回答'
    assert {item['kind'] for item in rows['statement-3']['limitations']} >= {'亚组限制', '探索性分析'}


def test_quotes_are_kept_for_traceability(case, registry):
    for row in assess(case, registry)['claims']:
        assert row['quote']
        assert isinstance(row['reason'], list) and row['reason']


def test_scope_fit_four_way_classification():
    q = {'population': 'P', 'comparison': 'C', 'outcome': 'O', 'include_exploratory': False}
    base = {'population': 'P', 'comparison': 'C', 'outcome': 'O'}
    assert ScopeFit.judge({**base, 'analysis': '主要'}, q)[0] == '直接回答'
    assert ScopeFit.judge({**base, 'analysis': '探索性'}, q)[0] == '探索性依据'
    assert ScopeFit.judge({**base, 'outcome': 'X', 'analysis': '主要'}, q)[0] == '范围不同'
    assert ScopeFit.judge({'population': 'P', 'analysis': '主要'}, q)[0] == '资料未报告'


def test_derive_limitations_never_crosses_claims():
    claim = {'id': 'z', 'population': '40-60', 'population_scope': 'subgroup',
             'analysis': '探索性', 'adjustment': '校正X', 'sample_note': 'n=12'}
    limitations = derive_limitations(claim)
    assert all(item['constrains_claim'] == 'z' for item in limitations)
    assert derive_limitations({'id': 'plain'}) == []


def test_correction_index_ignores_corrigendum_papers(case, registry):
    studies = StudyRegister(registry['trials'], registry['papers'])
    index = CorrectionIndex(studies)
    restatement = next(c for c in case['findings'] if c['id'] == 'statement-3')
    assert index.affecting(restatement) == []


def test_unknown_paper_raises(registry):
    studies = StudyRegister(registry['trials'], registry['papers'])
    selection = EvidenceSelection(studies)
    bad_case = {'query': {'population': 'P', 'comparison': 'C', 'outcome': 'O'},
                'findings': [{'id': 'x', 'paper': 'GHOST', 'population': 'P',
                              'comparison': 'C', 'outcome': 'O', 'analysis': '主要'}]}
    with pytest.raises(ValueError):
        selection.select(bad_case)


def test_cli_load_case_matches_assess(case, registry, tmp_path):
    case_path = tmp_path / 'case.json'
    registry_path = tmp_path / 'registry.json'
    import json
    case_path.write_text(json.dumps(case, ensure_ascii=False), encoding='utf-8')
    registry_path.write_text(json.dumps(registry, ensure_ascii=False), encoding='utf-8')
    assert load_case(case_path, registry_path) == assess(case, registry)
