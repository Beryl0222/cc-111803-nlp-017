"""合成文献证据核对。

把每条陈述（会议摘要、期刊稿、勘误后的重述）与查询的人群、比较条件、
结局逐项核对，并把方法学限制绑定到它实际约束的那条陈述上：

* 两个亚组陈述不能合并成一个总体结果；
* 安全性陈述的人群限制不会被复制到功效结论上，因为限制按陈述逐条推导；
* 同一试验的多个文献版本只算一项独立研究，不以文章数量充当重复验证；
* 勘误只联动它实际更正的试验与结局，其他结局的陈述独立保留；
* 归属存疑的试验不计入独立证据数，也不得给出确定的重复验证结论。
"""

SCOPE_FIELDS = ('population', 'comparison', 'outcome')
FIELD_LABELS = {'population': '人群', 'comparison': '比较条件', 'outcome': '结局'}

DIRECT = '直接回答'
OUT_OF_SCOPE = '范围不同'
UNREPORTED = '资料未报告'
EXPLORATORY = '探索性依据'

USABLE = '可直接使用'
SUPPORTING = '仅作旁证'
FULLTEXT = '需查阅全文'
UNCONFIRMED = '归属待确认'


class StudyRegister:
    """试验与文献目录：用登记号确定试验归属，疑似归属单独登记。"""

    def __init__(self, trials, papers):
        self.trials = {trial['id']: trial for trial in trials}
        self.papers = {paper['id']: paper for paper in papers}

    def paper(self, paper_id):
        try:
            return self.papers[paper_id]
        except KeyError as exc:
            raise ValueError(f'未登记的文献来源：{paper_id}') from exc

    def trial_id(self, paper_id):
        return self.paper(paper_id)['trial']

    def registry_id(self, paper_id):
        return self.trials[self.trial_id(paper_id)]['registry']

    def trial_confirmed(self, paper_id):
        trial = self.trials[self.trial_id(paper_id)]
        return trial.get('attribution', 'confirmed') != 'suspected'


class ScopeFit:
    """逐条核对人群、比较条件、结局与分析口径。"""

    @staticmethod
    def judge(claim, question):
        for name in SCOPE_FIELDS:
            if claim.get(name) is None:
                return UNREPORTED, name
            if claim[name] != question[name]:
                return OUT_OF_SCOPE, name
        if claim.get('analysis') == '探索性' and not question.get('include_exploratory'):
            return EXPLORATORY, 'analysis'
        return DIRECT, None

    @staticmethod
    def reason(status, field, claim, question):
        if status == DIRECT:
            return '人群、比较条件、结局均与查询一致，且为非探索性分析'
        if status == OUT_OF_SCOPE:
            return (f"{FIELD_LABELS[field]}不一致：陈述为“{claim[field]}”，"
                    f"查询为“{question[field]}”，只能回答范围不同的问题")
        if status == UNREPORTED:
            return f"陈述未报告{FIELD_LABELS[field]}，无法核对查询条件，需查阅全文确认"
        detail = '、'.join(ScopeFit._analysis_notes(claim))
        suffix = f"（{detail}）" if detail else ''
        scope = '亚组分析' if claim.get('population_scope') == 'subgroup' else '该分析'
        return f"{scope}为探索性分析{suffix}，不能替代总体结果，只能作为探索性依据"

    @staticmethod
    def _analysis_notes(claim):
        notes = []
        if claim.get('population_scope') == 'subgroup':
            notes.append('仅覆盖亚组人群')
        if claim.get('adjustment'):
            notes.append(f"采用{claim['adjustment']}校正口径")
        return notes


def derive_limitations(claim):
    """从陈述自身字段推导限制，只约束本陈述，不跨陈述复制。"""
    limitations = []
    if claim.get('population_scope') == 'subgroup':
        limitations.append({
            'kind': '亚组限制',
            'detail': f"仅适用于“{claim.get('population', '未报告人群')}”亚组，"
                      '不能外推为总体结果',
            'constrains_claim': claim['id'],
        })
    if claim.get('analysis') == '探索性':
        limitations.append({
            'kind': '探索性分析',
            'detail': '预设之外的探索性分析，不构成确证性结论',
            'constrains_claim': claim['id'],
        })
    if claim.get('adjustment'):
        limitations.append({
            'kind': '校正口径',
            'detail': f"结论仅在{claim['adjustment']}校正口径下成立",
            'constrains_claim': claim['id'],
        })
    if claim.get('sample_note'):
        limitations.append({
            'kind': '样本限制',
            'detail': claim['sample_note'],
            'constrains_claim': claim['id'],
        })
    return limitations


