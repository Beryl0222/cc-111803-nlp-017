class StudyRegister:
    def __init__(self, trials, papers):
        self.trials = {trial['id']: trial['registry'] for trial in trials}
        self.papers = {paper['id']: paper for paper in papers}

    def registry_id(self, paper):
        return self.trials[self.papers[paper]['trial']]


class ScopeFit:
    @staticmethod
    def judge(claim, question):
        for name in ('outcome', 'comparison', 'population'):
            if claim.get(name) is not None and claim[name] != question[name]:
                return '范围不同'
        if any(claim.get(name) is None for name in ('outcome', 'comparison', 'population')):
            return '资料不足'
        return '直接相关' if claim['analysis'] != '探索性' or question['include_exploratory'] else '另查探索性结果'


class EvidenceSelection:
    def __init__(self, studies):
        self.studies = studies

    def select(self, claims, question):
        counts = set()
        rows = []
        for claim in claims:
            trial = self.studies.registry_id(claim['paper'])
            fit = ScopeFit.judge(claim, question)
            if fit == '直接相关':
                counts.add(trial)
            rows.append({'claim': claim['id'], 'trial': trial, 'status': fit})
        return {'independent_direct_studies': len(counts), 'claims': rows}


def assess(case, registry):
    selection = EvidenceSelection(StudyRegister(registry['trials'], registry['papers']))
    return selection.select(case['findings'], case['query'])