class CorrectionIndex:
    """勘误按“试验 + 结局”联动，只影响勘误实际更正的那些陈述。"""

    def __init__(self, studies):
        self._studies = studies
        self._by_trial_outcome = {}
        self._by_claim = {}
        for paper in studies.papers.values():
            if paper.get('kind') != 'corrigendum':
                continue
            for correction in paper.get('corrections', []):
                key = (correction['trial'], correction['outcome'])
                entry = {
                    'corrigendum': paper['id'],
                    'trial': correction['trial'],
                    'outcome': correction['outcome'],
                    'replacement': correction.get('replaces_claim'),
                    'note': correction.get('note', ''),
                }
                self._by_trial_outcome.setdefault(key, []).append(entry)
                for claim_id in correction.get('targets_claims', []):
                    self._by_claim[claim_id] = entry

    def affecting(self, claim):
        # 勘误文献上的重述本身就是更正后的版本，不再被同一份勘误标记。
        if self._studies.paper(claim['paper']).get('kind') == 'corrigendum':
            return []
        entry = self._by_claim.get(claim['id'])
        if entry is not None:
            return [{**entry, 'match': 'explicit'}]
        if claim.get('outcome') is None:
            return []
        trial = self._studies.trial_id(claim['paper'])
        return [{**entry, 'match': 'trial-outcome'}
                for entry in self._by_trial_outcome.get((trial, claim['outcome']), [])]


class EvidenceSelection:
    def __init__(self, studies):
        self.studies = studies

    def select(self, case):
        corrections = CorrectionIndex(self.studies)
        rows = []
        direct_trials = set()
        unconfirmed = []
        for claim in case['findings']:
            row = self._evaluate(claim, case['query'], corrections)
            rows.append(row)
            if row['trial_attribution'] == 'suspected':
                unconfirmed.append({
                    'claim': claim['id'],
                    'trial': row['trial'],
                    'registry': row['registry'],
                    'status': row['status'],
                    'note': '试验归属为疑似，关系未确认，不计入独立证据数，'
                            '不得据此给出确定的重复验证结论',
                })
            elif row['status'] == DIRECT and row['usable_as'] == USABLE:
                direct_trials.add(row['trial'])
        return {
            'query': case['query'],
            'claims': rows,
            'independent_direct_studies': len(direct_trials),
            'direct_study_basis': sorted(direct_trials),
            'unconfirmed_links': unconfirmed,
        }

    def _evaluate(self, claim, question, corrections):
        paper = self.studies.paper(claim['paper'])
        trial = self.studies.trial_id(claim['paper'])
        registry = self.studies.registry_id(claim['paper'])
        confirmed = self.studies.trial_confirmed(claim['paper'])
        status, field = ScopeFit.judge(claim, question)
        reasons = [ScopeFit.reason(status, field, claim, question)]

        linked = corrections.affecting(claim)
        if linked:
            reasons.append(self._correction_note(linked[0]))
        if not confirmed:
            reasons.append(
                f'该文献与试验 {registry} 的归属仅为疑似，关系未经确认，'
                '不能据此给出确定的重复验证结论')

        usable, usable_reason = self._usability(status, linked, confirmed, claim)
        row = {
            'claim': claim['id'],
            'paper': claim['paper'],
            'paper_kind': paper.get('kind', '未登记'),
            'trial': trial,
            'registry': registry,
            'trial_attribution': 'confirmed' if confirmed else 'suspected',
            'status': status,
            'limitations': derive_limitations(claim),
            'corrections': linked,
            'usable_as': usable,
            'reason': reasons,
            'usable_reason': usable_reason,
        }
        if claim.get('quote'):
            row['quote'] = claim['quote']
        return row

    @staticmethod
    def _correction_note(entry):
        scope = '该陈述被勘误显式更正' if entry['match'] == 'explicit' \
            else '该陈述与勘误更正的是同一试验的同一结局'
        if entry['replacement']:
            return (f"{scope}：勘误 {entry['corrigendum']} 已更正“{entry['outcome']}”，"
                    f"以陈述 {entry['replacement']} 为准；原文保留可追溯，仅作旁证")
        return (f"{scope}：勘误 {entry['corrigendum']} 已更正“{entry['outcome']}”，"
                '原陈述仅作历史旁证')

    @staticmethod
    def _usability(status, linked, confirmed, claim):
        if linked:
            return SUPPORTING, '已被勘误更正，仅保留为历史旁证，结论以勘误后陈述为准'
        if not confirmed:
            return UNCONFIRMED, '试验归属未确认，需核实登记关系后才能定级'
        if status == UNREPORTED:
            return FULLTEXT, '查询所需条件未报告，需查阅全文核对'
        if status == OUT_OF_SCOPE:
            return SUPPORTING, '范围与查询不同，只能作为范围不同问题的旁证'
        if status == EXPLORATORY:
            return SUPPORTING, '探索性依据不能替代总体结果，仅作旁证'
        return USABLE, '范围与查询一致且无未决勘误，可直接使用'


def assess(case, registry):
    selection = EvidenceSelection(StudyRegister(registry['trials'], registry['papers']))
    return selection.select(case)
